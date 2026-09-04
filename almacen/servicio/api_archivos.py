# -*- coding: utf-8 -*-
"""
API de archivos del Almacén Maquita.
====================================
Implementa el contrato /api/nextcloud/* (ver docs/CONTRATO-API.md) para que
el explorador web del sistema central funcione sin cambiar UNA línea del frontend.

Códigos según el contrato REAL congelado en Fase 0:
  - crear (carpeta, archivo) → HTTP 201 · lo demás → 200 · error → JSON con success=false.

Autoría: Equipo de Tecnología Maquita — 2026-07-03
"""
import logging
import os

from flask import Blueprint, jsonify, request, send_file, session

import nucleo_archivos as nucleo
from registro import registrar_actividad
from seguridad_rutas import RutaInvalida, normalizar_ruta_virtual, ruta_fisica

log = logging.getLogger('almacen.api')

bp_archivos = Blueprint('almacen_archivos', __name__)


# ── autenticación ────────────────────────────────────────────────────────
CARPETA_CHAT = '/Archivos del chat'


def _es_carpeta_chat(ruta) -> bool:
    """La carpeta raiz 'Archivos del chat' es del sistema: no se borra, mueve ni renombra (su contenido si)."""
    r = '/' + str(ruta or '').strip().strip('/')
    return r.lower() in (CARPETA_CHAT.lower(), '/grabaciones de reuniones')   # carpetas raíz del sistema


from almacen_bd import consultar as _consultar_bd
CARPETA_CORREO = '/Archivos del correo'


def _es_de_correo(ruta) -> bool:
    r = '/' + str(ruta or '').strip().strip('/')
    return r.lower() == CARPETA_CORREO.lower() or r.lower().startswith(CARPETA_CORREO.lower() + '/')


def _error_pertenece_al_correo(usuario, ruta):
    """403 con los datos del correo dueño: el cliente/web lleva al correo para eliminarlo desde allí."""
    r = '/' + str(ruta or '').strip().strip('/')
    info = None
    try:
        filas = _consultar_bd("""SELECT buzon, carpeta_correo, uid, asunto, remitente, fecha_correo FROM correo_adjuntos
                              WHERE usuario_id = %s AND ruta_drive = %s AND estado = 'activo' ORDER BY id DESC LIMIT 1""", (int(usuario), r))
        if filas:
            f = filas[0]
            info = {'buzon': f['buzon'], 'carpeta': f['carpeta_correo'], 'uid': f['uid'], 'asunto': f['asunto'],
                    'remitente': f['remitente'], 'fecha': str(f['fecha_correo'] or ''),
                    'url': f"https://mail.maquita.org/webmail/?folder={f['carpeta_correo']}&uid={f['uid']}"}
    except Exception as _e:
        print(f'[correo-drive] sin datos del correo: {_e!r}')
        info = None
    resp = jsonify({'success': False, 'error': 'pertenece_al_correo',
                    'mensaje': 'Este archivo pertenece a un correo. Para eliminarlo, abre el correo y elimínalo desde allí '
                               '(esa acción no es reversible: el correo y sus adjuntos se eliminarán permanentemente).',
                    'correo': info})
    return resp, 403


def usuario_actual() -> int:
    """ID del usuario autenticado.
    - Montado dentro del sistema central: usa la sesión del sistema central (`usuario_id`) o flask_login.
    - Servicio independiente (futuro, tras nginx): cabecera interna de confianza.
    Sin identidad → aborta con 401."""
    from flask import abort
    usuario_id = session.get('usuario_id') or session.get('_user_id')
    if not usuario_id:
        try:
            from flask_login import current_user
            if getattr(current_user, 'is_authenticated', False):
                usuario_id = current_user.id
        except Exception:
            pass
    if not usuario_id:
        usuario_id = request.headers.get('X-Almacen-Usuario-Id')
    if not usuario_id:
        abort(401)
    return int(usuario_id)


