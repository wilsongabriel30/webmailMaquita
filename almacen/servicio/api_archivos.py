# -*- coding: utf-8 -*-
"""
API de archivos del Almacén Maquita.
====================================
Implementa el contrato /api/nextcloud/* (ver docs/CONTRATO-API.md) para que
el explorador web de FARO funcione sin cambiar UNA línea del frontend.

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
def usuario_actual() -> int:
    """ID del usuario autenticado.
    - Montado dentro de FARO: usa la sesión de FARO (`usuario_id`) o flask_login.
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
    (lectura, o escritura según su rol). Rutas personales: siempre True."""
    try:
        from api_unidades import permiso_unidad
        return permiso_unidad(usuario, ruta, escritura)
    except Exception:
        return True


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


@bp_archivos.route('/preview', methods=['GET'])
def preview():
    """GET /preview?file=<ruta> — miniatura/vista previa. Imágenes: sirve el archivo.
    PDF: primera página como PNG (pdftoppm, cacheado). Otros: 404 JSON (se muestra icono)."""
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
        return send_file(fisica, as_attachment=False)
    if ext == 'pdf':
        png = _miniatura_pdf(fisica)
        if png:
            return send_file(png, mimetype='image/png')
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
    return jsonify({'success': True, 'message': 'Enviado a la papelera'})


# ── mover / copiar / renombrar ──────────────────────────────────────────
@bp_archivos.route('/archivos/mover', methods=['POST'])
def mover():
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
