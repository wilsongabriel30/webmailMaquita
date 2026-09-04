# -*- coding: utf-8 -*-
"""
API de compartir del Almacén Maquita.
=====================================
Compartir con personas o por enlace público (semántica Google Drive),
listado de compartidos y búsqueda de usuarios para el autocompletado.

Autoría: Equipo de Tecnología Maquita — 2026-07-03
"""
import logging
import os
import secrets

from flask import Blueprint, jsonify, request

from almacen_bd import consultar, ejecutar
from api_archivos import error, usuario_actual
from config_almacen import URL_PUBLICA, URL_LINKS
import macros
from seguridad_rutas import RutaInvalida, normalizar_ruta_virtual, ruta_fisica

log = logging.getLogger('almacen.compartir')

bp_compartir = Blueprint('almacen_compartir', __name__)

TIPO_USUARIO, TIPO_GRUPO, TIPO_ENLACE = 0, 1, 3


@bp_compartir.route('/compartir', methods=['POST'])
def compartir():
    """
    POST /compartir — {ruta, tipo, permisos, con_quien?, clave?, expira?}
    tipo: 0=usuario, 1=grupo, 3=enlace público. Contrato: HTTP 201.
    """
    usuario = usuario_actual()
    datos = request.get_json() or {}
    return crear_compartido(usuario, datos)