def _permiso_unidad(usuario, ruta, escritura=False) -> bool:
    """Si la ruta es de una unidad compartida, verifica que el usuario tenga acceso
    (lectura, o escritura según su rol). Rutas personales: siempre True.
    Falla CERRADO: ante cualquier error, sin acceso (antes abría)."""
    try:
        from permisos_unidad import permiso_unidad
        return permiso_unidad(usuario, ruta, escritura)
    except Exception as excepcion:
        log.error('No se pudo comprobar el permiso de unidad (%s): %s', ruta, excepcion)
        return False


def error(mensaje: str, codigo: int = 500):
    """Respuesta de error uniforme (misma forma que el sistema actual)."""
    return jsonify({'success': False, 'error': mensaje}), codigo


# ── salud ────────────────────────────────────────────────────────────────
@bp_archivos.route('/status', methods=['GET'])
def estado():
    """Salud del servicio (el explorador la consulta al abrir).
    Incluye `es_master`: el frontend usa esto para MOSTRAR u OCULTAR las
    opciones de administración. El usuario normal ni las ve ni recibe errores."""
    from almacen_bd import es_master
    usuario = usuario_actual()
    return jsonify({'success': True, 'motor': 'almacen-maquita', 'version': '0.1.0',
                    'es_master': es_master(usuario)})


# ── listar ───────────────────────────────────────────────────────────────
@bp_archivos.route('/archivos', methods=['GET'])
def listar():
    """GET /archivos?ruta=/x — estructura completa que consume el explorador."""
    usuario = usuario_actual()
    ruta = request.args.get('ruta', '/')
    try:
        ruta = normalizar_ruta_virtual(ruta)
        if not _permiso_unidad(usuario, ruta, escritura=False):
            return error('No tienes acceso a esta unidad compartida', 403)
        carpetas, archivos = nucleo.listar(usuario, ruta)
    except RutaInvalida as excepcion:
        return error(str(excepcion), 400)
    except FileNotFoundError:
        return error('Carpeta no encontrada', 404)

    # Migas de pan (breadcrumb) igual que el contrato
    migas, acumulada = [], ''
    for parte in [p for p in ruta.split('/') if p]:
        acumulada += '/' + parte
        migas.append({'nombre': parte, 'ruta': acumulada})

    return jsonify({
        'success': True,
        'ruta_actual': ruta,
        'breadcrumb': migas,
        'carpetas': carpetas,
        'archivos': archivos,
        'total_carpetas': len(carpetas),
        'total_archivos': len(archivos),
    })


# ── subir ────────────────────────────────────────────────────────────────
@bp_archivos.route('/archivos', methods=['POST'])
def subir():
    """POST /archivos — multipart: campo(s) `archivo` + campo `carpeta`.
    Streaming a disco; contrato: HTTP 201."""
    usuario = usuario_actual()
    carpeta = request.form.get('carpeta', '/')
    if not _permiso_unidad(usuario, carpeta, escritura=True):
        return error('No tienes permiso de escritura en esta unidad', 403)
    archivos = request.files.getlist('archivo')
    if not archivos:
        return error('No se recibió ningún archivo', 400)
    subidos = []
    try:
        for almacenado in archivos:
            r = nucleo.subir(usuario, carpeta, almacenado.filename, almacenado.stream)
            subidos.append(r)
            registrar_actividad(usuario, 'subio', r['ruta'], r.get('tamano_humano', ''))
    except RutaInvalida as excepcion:
        return error(str(excepcion), 400)
    return jsonify({'success': True, 'archivos': subidos,
                    'total': len(subidos)}), 201


