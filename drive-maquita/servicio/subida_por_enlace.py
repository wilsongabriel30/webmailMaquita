"""Subida de archivos por enlace de carpeta (15/10/2026).

Un acceso creado con «Pedir archivos a alguien de fuera» (subida_externa.py:
`permite_subir`, correo y código obligatorio) deja a esa persona SUBIR
archivos y CREAR carpetas dentro. Nada más: no
puede borrar, renombrar ni sobrescribir. Si el nombre ya existe, el archivo
nuevo entra como «nombre (2).ext».

Las rutas viven bajo /api/almacen/publico/subida/ porque:
- ese prefijo ya está fuera del candado de sesión (la llave es el token);
- su location de nginx no corta a los 60 s ni pasa por la caché de páginas.

Mismas puertas que la vista pública: enlace vigente, no restringido, clave y
código al correo si los pide. Cada subida queda en la actividad del dueño.
"""
import logging
import os
from datetime import datetime, timezone

from flask import Blueprint, jsonify, request

log = logging.getLogger(__name__)

bp_subida_enlace = Blueprint('subida_enlace', __name__)

LIMITE_ARCHIVO = 2 * 1024 * 1024 * 1024      # 2 GB por archivo
MAX_PROFUNDIDAD = 12                           # niveles de carpeta al subir una carpeta


def _fila_subida(token):
    from almacen_bd import consultar
    filas = consultar('SELECT id, propietario_id, ruta, tipo, permisos, permite_subir, email, requiere_otp, '
                      'subida_desde, subida_hasta, subida_bytes, permite_macros FROM compartidos WHERE token = %s',
                      ((token or '').strip(),))
    return filas[0] if filas else None


def estado_subida(token):
    """(True, '') si este enlace deja subir AHORA; (False, motivo) si no.
    Siempre hace falta un correo concreto, el código obligatorio, estar dentro
    del plazo (protecciones_subida) y además una de dos:
      - se pidió expresamente («Pedir archivos a alguien de fuera»: `permite_subir`);
      - es un externo con rol Editor sobre una carpeta (compartir de siempre).
    Bajar a Lector o quitar el código le quita la subida. Ante cualquier duda, NO.
    (El bit 4 de `permisos` NO sirve: el rol «Editor» = 15 ya lo trae.)"""
    no = (False, 'Este enlace no permite subir archivos.')
    try:
        f = _fila_subida(token)
        if not f or not (f['requiere_otp'] and (f['email'] or '').strip()):
            return no
        if not f['permite_subir']:
            from subida_externa import externo_editor_de_carpeta
            if not externo_editor_de_carpeta(f):
                return no
        from protecciones_subida import plazo_abierto
        return plazo_abierto(f)
    except Exception as excepcion:
        log.warning('estado_subida(%s): %s', token, excepcion)
        return no


def permite_subir(token):
    return estado_subida(token)[0]


def _fallo(mensaje, codigo):
    return jsonify({'success': False, 'error': mensaje}), codigo


def _validar(token):
    """Devuelve (comp, None) si el enlace deja subir, o (None, respuesta)."""
    from integracion_faro import _compartido, _bloqueo_restringido, _clave_ok
    from api_acceso_externo import otp_ok
    comp = _compartido(token)
    if not comp:
        return None, _fallo('Este enlace ya no es válido.', 404)
    if _bloqueo_restringido(comp) is not None:
        return None, _fallo('Este enlace es solo para personas invitadas.', 403)
    if comp['expira_en'] is not None and comp['expira_en'] < datetime.now(timezone.utc):
        return None, _fallo('Este enlace caducó.', 410)
    if not _clave_ok(token, comp) or not otp_ok(token, comp):
        return None, _fallo('Vuelve a abrir el enlace e identifícate.', 403)
    puede, motivo = estado_subida(token)
    if not puede:
        return None, _fallo(motivo, 403)
    return comp, None