def crear_compartido(usuario, datos):
    """Núcleo de compartir, reutilizable SIN sesión web.

    Lo usa también el endpoint por token DAV para «Compartir» desde la app de
    Windows (P-12). Recibe ya resueltos `usuario` (id) y `datos` (dict) y
    devuelve la misma respuesta Flask (jsonify, código) que la ruta. No lee la
    sesión ni CSRF: quien lo llame es responsable de autenticar al `usuario`.
    """
    try:
        ruta = normalizar_ruta_virtual(datos.get('ruta', ''))
    except RutaInvalida as excepcion:
        return error(str(excepcion), excepcion.codigo)
    if ruta == '/':
        return error('No se puede compartir la raíz', 400)

    # ── QUIÉN PUEDE SACAR DOCUMENTACIÓN DE UNA UNIDAD COMPARTIDA ────────────
    # Las unidades guardan documentación de la organización, no de una persona.
    # Compartir algo de una unidad —sobre todo hacia fuera— solo lo pueden hacer
    # los MASTER y el MANAGER de esa unidad. Un editor o un lector tienen acceso
    # para trabajar, no para decidir qué sale de la Fundación.
    # Se comprueba aquí, en el núcleo, y no en la pantalla: así vale igual desde
    # la web, desde la app de Windows y desde cualquier llamada directa.
    if ruta.startswith('/unidades/'):
        try:
            unidad_id = int(ruta.split('/')[2])
        except (IndexError, ValueError):
            return error('Ruta de unidad no válida', 400)
        from api_unidades import rol_en_unidad
        if rol_en_unidad(usuario, unidad_id) != 'manager':
            return error(
                'Solo el administrador de la unidad compartida puede compartir '
                'su documentación. Pedíselo a quien la administra.', 403)

    # ── LO QUE SE COMPARTE TIENE QUE EXISTIR ────────────────────────────────
    # 05/08/2026: se estaban creando enlaces a rutas inexistentes. El enlace
    # nacía «bien» (con su URL y todo), pero al abrirlo la otra persona veía
    # «No encontramos ese contenido» y el formulario de SOLICITAR ACCESO — que
    # es el mensaje para un enlace caducado. Quien compartía quedaba mal sin
    # saber por qué, y quien recibía creía que le faltaban permisos.
    # Caso real: una carpeta «Talk» que en el Nextcloud estaba vacía y por eso
    # nunca llegó al Drive; el explorador la seguía ofreciendo para compartir.
    # Se comprueba aquí, en el núcleo, para que valga también desde la app de
    # Windows y desde cualquier llamada directa.
    try:
        # escritura=True: en una unidad compartida publican manager/editor; un
        # viewer o un no miembro no puede sacar por enlace lo que solo mira (C-7).
        if not os.path.exists(ruta_fisica(usuario, ruta, escritura=True)):
            return error(
                'Eso ya no está en tu Drive, así que no se puede compartir. '
                'Actualizá la vista (F5) y comprobá que siga ahí.', 404)
    except RutaInvalida as excepcion:
        return error(str(excepcion), excepcion.codigo)

    # ── POLÍTICA DE MACROS ──────────────────────────────────────────────────
    # Un archivo con macros es de uso interno de los trabajadores de Maquita.
    # No sale de la organización con la macro dentro: se ejecutaría en el
    # Excel de quien lo reciba, junto con la lógica de negocio que contenga.
    # (OnlyOffice no ejecuta VBA, así que aquí nunca corre; el riesgo es que
    # el archivo SALGA.) Quien necesite enviarlo, descarga la copia limpia:
    # mismo formato, mismos datos y fórmulas, sin la macro.
    # Se comprueba por CONTENIDO, no por extensión: renombrar un .xlsm a .xlsx
    # no sirve para saltarse esto. Ver macros.py y
    # 00-CLAUDE-CONTEXTO/EDICION-REFERENCIAS-Y-MACROS-ONLYOFFICE.md
    try:
        fisica_origen = ruta_fisica(usuario, ruta)
        nombre_origen = ruta.rsplit('/', 1)[-1]
        if (os.path.isfile(fisica_origen)
                and macros.tiene_macros(fisica_origen, nombre_origen)):
            return error(
                'Este archivo tiene macros y no se puede compartir: las '
                'macros son de uso interno de Maquita. Descargá la copia sin '
                'macros («%s») y compartí esa: conserva los datos, las '
                'fórmulas y el formato.'
                % macros.nombre_copia_limpia(nombre_origen), 409)
    except Exception as excepcion:
        # Fallar CERRADO: si no se puede comprobar, no se comparte.
        log.warning('No se pudo comprobar macros de %s: %s',
                    ruta, excepcion)
        return error('No se pudo verificar el archivo antes de compartirlo. '
                     'Intentá de nuevo; si sigue, avisá a Tecnología.', 503)

    tipo = int(datos.get('tipo', TIPO_ENLACE))
    permisos = int(datos.get('permisos', 1))
    destinatario = (datos.get('con_quien') or datos.get('shareWith') or datos.get('destinatario') or '').strip() or None
    if tipo in (TIPO_USUARIO, TIPO_GRUPO) and not destinatario:
        return error('Falta el destinatario', 400)

    token = secrets.token_urlsafe(24) if tipo == TIPO_ENLACE else None

    # Expiración (días desde hoy) y clave opcional — como los enlaces de Drive de pago.
    import hashlib
    from datetime import datetime, timezone, timedelta
    expira_en = None
    try:
        dias = int(datos.get('expira_dias') or 0)
        if dias > 0:
            expira_en = datetime.now(timezone.utc) + timedelta(days=dias)
    except (TypeError, ValueError):
        expira_en = None
    clave = (datos.get('clave') or '').strip()
    clave_hash = hashlib.sha256(clave.encode()).hexdigest() if clave else None
    # ¿Se permite descargar/copiar? (control tipo Drive; por defecto sí)
    permite_descarga = datos.get('permite_descarga', True) is not False
    # Fase C: verificacion por codigo al correo (elegible al compartir)
    requiere_otp = datos.get('requiere_otp') is True

    # Compartir con una PERSONA por correo (interno o externo) con rol lector/editor.
    # Genera SIEMPRE un token (el enlace es la credencial de acceso; puede llevar clave).
    email = (datos.get('email') or '').strip().lower()[:255] or None
    rol = (datos.get('rol') or '').strip()   # 'lector' | 'editor'

    # ── P-13: CÓMO se abre el enlace (descargar / ver / editar) ─────────────
    # Es la elección de quien comparte, igual que en Drive o Nextcloud:
    #   'descargar' → el enlace entrega el archivo (comportamiento clásico)
    #   'ver'       → abre OnlyOffice en SOLO LECTURA
    #   'editar'    → abre OnlyOffice en EDICIÓN, guardando en el Drive
    # «editar» implica permiso de escritura para el invitado; por eso ajusta
    # `puede_editar`, que es lo que ya lee el editor público (config-public).
    modo = (datos.get('modo') or '').strip().lower()
    if modo not in ('descargar', 'ver', 'editar'):
        modo = 'descargar'
    puede_editar = (rol == 'editor') or (modo == 'editar')
    if modo == 'editar':
        permisos = permisos | 2
    if email:
        import re as _re
        if not _re.fullmatch(r'[^@\s]+@[^@\s]+\.[^@\s]+', email):
            return error('Correo inválido', 400)
        if token is None:
            token = secrets.token_urlsafe(24)

    fila = ejecutar("""
        INSERT INTO compartidos (propietario_id, ruta, tipo, destinatario, token, permisos,
                                 expira_en, clave_hash, permite_descarga, email, puede_editar,
                                 requiere_otp, modo)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING id, creado_en
    """, (usuario, ruta, tipo, destinatario, token, permisos,
          expira_en, clave_hash, permite_descarga, email, puede_editar,
          requiere_otp, modo))

    compartido = {
        'id': fila['id'],
        'ruta': ruta,
        'tipo': tipo,
        'permisos': permisos,
        'con_quien': destinatario or email,
        'email': email,
        'rol': rol or ('editor' if permisos & 2 else 'lector'),
        'puede_editar': puede_editar,
        'modo': modo,
        'token': token,
        # Enlace ÚNICO: /s/<token> ya sabe qué hacer según el `modo` guardado
        # (descargar, abrir en solo lectura o abrir en edición). Así el que
        # comparte pega siempre el mismo enlace.
        'url': f'{URL_LINKS}/s/{token}' if token else None,
        # Enlace directo de EDICIÓN en línea (invitado sin cuenta FARO)
        'url_editar': (f'{URL_LINKS}/e/{token}'
                       if token else None),
        'expira_en': expira_en.isoformat() if expira_en else None,
        'con_clave': bool(clave_hash),
        'permite_descarga': permite_descarga,
        'requiere_otp': requiere_otp,
        'creado_en': fila['creado_en'].isoformat(),
    }
    # Fase B: invitación por correo a la persona (best-effort: si el correo
    # falla, el compartir NO falla). Emisor único: email_service de FARO.
    if email:
        try:
            from correo_compartir import enviar_invitacion
            compartido['correo_enviado'] = enviar_invitacion(compartido, usuario)
        except Exception as _exc:
            log.warning('Invitación por correo falló: %s', _exc)

    log.info('Compartido id=%s ruta=%s tipo=%s por usuario %s',
             fila['id'], ruta, tipo, usuario)
    return jsonify({'success': True, 'compartido': compartido}), 201