# ── descargar ────────────────────────────────────────────────────────────
@bp_archivos.route('/archivos/descargar', methods=['GET'])
def descargar():
    """GET /archivos/descargar?ruta= — entrega el archivo.
    NOTA producción: detrás de nginx se cambia send_file por X-Accel-Redirect
    (los bytes los sirve nginx directo del disco, zero-copy)."""
    usuario = usuario_actual()
    try:
        fisica = ruta_fisica(usuario, request.args.get('ruta', ''))
    except RutaInvalida as excepcion:
        return error(str(excepcion), 400)
    if not os.path.isfile(fisica):
        return error('Archivo no encontrado', 404)

    if request.headers.get('X-Almacen-Accel') == '1':
        # Modo nginx: respuesta vacía con cabecera de redirección interna
        respuesta = jsonify({'success': True})
        respuesta.headers['X-Accel-Redirect'] = '/almacen-datos-interno' + \
            fisica[len(os.path.dirname(os.path.dirname(os.path.dirname(fisica)))):]
        return respuesta
    return send_file(fisica, as_attachment=True,
                     download_name=os.path.basename(fisica))


# ── eliminar (papelera) ──────────────────────────────────────────────────
@bp_archivos.route('/archivos/ver', methods=['GET'])
def ver():
    """GET /archivos/ver?ruta= — entrega el archivo INLINE (para previsualizar en el navegador)."""
    usuario = usuario_actual()
    try:
        fisica = ruta_fisica(usuario, request.args.get('ruta', ''))
    except RutaInvalida as excepcion:
        return error(str(excepcion), 400)
    if not os.path.isfile(fisica):
        return error('Archivo no encontrado', 404)
    return send_file(fisica, as_attachment=False,
                     download_name=os.path.basename(fisica))


_EXT_IMAGEN = {'jpg', 'jpeg', 'png', 'gif', 'webp', 'bmp', 'svg'}