def _carpeta_destino(comp, subruta):
    """Ruta virtual (del dueño) de la carpeta de destino, ya contenida."""
    from integracion_faro import _fisica_dentro
    from seguridad_rutas import normalizar_ruta_virtual
    _base, destino = _fisica_dentro(comp, (subruta or '').strip('/'))
    if not destino or not os.path.isdir(destino):
        return None
    if not subruta.strip('/'):
        return normalizar_ruta_virtual(comp['ruta'])
    return normalizar_ruta_virtual(comp['ruta'] + '/' + subruta.strip('/'))


def _nombre_libre(propietario_id, carpeta, nombre):
    """«informe.pdf» → «informe (2).pdf» si ya existe: nunca se sobrescribe."""
    from seguridad_rutas import ruta_fisica
    base, punto, ext = nombre.rpartition('.')
    if not base:
        base, punto, ext = nombre, '', ''
    candidato, n = nombre, 1
    while os.path.exists(ruta_fisica(propietario_id, carpeta.rstrip('/') + '/' + candidato)):
        n += 1
        candidato = '%s (%d)%s%s' % (base, n, punto, ext)
    return candidato


def _asegurar_carpetas(propietario_id, carpeta, partes):
    """Crea (si faltan) las subcarpetas de una carpeta subida entera."""
    import nucleo_archivos as nucleo
    from seguridad_rutas import ruta_fisica
    for parte in partes:
        siguiente = carpeta.rstrip('/') + '/' + parte
        if not os.path.isdir(ruta_fisica(propietario_id, siguiente)):
            nucleo.crear_carpeta(propietario_id, carpeta, parte)
        carpeta = siguiente
    return carpeta


def _partes_limpias(relativa):
    partes = [p.strip() for p in (relativa or '').replace('\\', '/').split('/')]
    partes = [p for p in partes if p]
    if any(p in ('.', '..') for p in partes) or len(partes) > MAX_PROFUNDIDAD:
        raise ValueError('Ruta de carpeta no válida')
    return partes


def _quien():
    return (request.headers.get('X-Real-IP') or request.remote_addr or '')[:60]


@bp_subida_enlace.route('/publico/subida/<token>', methods=['POST'])
def subir_por_enlace(token):
    """Un archivo por petición: `archivo`, `subruta` y, si viene de una
    carpeta arrastrada, `relativa` (ruta de carpetas sin el nombre)."""
    import nucleo_archivos as nucleo
    import protecciones_subida as prot
    from almacen_bd import ejecutar
    from registro import registrar_actividad
    from seguridad_rutas import RutaInvalida

    comp, fallo = _validar(token)
    if fallo:
        return fallo
    if (request.content_length or 0) > LIMITE_ARCHIVO + 1024 * 1024:
        return _fallo('El archivo supera el límite de 2 GB.', 413)
    entrante = request.files.get('archivo')
    nombre = ((entrante.filename if entrante else '') or '').replace('\\', '/').split('/')[-1].strip()
    if not entrante or not nombre:
        return _fallo('No llegó ningún archivo.', 400)
    fila = _fila_subida(token)
    con_macros = bool(fila.get('permite_macros'))
    prohibido = prot.tipo_prohibido(nombre, con_macros)
    if prohibido:
        return _fallo(prohibido, 415)
    if not prot.cabe(fila, request.content_length):
        return _fallo('Se alcanzó el máximo de 20 GB para esta invitación. Avisa a quien te invitó.', 413)

    carpeta = _carpeta_destino(comp, request.form.get('subruta', ''))
    if not carpeta:
        return _fallo('La carpeta de destino ya no existe.', 404)
    dueno, quien = comp['propietario_id'], comp.get('email') or comp['id']
    temporal = None
    try:
        temporal, tamano = prot.a_temporal(entrante.stream, LIMITE_ARCHIVO)
        limpio, firma = prot.revisar_virus(temporal)
        if not limpio:
            registrar_actividad(dueno, 'virus_por_enlace', carpeta.rstrip('/') + '/' + nombre,
                                '%s · IP %s · %s' % (quien, _quien(), firma))
            log.warning('VIRUS rechazado por enlace %s: %s (%s) %s', comp['id'], nombre, firma, _quien())
            return _fallo('El antivirus detectó una amenaza en «%s» y no se guardó.' % nombre, 422)
        prohibido = prot.contenido_prohibido(temporal, nombre, con_macros)
        if prohibido:
            registrar_actividad(dueno, 'bloqueado_por_enlace', carpeta.rstrip('/') + '/' + nombre,
                                '%s · IP %s · macros o programa' % (quien, _quien()))
            return _fallo(prohibido, 415)
        # Con la opción avanzada, lo que trae macros entra pero queda señalado.
        marca = ' · con macros' if con_macros and (prot.tipo_prohibido(nombre) or prot.tiene_macros(temporal, nombre)) else ''
        carpeta = _asegurar_carpetas(dueno, carpeta, _partes_limpias(request.form.get('relativa')))
        nombre = _nombre_libre(dueno, carpeta, nombre)
        with open(temporal, 'rb') as flujo:
            r = nucleo.subir(dueno, carpeta, nombre, flujo)
        ejecutar('UPDATE compartidos SET subida_bytes = subida_bytes + %s WHERE id = %s', (tamano, comp['id']))
    except (RutaInvalida, ValueError) as excepcion:
        return _fallo(str(excepcion), 400)
    except RuntimeError as excepcion:
        log.error('Subida por enlace %s sin antivirus: %s', comp['id'], excepcion)
        return _fallo('No se pudo revisar el archivo con el antivirus. Inténtalo en unos minutos.', 503)
    except Exception:
        log.exception('Subida por enlace %s fallida (%s)', comp['id'], nombre)
        return _fallo('No se pudo guardar el archivo. Inténtalo otra vez.', 500)
    finally:
        prot.borrar(temporal)

    import conversion_automatica
    conversion_automatica.encolar(dueno, r['ruta'])       # formato antiguo → moderno, en segundo plano
    registrar_actividad(dueno, 'subio_por_enlace', r['ruta'],
                        '%s · IP %s · %s%s' % (quien, _quien(), r.get('tamano_humano', ''), marca))
    log.info('Subida por enlace %s: %s (%s)', comp['id'], r['ruta'], _quien())
    return jsonify({'success': True, 'nombre': r['nombre'],
                    'tamano': r.get('tamano_humano', '')}), 201