@bp_compartir.route('/shares', methods=['GET'])
@bp_compartir.route('/compartidos', methods=['GET'])
def listar_compartidos():
    """GET /compartidos — lo que YO he compartido, o (con ?tipo=conmigo) lo que
    otras personas me compartieron a MÍ."""
    usuario = usuario_actual()
    if (request.args.get('tipo') or '').strip() == 'conmigo':
        from vista_compartidos import listar_para
        items = listar_para(usuario)
        return jsonify({'success': True, 'compartidos': items,
                        'shares': items, 'total': len(items)})
    ruta_filtro = (request.args.get('ruta') or '').strip()
    # En una carpeta de UNIDAD COMPARTIDA, quien la administra ve TODOS los
    # compartidos de esa ruta, no solo los que creó él (12/08/2026): antes
    # cada administrador veía únicamente los suyos y parecía que faltaba gente.
    filtro = 'propietario_id = %s'
    parametros = [usuario]
    if ruta_filtro.startswith('/unidades/'):
        try:
            from api_unidades import rol_en_unidad
            id_unidad = int(ruta_filtro.split('/')[2])
            if rol_en_unidad(usuario, id_unidad) == 'manager':
                filtro = 'TRUE'
                parametros = []
        except Exception:
            pass
    sql = """
        SELECT id, ruta, tipo, destinatario AS con_quien, token, permisos, creado_en,
               puede_editar, permite_descarga, expira_en, clave_hash, email,
               accesos, modo, requiere_otp
        FROM compartidos WHERE """ + filtro + """
    """
    if ruta_filtro:
        sql += " AND ruta = %s"
        parametros.append(ruta_filtro)
    sql += " ORDER BY creado_en DESC"
    filas = consultar(sql, tuple(parametros))
    # Resolver en UNA consulta el nombre completo de los destinatarios
    # internos: `destinatario` guarda el username de FARO y el diálogo de
    # compartir necesita mostrar el nombre de la persona (12/08/2026).
    nombre_por_username = {}
    usernames = {f['con_quien'] for f in filas if f.get('con_quien')}
    if usernames:
        try:
            personas = consultar("""
                SELECT u.username,
                       COALESCE(t.nombres || ' ' || t.apellidos,
                                u.full_name, u.username) AS nombre
                FROM usuarios u
                LEFT JOIN trabajadores t ON u.trabajador_id = t.id
                WHERE u.username IN %s
            """, (tuple(usernames),), nomina=True)
            nombre_por_username = {p['username']: p['nombre'] for p in personas}
        except Exception as exc:
            log.warning('No se pudo resolver nombres de destinatarios: %s', exc)
    compartidos = []
    for fila in filas:
        fila = dict(fila)
        fila['creado_en'] = fila['creado_en'].isoformat()
        fila['url'] = f"{URL_LINKS}/s/{fila['token']}" if fila['token'] else None
        fila['url_editar'] = (f"{URL_LINKS}/e/{fila['token']}"
                              if fila['token'] else None)
        fila['con_clave'] = bool(fila.pop('clave_hash', None))
        fila['permite_descarga'] = bool(fila.get('permite_descarga'))
        fila['puede_editar'] = bool(fila.get('puede_editar'))
        fila['expira_en'] = fila['expira_en'].isoformat() if fila.get('expira_en') else None
        # Alias que espera el frontend (compatibilidad con la vista de la Nube)
        fila['fecha_expiracion'] = fila['expira_en']
        fila['password_protegido'] = fila['con_clave']
        # Alias que espera la lista «Personas con acceso» del explorador:
        # nombre completo, y el identificador/correo en los dos nombres de
        # campo que consume el frontend (12/08/2026).
        fila['compartido_con'] = fila.get('email') or fila.get('con_quien') or ''
        fila['share_with'] = fila.get('con_quien') or fila.get('email') or ''
        fila['compartido_con_nombre'] = (
            nombre_por_username.get(fila.get('con_quien'))
            or fila.get('email') or fila.get('con_quien') or '')
        fila['share_with_displayname'] = fila['compartido_con_nombre']
        # Para el gestor de enlaces: cuantas veces se abrio, como se abre y si
        # es un enlace ABIERTO (lo ve cualquiera que tenga la direccion) o esta
        # protegido con clave, con codigo al correo o con caducidad.
        fila['accesos'] = int(fila.get('accesos') or 0)
        fila['modo'] = fila.get('modo') or 'descargar'
        fila['requiere_otp'] = bool(fila.get('requiere_otp'))
        fila['es_publico'] = bool(fila['token']) and fila['tipo'] == TIPO_ENLACE
        fila['abierto_a_cualquiera'] = (fila['es_publico'] and not fila['con_clave']
                                        and not fila['requiere_otp']
                                        and not fila['expira_en'])
        compartidos.append(fila)
    # 'shares' es el alias que consume el frontend del explorador; 'compartidos'
    # es el nombre del contrato del motor. Se devuelven ambos.
    return jsonify({'success': True, 'compartidos': compartidos,
                    'shares': compartidos, 'total': len(compartidos)})