def _miniatura_pdf(fisica: str) -> str:
    """Genera (y cachea) la miniatura PNG de la primera página de un PDF con pdftoppm.
    Devuelve la ruta del PNG, o None si no se pudo."""
    import subprocess
    import hashlib
    try:
        mtime = int(os.path.getmtime(fisica))
        clave = hashlib.sha1(f'{fisica}:{mtime}'.encode()).hexdigest()
        cache_dir = '/tmp/almacen-previews'
        os.makedirs(cache_dir, exist_ok=True)
        salida = os.path.join(cache_dir, clave)          # pdftoppm añade .png
        png = salida + '.png'
        if not os.path.exists(png):
            subprocess.run(['pdftoppm', '-png', '-singlefile', '-scale-to', '400',
                            fisica, salida], timeout=15, check=True,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return png if os.path.exists(png) else None
    except Exception as excepcion:
        log.debug('miniatura pdf falló: %s', excepcion)
        return None


_CACHE_PREVIEWS = '/tmp/almacen-previews'


def _clave_cache(fisica: str, sufijo: str = '') -> str:
    import hashlib
    mtime = int(os.path.getmtime(fisica))
    return hashlib.sha1(f'{fisica}:{mtime}{sufijo}'.encode()).hexdigest()


def _miniatura_imagen(fisica: str, lado: int = 400) -> str:
    """Miniatura real de una imagen (Pillow). Enviar la foto completa (varios MB)
    por cada celda de la cuadrícula era lo que hacía lenta la vista."""
    try:
        os.makedirs(_CACHE_PREVIEWS, exist_ok=True)
        png = os.path.join(_CACHE_PREVIEWS, _clave_cache(fisica, f':{lado}') + '.jpg')
        if not os.path.exists(png):
            from PIL import Image
            with Image.open(fisica) as im:
                im.thumbnail((lado, lado))
                if im.mode not in ('RGB', 'L'):
                    im = im.convert('RGB')
                im.save(png, 'JPEG', quality=80)
        return png if os.path.exists(png) else None
    except Exception as excepcion:
        log.debug('miniatura imagen falló: %s', excepcion)
        return None


# Lección de la Nube (2026): una carpeta llena de documentos disparaba TODAS
# las conversiones a la vez y tumbaba el servidor de previews ("fork storm").
# Aquí: máximo 2 conversiones simultáneas por worker (las demás esperan) y
# los fallos no se reintentan por 5 minutos (caché negativa).
import threading as _threading_conv
_SEM_CONVERSIONES = _threading_conv.Semaphore(2)
_FALLOS_CONVERSION: dict = {}   # clave_cache -> momento del fallo


def _miniatura_office(usuario: int, ruta: str, fisica: str, ext: str) -> str:
    """Miniatura de un documento office generada por el CONVERSOR del Document
    Server (el mismo OnlyOffice de la edición) y cacheada en disco. El DS
    descarga el archivo con un token firmado, igual que al editar."""
    try:
        from api_onlyoffice import (TIPOS_DOCUMENTO, URL_PUBLICA,
                                    firmar_jwt, secreto_ds, url_interna_ds)
        if ext not in TIPOS_DOCUMENTO or not (secreto_ds() and url_interna_ds()):
            return None
        os.makedirs(_CACHE_PREVIEWS, exist_ok=True)
        clave = _clave_cache(fisica, ':oo')
        png = os.path.join(_CACHE_PREVIEWS, clave + '.png')
        if os.path.exists(png):
            return png
        import time as _time
        import requests as _requests
        # caché negativa: si acaba de fallar, no insistir (protege al DS)
        ultimo_fallo = _FALLOS_CONVERSION.get(clave, 0)
        if _time.time() - ultimo_fallo < 300:
            return None
        if not _SEM_CONVERSIONES.acquire(timeout=10):
            return None   # DS ocupado: mejor icono que avalancha
        exp = int(_time.time()) + 3600
        t_desc = firmar_jwt({'u': usuario, 'r': ruta, 'uso': 'descarga', 'exp': exp})
        cuerpo = {
            'async': False,
            'filetype': ext,
            'outputtype': 'png',
            'thumbnail': {'aspect': 1, 'first': True, 'width': 400, 'height': 400},
            'key': _clave_cache(fisica, ':thumb')[:20],
            'url': f'{URL_PUBLICA}/api/almacen/onlyoffice/download?t={t_desc}',
        }
        cuerpo['token'] = firmar_jwt(cuerpo)
        try:
            r = _requests.post(f'{url_interna_ds()}/ConvertService.ashx',
                               json=cuerpo, headers={'Accept': 'application/json'},
                               timeout=20)
            datos = r.json()
            if not datos.get('fileUrl'):
                log.debug('conversor sin fileUrl: %s', datos)
                _FALLOS_CONVERSION[clave] = _time.time()
                return None
            img = _requests.get(datos['fileUrl'], timeout=20)
            if img.status_code != 200 or not img.content:
                _FALLOS_CONVERSION[clave] = _time.time()
                return None
            with open(png, 'wb') as destino:
                destino.write(img.content)
            return png
        finally:
            _SEM_CONVERSIONES.release()
    except Exception as excepcion:
        log.debug('miniatura office falló: %s', excepcion)
        return None


def _respuesta_preview(archivo: str, mime: str = 'image/png'):
    """send_file + caché de navegador: la miniatura de un archivo no cambia
    (la clave incluye el mtime), así que el navegador puede guardarla un día."""
    respuesta = send_file(archivo, mimetype=mime, as_attachment=False)
    respuesta.headers['Cache-Control'] = 'private, max-age=86400'
    return respuesta


@bp_archivos.route('/preview', methods=['GET'])
def preview():
    """GET /preview?file=<ruta> — miniatura/vista previa RÁPIDA (todo cacheado
    en disco y en el navegador). Imágenes: thumbnail real. PDF: primera página.
    Office: miniatura generada por el Document Server. Otros: 404 (icono)."""
    usuario = usuario_actual()
    ruta = request.args.get('file') or request.args.get('ruta') or ''
    try:
        fisica = ruta_fisica(usuario, ruta)
    except RutaInvalida:
        return error('Ruta inválida', 400)
    if not os.path.isfile(fisica):
        return error('Sin vista previa', 404)
    ext = os.path.splitext(fisica)[1].lstrip('.').lower()
    if ext in _EXT_IMAGEN:
        if ext == 'svg':
            return _respuesta_preview(fisica, 'image/svg+xml')
        png = _miniatura_imagen(fisica)
        if png:
            return _respuesta_preview(png, 'image/jpeg')
        return send_file(fisica, as_attachment=False)
    if ext == 'pdf':
        png = _miniatura_pdf(fisica)
        if png:
            return _respuesta_preview(png)
    png = _miniatura_office(usuario, ruta, fisica, ext)
    if png:
        return _respuesta_preview(png)
    return error('Sin vista previa', 404)


@bp_archivos.route('/archivos/acceso-directo', methods=['POST'])
def crear_acceso_directo():
    """POST /archivos/acceso-directo — {destino, carpeta} : crea un acceso directo (shortcut)."""
    usuario = usuario_actual()
    datos = request.get_json() or {}
    if not datos.get('destino'):
        return error('destino requerido', 400)
    try:
        r = nucleo.crear_acceso_directo(usuario, datos.get('carpeta', '/'),
                                        datos['destino'], datos.get('nombre'))
    except RutaInvalida as e:
        return error(str(e), 400)
    except FileNotFoundError as e:
        return error(str(e), 404)
    return jsonify({'success': True, **r}), 201


@bp_archivos.route('/recientes', methods=['GET'])
def recientes():
    """GET /recientes — archivos modificados más recientemente (vista 'Reciente')."""
    usuario = usuario_actual()
    items = nucleo.recientes(usuario)
    return jsonify({'success': True, 'carpetas': [], 'archivos': items,
                    'total': len(items)})


@bp_archivos.route('/archivos', methods=['DELETE'])
def eliminar():
    if _es_carpeta_chat(request.args.get('ruta')):
        return error('La carpeta "Archivos del chat" es del sistema y no se puede eliminar (su contenido si)', 403)
    if _es_de_correo(request.args.get('ruta')):
        return _error_pertenece_al_correo(usuario_actual(), request.args.get('ruta'))
    """DELETE /archivos?ruta= — mueve a la papelera (recuperable)."""
    usuario = usuario_actual()
    ruta = request.args.get('ruta')
    if not ruta:
        return error('Ruta requerida', 400)
    if not _permiso_unidad(usuario, ruta, escritura=True):
        return error('No tienes permiso para borrar en esta unidad', 403)
    try:
        nucleo.enviar_a_papelera(usuario, ruta)
    except RutaInvalida as excepcion:
        return error(str(excepcion), 400)
    except FileNotFoundError:
        return error('No existe el elemento', 404)
    registrar_actividad(usuario, 'elimino', ruta)
    # T-18: si es un archivo del chat, avisar al chat (se oculta para este usuario hasta que lo restaure)
    try:
        from hook_chat import avisar_chat, es_de_chat
        avisar_chat(usuario, ruta, 'papelera')
        if es_de_chat(ruta):
            return jsonify({'success': True, 'message': 'Enviado a la papelera',
                            'aviso': 'Este archivo también dejará de verse en tu chat. Si lo restauras desde la papelera, vuelve a aparecer.'})
    except Exception:
        pass
    return jsonify({'success': True, 'message': 'Enviado a la papelera'})


# ── mover / copiar / renombrar ──────────────────────────────────────────
@bp_archivos.route('/archivos/mover', methods=['POST'])
def mover():
    _d = request.get_json(silent=True) or {}
    if _es_carpeta_chat(_d.get('origen')):
        return error('La carpeta "Archivos del chat" es del sistema y no se puede mover', 403)
    if _es_de_correo(_d.get('origen')) or _es_de_correo(_d.get('destino')):
        return error('«Archivos del correo» la administra el correo: no se puede mover nada hacia o desde esa carpeta', 403)
    """POST /archivos/mover — {origen, destino}."""
    usuario = usuario_actual()
    datos = request.get_json() or {}
    if not datos.get('origen') or not datos.get('destino'):
        return error('origen y destino son requeridos', 400)
    try:
        nucleo.mover(usuario, datos['origen'], datos['destino'])
    except RutaInvalida as excepcion:
        return error(str(excepcion), 400)
    except FileNotFoundError:
        return error('El origen no existe', 404)
    registrar_actividad(usuario, 'movio', datos['destino'], datos['origen'])
    return jsonify({'success': True, 'message': 'Movido correctamente'})


@bp_archivos.route('/archivos/copiar', methods=['POST'])
def copiar():
    """POST /archivos/copiar — {origen, destino}."""
    usuario = usuario_actual()
    datos = request.get_json() or {}
    if not datos.get('origen') or not datos.get('destino'):
        return error('origen y destino son requeridos', 400)
    try:
        nucleo.copiar(usuario, datos['origen'], datos['destino'])
    except RutaInvalida as excepcion:
        return error(str(excepcion), 400)
    except FileNotFoundError:
        return error('El origen no existe', 404)
    registrar_actividad(usuario, 'copio', datos['destino'], datos['origen'])
    return jsonify({'success': True, 'message': 'Copiado correctamente'})


@bp_archivos.route('/archivos/renombrar', methods=['POST'])
def renombrar():
    _d = request.get_json(silent=True) or {}
    if _es_carpeta_chat(_d.get('ruta') or _d.get('origen')):
        return error('La carpeta "Archivos del chat" es del sistema y no se puede renombrar', 403)
    if _es_de_correo(_d.get('ruta') or _d.get('origen')):
        return error('«Archivos del correo» la administra el correo: no se puede renombrar', 403)
    """POST /archivos/renombrar — {ruta, nuevo_nombre}."""
    usuario = usuario_actual()
    datos = request.get_json() or {}
    if not datos.get('ruta') or not datos.get('nuevo_nombre'):
        return error('ruta y nuevo_nombre son requeridos', 400)
    try:
        ruta_nueva = nucleo.renombrar(usuario, datos['ruta'], datos['nuevo_nombre'])
    except RutaInvalida as excepcion:
        return error(str(excepcion), 400)
    except FileNotFoundError:
        return error('No existe el elemento', 404)
    registrar_actividad(usuario, 'renombro', ruta_nueva, datos['ruta'])
    return jsonify({'success': True, 'ruta_nueva': ruta_nueva})


# ── carpetas ─────────────────────────────────────────────────────────────
@bp_archivos.route('/carpetas', methods=['POST'])
def crear_carpeta():
    """POST /carpetas — {nombre, ruta}. Contrato: HTTP 201."""
    usuario = usuario_actual()
    datos = request.get_json() or {}
    if not datos.get('nombre'):
        return error('Nombre requerido', 400)
    if not _permiso_unidad(usuario, datos.get('ruta', '/'), escritura=True):
        return error('No tienes permiso de escritura en esta unidad', 403)
    try:
        carpeta = nucleo.crear_carpeta(usuario, datos.get('ruta', '/'), datos['nombre'])
    except RutaInvalida as excepcion:
        return error(str(excepcion), 400)
    registrar_actividad(usuario, 'creo_carpeta', carpeta['ruta'])
    return jsonify({'success': True, 'carpeta': carpeta}), 201


# ── búsqueda y cuota ─────────────────────────────────────────────────────
@bp_archivos.route('/buscar', methods=['GET'])
def buscar():
    """GET /buscar?q= — contrato: {resultados, termino, total}."""
    usuario = usuario_actual()
    termino = request.args.get('q', '').strip()
    if len(termino) < 2:
        return error('La búsqueda debe tener al menos 2 caracteres', 400)
    resultados = nucleo.buscar(usuario, termino)
    return jsonify({'success': True, 'resultados': resultados,
                    'termino': termino, 'total': len(resultados)})


@bp_archivos.route('/cuota', methods=['GET'])
def cuota():
    """GET /cuota — uso y límite de almacenamiento."""
    usuario = usuario_actual()
    datos = nucleo.cuota(usuario)
    datos['success'] = True
    return jsonify(datos)