@bp_subida_enlace.route('/publico/subida/<token>/reglas', methods=['GET'])
def reglas_por_enlace(token):
    """Lo que la página necesita para avisar ANTES de subir (el servidor lo
    vuelve a comprobar todo al recibir cada archivo)."""
    comp, fallo = _validar(token)
    if fallo:
        return fallo
    fila = _fila_subida(token)
    return jsonify({'success': True, 'macros': bool(fila.get('permite_macros')),
                    'hasta': fila['subida_hasta'].isoformat() if fila.get('subida_hasta') else None})


@bp_subida_enlace.route('/publico/subida/<token>/carpeta', methods=['POST'])
def crear_carpeta_por_enlace(token):
    import nucleo_archivos as nucleo
    from registro import registrar_actividad
    from seguridad_rutas import RutaInvalida, ruta_fisica

    comp, fallo = _validar(token)
    if fallo:
        return fallo
    carpeta = _carpeta_destino(comp, request.form.get('subruta', ''))
    if not carpeta:
        return _fallo('La carpeta de destino ya no existe.', 404)
    nombre = (request.form.get('nombre') or '').strip()
    dueno = comp['propietario_id']
    try:
        if os.path.exists(ruta_fisica(dueno, carpeta.rstrip('/') + '/' + nombre)):
            return _fallo('Ya existe algo con ese nombre.', 409)
        r = nucleo.crear_carpeta(dueno, carpeta, nombre)
    except RutaInvalida as excepcion:
        return _fallo(str(excepcion), 400)
    registrar_actividad(dueno, 'carpeta_por_enlace', r['ruta'],
                        '%s · IP %s' % (comp.get('email') or comp['id'], _quien()))
    return jsonify({'success': True, 'nombre': r['nombre']}), 201


def registrar(app):
    """Monta las rutas bajo /api/almacen y las exime de CSRF (sin sesión)."""
    app.register_blueprint(bp_subida_enlace, url_prefix='/api/almacen')
    csrf = app.extensions.get('csrf')
    if csrf:
        csrf.exempt(bp_subida_enlace)