@bp_compartir.route('/compartidos-conmigo', methods=['GET'])
def compartidos_conmigo():
    """GET /compartidos-conmigo — lo que otras personas me compartieron a MI
    correo (vigente). El acceso a cada elemento es su token de enlace: la UI
    usa /publico/<token> (descargar) y el editor público (abrir en línea)."""
    usuario = usuario_actual()
    fila = consultar('SELECT username, email FROM usuarios WHERE id = %s',
                     (usuario,), nomina=True)
    correo = (fila[0]['email'] or '').strip().lower() if fila else ''
    _nombre_usuario = (fila[0]['username'] or '').strip() if fila else ''
    if not correo and not _nombre_usuario:
        return jsonify({'success': True, 'compartidos': [], 'total': 0})
    filas = consultar("""
        SELECT id, propietario_id, ruta, token, puede_editar, permite_descarga,
               clave_hash, expira_en, creado_en
        FROM compartidos
        WHERE (LOWER(email) = %s OR destinatario = %s) AND propietario_id <> %s
          AND (expira_en IS NULL OR expira_en > NOW())
        ORDER BY creado_en DESC
    """, (correo, _nombre_usuario, usuario))
    if not filas:
        return jsonify({'success': True, 'compartidos': [], 'total': 0})
    duenos = tuple({int(f['propietario_id']) for f in filas})
    nombres = consultar("""
        SELECT u.id, COALESCE(t.nombres || ' ' || t.apellidos, u.full_name, u.username) AS nombre
        FROM usuarios u LEFT JOIN trabajadores t ON u.trabajador_id = t.id
        WHERE u.id IN %s
    """, (duenos,), nomina=True)
    nombre_de = {n['id']: n['nombre'] for n in nombres}
    from api_onlyoffice import EXTENSIONES_EDITABLES, TIPOS_DOCUMENTO
    resultado = []
    for f in filas:
        nombre = f['ruta'].rsplit('/', 1)[-1]
        extension = nombre.rsplit('.', 1)[-1].lower() if '.' in nombre else ''
        tamano = None
        es_carpeta = False
        try:
            fisica = ruta_fisica(f['propietario_id'], f['ruta'])
            if os.path.isdir(fisica):
                es_carpeta, tamano = True, 0
            elif os.path.isfile(fisica):
                tamano = os.path.getsize(fisica)
        except RutaInvalida:
            pass
        if tamano is None:
            continue   # el dueño lo movió o borró: no se muestra
        from permisos_compartidos import ruta_compartida
        resultado.append({
            'id': f['id'], 'nombre': nombre, 'extension': extension,
            'es_carpeta': es_carpeta,
            'ruta': ruta_compartida(f['propietario_id'], f['ruta']),
            'tamano_bytes': tamano, 'token': f['token'],
            'de': nombre_de.get(f['propietario_id']) or f"Usuario {f['propietario_id']}",
            'puede_editar': bool(f['puede_editar']) and extension in EXTENSIONES_EDITABLES,
            'abre_en_linea': extension in TIPOS_DOCUMENTO,
            'permite_descarga': bool(f['permite_descarga']),
            'requiere_clave': bool(f['clave_hash']),
            'expira_en': f['expira_en'].isoformat() if f['expira_en'] else None,
            'creado_en': f['creado_en'].isoformat(),
        })
    return jsonify({'success': True, 'compartidos': resultado, 'total': len(resultado)})


@bp_compartir.route('/compartidos/<int:compartido_id>', methods=['DELETE'])
def eliminar_compartido(compartido_id):
    """DELETE /compartidos/<id> — deja de compartir (solo el propietario)."""
    usuario = usuario_actual()
    fila = ejecutar("""
        DELETE FROM compartidos WHERE id = %s AND propietario_id = %s RETURNING id
    """, (compartido_id, usuario))
    if not fila:
        return error('Compartido no encontrado', 404)
    return jsonify({'success': True, 'message': 'Se dejó de compartir'})


@bp_compartir.route('/compartidos/<int:compartido_id>', methods=['PUT'])
def actualizar_compartido(compartido_id):
    """PUT /compartidos/<id> — cambia parámetros de un enlace ya creado
    (solo el propietario): rol/permiso, expiración, clave, descarga. Cualquier
    campo omitido se deja igual. Para revocar se usa DELETE."""
    usuario = usuario_actual()
    datos = request.get_json() or {}

    fila = consultar("""
        SELECT id, permisos, puede_editar, clave_hash, expira_en, permite_descarga
        FROM compartidos WHERE id = %s AND propietario_id = %s
    """, (compartido_id, usuario))
    if not fila:
        return error('Compartido no encontrado', 404)
    actual = dict(fila[0])

    import hashlib
    from datetime import datetime, timezone, timedelta

    # rol / permisos
    puede_editar = actual['puede_editar']
    permisos = actual['permisos']
    if 'rol' in datos:
        puede_editar = (str(datos.get('rol')).strip() == 'editor')
        permisos = 15 if puede_editar else 1
    if 'permisos' in datos:
        permisos = int(datos.get('permisos'))
        puede_editar = bool(permisos & 2)

    # expiración: número de días desde hoy, o 0/null para quitarla
    expira_en = actual['expira_en']
    if 'expira_dias' in datos:
        try:
            dias = int(datos.get('expira_dias') or 0)
            expira_en = (datetime.now(timezone.utc) + timedelta(days=dias)) if dias > 0 else None
        except (TypeError, ValueError):
            pass

    # clave: cadena nueva, o '' para quitarla (si la clave no viene, no se toca)
    clave_hash = actual['clave_hash']
    if 'clave' in datos:
        clave = (datos.get('clave') or '').strip()
        clave_hash = hashlib.sha256(clave.encode()).hexdigest() if clave else None

    permite_descarga = actual['permite_descarga']
    if 'permite_descarga' in datos:
        permite_descarga = datos.get('permite_descarga') is not False

    if 'requiere_otp' in datos:
        ejecutar('UPDATE compartidos SET requiere_otp = %s WHERE id = %s AND propietario_id = %s',
                 (datos.get('requiere_otp') is True, compartido_id, usuario))

    ejecutar("""
        UPDATE compartidos
        SET permisos = %s, puede_editar = %s, expira_en = %s,
            clave_hash = %s, permite_descarga = %s
        WHERE id = %s AND propietario_id = %s
    """, (permisos, puede_editar, expira_en, clave_hash, permite_descarga,
          compartido_id, usuario))
    log.info('Compartido id=%s actualizado por usuario %s', compartido_id, usuario)
    return jsonify({'success': True, 'compartido': {
        'id': compartido_id, 'permisos': permisos, 'puede_editar': puede_editar,
        'rol': 'editor' if puede_editar else 'lector',
        'expira_en': expira_en.isoformat() if expira_en else None,
        'con_clave': bool(clave_hash), 'permite_descarga': permite_descarga,
    }})


@bp_compartir.route('/compartir/ajustes', methods=['GET', 'POST'])
def ajustes_de_elemento():
    """Ajustes de compartición de un elemento propio (hallazgos CO-02 y CO-03).

    GET  /compartir/ajustes?ruta=/carpeta
    POST /compartir/ajustes  {ruta, acceso_limitado?, editores_comparten?}

    Solo el dueño: la ruta se resuelve dentro de SU espacio, así que nadie puede
    leer ni tocar los ajustes de otra persona.
    """
    from ajustes_compartir import obtener, establecer
    usuario = usuario_actual()
    datos = request.get_json(silent=True) or {}
    crudo = datos.get('ruta') if request.method == 'POST' else request.args.get('ruta')
    try:
        ruta = normalizar_ruta_virtual(crudo or '')
    except RutaInvalida as excepcion:
        return error(str(excepcion), excepcion.codigo)
    if ruta == '/':
        return error('La raíz no admite ajustes de compartición', 400)

    if request.method == 'GET':
        return jsonify({'success': True, 'ruta': ruta, 'ajustes': obtener(usuario, ruta)})

    def booleano(clave):
        if clave not in datos:
            return None
        return datos.get(clave) is True

    ajustes = establecer(usuario, ruta,
                         acceso_limitado=booleano('acceso_limitado'),
                         editores_comparten=booleano('editores_comparten'))
    log.info('Ajustes de compartición ruta=%s usuario=%s -> %s', ruta, usuario, ajustes)
    return jsonify({'success': True, 'ruta': ruta, 'ajustes': ajustes})


@bp_compartir.route('/usuarios/buscar', methods=['GET'])
def buscar_usuarios():
    """
    GET /usuarios/buscar?q= — autocompletado para compartir.
    Contrato: {usuarios: [{id, nombre, email, tipo}], grupos, total}.
    Lee de la base de nómina (solo lectura): son los mismos usuarios de FARO.
    """
    usuario_actual()
    consulta = (request.args.get('q') or '').strip()
    limite = min(int(request.args.get('limite', 10)), 25)
    if len(consulta) < 2:
        return jsonify({'success': True, 'usuarios': [], 'grupos': [], 'total': 0})

    filas = consultar("""
        SELECT u.username AS id,
               u.id AS usuario_id,
               COALESCE(t.nombres || ' ' || t.apellidos, u.full_name, u.username) AS nombre,
               COALESCE(u.email, '') AS email
        FROM usuarios u
        LEFT JOIN trabajadores t ON u.trabajador_id = t.id
        WHERE u.active = TRUE
          AND (unaccent(LOWER(u.username)) LIKE '%%' || unaccent(LOWER(%s)) || '%%'
               OR unaccent(LOWER(COALESCE(t.nombres, ''))) LIKE '%%' || unaccent(LOWER(%s)) || '%%'
               OR unaccent(LOWER(COALESCE(t.apellidos, ''))) LIKE '%%' || unaccent(LOWER(%s)) || '%%'
               OR unaccent(LOWER(COALESCE(u.full_name, ''))) LIKE '%%' || unaccent(LOWER(%s)) || '%%'
               OR LOWER(COALESCE(u.email, '')) LIKE '%%' || LOWER(%s) || '%%')
        ORDER BY
          (unaccent(LOWER(COALESCE(t.apellidos, u.username))) LIKE unaccent(LOWER(%s)) || '%%') DESC,
          (unaccent(LOWER(u.username)) LIKE unaccent(LOWER(%s)) || '%%') DESC,
          u.username
        LIMIT %s
    """, (consulta, consulta, consulta, consulta, consulta,
          consulta, consulta, limite), nomina=True)

    usuarios = [{'id': f['id'], 'usuario_id': f['usuario_id'], 'nombre': f['nombre'],
                 'email': f['email'], 'tipo': 'usuario'} for f in filas]
    return jsonify({'success': True, 'usuarios': usuarios, 'grupos': [],
                    'total': len(usuarios)})


@bp_compartir.route('/usuarios/buscar-faro', methods=['GET'])
def buscar_usuarios_faro():
    """
    GET /usuarios/buscar-faro?q=juan&limite=10 — autocompletado del dialogo
    "Compartir" del explorador.

    POR QUE EXISTE (06/08/2026): el explorador es el mismo en modo Nube y en modo
    Almacen, y su dialogo de compartir llama SIEMPRE a `<API_BASE>/usuarios/buscar-faro`.
    Ese endpoint solo existia en el modulo Nextcloud (`/api/nextcloud/...`), asi que
    en modo Almacen la llamada caia en el catch-all y el buscador respondia
    "No se encontraron usuarios" para TODO el mundo. Aqui se sirve el mismo
    contrato, adaptado al Almacen (que comparte por nombre de usuario, sin Nextcloud).

    Contrato que espera el navegador por cada persona:
      nombre, email, username, username_nc, departamento, cargo, tipo, share_type.
    `username_nc` es el identificador que se manda luego como destinatario.
    """
    usuario_actual()
    consulta = (request.args.get('q') or '').strip()
    limite = min(int(request.args.get('limite', 10) or 10), 25)
    if len(consulta) < 2:
        return jsonify({'success': True, 'usuarios': [], 'total': 0})

    filas = consultar("""
        SELECT u.id, u.username, COALESCE(u.email, '') AS email,
               COALESCE(t.nombres || ' ' || t.apellidos, u.full_name, u.username) AS nombre,
               COALESCE(d.nombre, '') AS departamento, COALESCE(c.nombre, '') AS cargo,
               COALESCE(t.foto_perfil, '') AS foto_perfil
        FROM usuarios u
        LEFT JOIN trabajadores t ON u.trabajador_id = t.id
        LEFT JOIN departamentos_empresa d ON t.departamento_id = d.id
        LEFT JOIN cargos c ON t.cargo_id = c.id
        WHERE u.active = TRUE
          AND (unaccent(LOWER(u.username)) LIKE '%%' || unaccent(LOWER(%s)) || '%%'
               OR unaccent(LOWER(COALESCE(t.nombres, ''))) LIKE '%%' || unaccent(LOWER(%s)) || '%%'
               OR unaccent(LOWER(COALESCE(t.apellidos, ''))) LIKE '%%' || unaccent(LOWER(%s)) || '%%'
               OR unaccent(LOWER(COALESCE(u.full_name, ''))) LIKE '%%' || unaccent(LOWER(%s)) || '%%'
               OR LOWER(COALESCE(u.email, '')) LIKE '%%' || LOWER(%s) || '%%')
        ORDER BY
          (unaccent(LOWER(COALESCE(t.apellidos, u.username))) LIKE unaccent(LOWER(%s)) || '%%') DESC,
          u.username
        LIMIT %s
    """, (consulta, consulta, consulta, consulta, consulta, consulta, limite),
        nomina=True)

    usuarios = [{
        'id': f['id'], 'usuario_id': f['id'], 'faro_id': f['id'],
        'nombre': f['nombre'],
        'email': f['email'], 'username': f['username'],
        'username_nc': f['username'],       # el Almacen comparte por nombre de usuario
        'departamento': f.get('departamento') or '', 'cargo': f.get('cargo') or '',
        # Foto de perfil de la ficha de nomina. Nginx sirve /uploads/ desde
        # interfaces/web/estaticos/uploads/, asi que basta anteponer la barra.
        'avatar_url': ('/' + f['foto_perfil'].lstrip('/')) if f.get('foto_perfil') else '',
        'tipo': 'interno', 'share_type': 0, 'requiere_sync': False,
        # El navegador pinta estas dos: sin ellas aparecia "undefined" (06/08/2026)
        'creable': True, 'badge': 'Maquita', 'badge_class': 'bg-success',
    } for f in filas]

    # Correo externo: si escribieron un correo completo que no es de nadie de la
    # casa, se ofrece igual para poder invitar a alguien de fuera.
    if '@' in consulta and '.' in consulta.split('@')[-1]:
        correo = consulta.lower()
        if not any((u['email'] or '').lower() == correo for u in usuarios):
            usuarios.append({
                'id': None, 'usuario_id': None, 'faro_id': None, 'nombre': correo,
                'email': correo, 'username': correo, 'username_nc': None,
                'departamento': '', 'cargo': 'Persona externa', 'avatar_url': '',
                'tipo': 'externo', 'share_type': 4, 'requiere_sync': False,
                'creable': True, 'badge': 'Externo', 'badge_class': 'bg-warning text-dark',
            })

    return jsonify({'success': True, 'usuarios': usuarios, 'total': len(usuarios)})
