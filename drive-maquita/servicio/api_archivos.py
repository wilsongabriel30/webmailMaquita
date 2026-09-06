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
import protecciones_sistema as _prot
from registro import registrar_actividad
from seguridad_rutas import (RutaInvalida, normalizar_ruta_virtual,
                             ruta_fisica, unidad_de_ruta)

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
    """¿Tiene el usuario acceso a esta ruta? Cubre los tres espacios:
    «Mi unidad» (siempre suyo), las unidades compartidas y lo que otra persona
    le compartió a él (/compartido/<dueño>/…). Rutas personales: siempre True."""
    try:
        from permisos_compartidos import permiso_compartido
        veredicto = permiso_compartido(usuario, ruta, escritura)
        if veredicto is not None:
            return veredicto
        from api_unidades import permiso_unidad
        return permiso_unidad(usuario, ruta, escritura)
    except Exception:
        # Un fallo al comprobar el permiso NO puede conceder acceso: falla cerrado.
        return False


def _efectivo(usuario, ruta):
    """(usuario, ruta) con los que hay que llamar al núcleo. En el espacio
    «Compartido conmigo» el trabajo se hace en el espacio del DUEÑO: así su
    índice de búsqueda, sus versiones, su papelera y su cuota siguen siendo los
    suyos, que es de quien es el contenido. El permiso ya se validó antes."""
    try:
        from permisos_compartidos import resolver
        return resolver(usuario, ruta)
    except Exception:
        return usuario, ruta


def _prefijo(ruta):
    """Prefijo del espacio compartido de esta ruta ('' si es una ruta normal)."""
    try:
        from permisos_compartidos import prefijo_de
        return prefijo_de(ruta)
    except Exception:
        return ''


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
        _prefijo_comp = _prefijo(ruta)
        usuario_efectivo, ruta_efectiva = _efectivo(usuario, ruta)
        carpetas, archivos = nucleo.listar(usuario_efectivo, ruta_efectiva)
        if _prefijo_comp:
            from vista_compartidos import reprefijar
            reprefijar(carpetas, _prefijo_comp)
            reprefijar(archivos, _prefijo_comp)
    except RutaInvalida as excepcion:
        return error(str(excepcion), excepcion.codigo)
    except FileNotFoundError:
        return error('Carpeta no encontrada', 404)

    # Orden pedido por el explorador (12/08/2026): antes el parametro se
    # IGNORABA y todo salia por nombre. fecha_mia/abierta usan la actividad
    # del propio usuario (que subio/edito o abrio) con la fecha de
    # modificacion como respaldo. FAIL-SILENT: si algo falla, orden natural.
    orden = (request.args.get('orden') or 'nombre').strip()
    inverso = ((request.args.get('dir') or 'asc').strip() == 'desc')
    try:
        from almacen_bd import consultar as _consultar
        clave = None
        if orden in ('fecha_mia', 'abierta'):
            acciones = ['apertura', 'abrio'] if orden == 'abierta' else                        ['subio', 'edito', 'renombro', 'movio', 'creo_carpeta', 'copio']
            filas_act = _consultar(
                'SELECT ruta, MAX(creado_en) AS f FROM actividad '
                'WHERE usuario_id = %s AND accion = ANY(%s) AND ruta LIKE %s '
                'GROUP BY ruta',
                (usuario, acciones, (ruta.rstrip('/') or '') + '/%'))
            mio = {f['ruta']: f['f'].isoformat() for f in filas_act}
            clave = lambda i: (mio.get(i.get('ruta') or i.get('ruta_completa') or '')
                               or i.get('modificado_at') or '')
        elif orden == 'fecha':
            clave = lambda i: i.get('modificado_at') or ''
        elif orden == 'tamano':
            clave = lambda i: float(i.get('tamano_bytes') or i.get('tamano') or 0)
        if clave is not None:
            carpetas.sort(key=clave, reverse=inverso)
            archivos.sort(key=clave, reverse=inverso)
        elif inverso:
            carpetas.reverse()
            archivos.reverse()
    except Exception as excepcion:
        log.debug('Orden %s no aplicado: %s', orden, excepcion)

    # Migas de pan (breadcrumb).
    # La PRIMERA miga es siempre la raiz, como en Drive: sin ella, entrar en una
    # carpeta de primer nivel dejaba una sola miga, la interfaz lo tomaba por la
    # raiz y no mostraba la ruta; y ademas no habia manera de volver arriba
    # pulsando el camino.
    # En una unidad compartida la raiz es la propia unidad, no «Mi unidad»:
    # decir «Mi unidad» dentro de una unidad de equipo seria mentir sobre donde
    # esta la persona.
    unidad_id, _sub = unidad_de_ruta(ruta)
    if _prefijo_comp:
        # Dentro de lo que otra persona compartió, la primera miga es
        # «Compartido conmigo»: decir «Mi unidad» sería mentir sobre dónde está.
        from vista_compartidos import migas as _migas_compartido
        migas = _migas_compartido(_prefijo_comp, ruta_efectiva, '')
        partes = []
        acumulada = ''
    elif unidad_id is None:
        migas = [{'nombre': 'Mi unidad', 'ruta': '/'}]
        partes = [p for p in ruta.split('/') if p]
        acumulada = ''
    else:
        migas = []
        partes = [p for p in ruta.split('/') if p]
        acumulada = ''

    for parte in partes:
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


# ── auxiliar de subir ─────────────────────────────────────────────────────
# CUIDADO AL EDITAR: esta función va ANTES del decorador de `subir()`, no
# entre medio. El 29/07/2026 quedó insertada justo debajo de
# `@bp_archivos.route('/archivos', methods=['POST'])` y se quedó con la ruta:
# Flask registró ESTA función como manejador del POST y `subir()` dejó de
# tener ruta. Toda subida devolvía 500 con
#   TypeError: _refrescar_vinculos_del_origen() missing 2 required
#   positional arguments: 'usuario' and 'ruta'
# En Python un decorador se aplica SIEMPRE a la primera función que le sigue.
def _refrescar_vinculos_del_origen(usuario, ruta):
    """Actualiza los destinos que toman datos de `ruta`. Best-effort absoluto:
    una subida NUNCA debe fallar porque un vínculo no se pudiera refrescar."""
    try:
        from api_vinculos import refrescar_por_origen, EXT_EXCEL
        extension = ruta.rsplit('.', 1)[-1].lower() if '.' in ruta else ''
        if extension in EXT_EXCEL:
            refrescar_por_origen(usuario, ruta)
    except Exception as excepcion:
        log.warning('Refresco de vínculos tras subir %s: %s', ruta, excepcion)


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
        # Se registra el detalle: un 400 mudo en el registro de nginx no dice
        # nada, y sin saber que llego de verdad no se puede arreglar nada.
        log.warning('Subida sin archivo | carpeta=%r | campos=%r | archivos=%r '
                    '| tipo=%r | tamano=%r',
                    carpeta, list(request.form.keys()),
                    list(request.files.keys()),
                    request.content_type, request.content_length)
        return error('No se recibió ningún archivo', 400)
    subidos = []
    try:
        for almacenado in archivos:
            # Al subir una CARPETA, Chrome manda como nombre del archivo la
            # ruta relativa entera («01 Doc. Vigente/.../DOF.FOR.001.xlsx»)
            # porque el File trae `webkitRelativePath`. El motor rechaza
            # cualquier nombre con barras --y hace bien, es su defensa contra
            # rutas fabricadas--, asi que la subida moria con «Nombre de
            # archivo invalido».
            # Aqui se toma solo el nombre. Es seguro: la carpeta de destino
            # llega aparte, en su propio campo, y ya viene validada; de la ruta
            # que venga pegada al nombre no se hace ningun caso.
            nombre = (almacenado.filename or '').replace('\\', '/').split('/')[-1].strip()
            _usuario_ef, _carpeta_ef = _efectivo(usuario, carpeta)
            r = nucleo.subir(_usuario_ef, _carpeta_ef, nombre, almacenado.stream)
            _pref = _prefijo(carpeta)
            if _pref:
                from vista_compartidos import reprefijar_item
                reprefijar_item(r, _pref)
            subidos.append(r)
            registrar_actividad(usuario, 'subio', r['ruta'], r.get('tamano_humano', ''))
            # Si el archivo subido es ORIGEN de vínculos de datos, sus destinos
            # deben actualizarse. Hasta ahora el refresco SOLO se disparaba al
            # guardar desde OnlyOffice (api_onlyoffice.py, callback), así que
            # subir una versión nueva del origen dejaba los destinos con datos
            # viejos y sin ningún aviso.
            #
            # Se engancha aquí, en el endpoint de subida del usuario, y NO
            # dentro de nucleo.subir(): el propio motor de vínculos usa
            # nucleo.subir() para escribir el destino (api_vinculos.py:141), y
            # engancharlo ahí se realimentaría.
            _refrescar_vinculos_del_origen(usuario, r['ruta'])
    except RutaInvalida as excepcion:
        log.warning('Subida rechazada | carpeta=%r | nombres=%r | motivo=%s',
                    carpeta, [a.filename for a in archivos], excepcion)
        return error(str(excepcion), 400)
    except Exception as excepcion:
        # Cualquier otro fallo tambien deja rastro con el nombre del archivo:
        # antes se perdia en un 500 generico y no habia forma de saber cual
        # de los archivos de una tanda fue el que reviento.
        log.exception('Subida fallida | carpeta=%r | nombres=%r',
                      carpeta, [a.filename for a in archivos])
        raise
    return jsonify({'success': True, 'archivos': subidos,
                    'total': len(subidos)}), 201


# ── descargar ────────────────────────────────────────────────────────────
@bp_archivos.route('/archivos/descargar', methods=['GET'])
def descargar():
    """GET /archivos/descargar?ruta= — entrega el archivo.
    NOTA producción: detrás de nginx se cambia send_file por X-Accel-Redirect
    (los bytes los sirve nginx directo del disco, zero-copy)."""
    usuario = usuario_actual()
    _ruta_pedida = request.args.get('ruta', '')
    if not _permiso_unidad(usuario, _ruta_pedida, escritura=False):
        return error('No tienes acceso a esta unidad compartida', 403)
    try:
        _usuario_ef, _ruta_ef = _efectivo(usuario, _ruta_pedida)
        fisica = ruta_fisica(_usuario_ef, _ruta_ef)
    except RutaInvalida as excepcion:
        return error(str(excepcion), excepcion.codigo)
    if not os.path.isfile(fisica):
        return error('Archivo no encontrado', 404)

    # (2026-08-13) Entrega por nginx (X-Accel-Redirect): tras validar sesión y
    # permisos, nginx sirve los bytes DIRECTO del NFS (location interna
    # /almacen-datos-interno/ en faro-maquita.conf) con Range nativo — clave
    # para <audio>/<video> (arranque y seek instantáneos) y cero bloqueo del
    # event loop. Se pide con ?accel=1 (visor de medios) o la cabecera
    # X-Almacen-Accel: 1. SOLO tipos de MEDIOS (lista blanca): un HTML/SVG
    # inline en este origen sería XSS almacenado (regla anti-XSS de hoy);
    # cualquier otro tipo sigue el camino send_file con descarga forzada.
    # La rama anterior calculaba la ruta con dirname()x3 (rota a profundidad
    # variable) y la location de nginx no existía: estaba muerta.
    quiere_accel = (request.args.get('accel') == '1'
                    or request.headers.get('X-Almacen-Accel') == '1')
    if quiere_accel:
        from config_almacen import raiz_datos
        ext = os.path.splitext(fisica)[1].lstrip('.').lower()
        rel = os.path.relpath(fisica, raiz_datos())
        if ext in _EXT_MEDIOS_ACCEL and not rel.startswith('..'):
            from urllib.parse import quote
            import mimetypes
            respuesta = jsonify({'success': True})
            respuesta.headers['X-Accel-Redirect'] = '/almacen-datos-interno/' + quote(rel)
            mime = mimetypes.guess_type(fisica)[0]
            if mime:
                respuesta.headers['Content-Type'] = mime
            respuesta.headers['Content-Disposition'] = 'inline'
            respuesta.headers['X-Content-Type-Options'] = 'nosniff'
            return respuesta
        # tipo no-medio o raíz distinta a la del alias de nginx: camino normal
    return send_file(fisica, as_attachment=True,
                     download_name=os.path.basename(fisica))


# ── eliminar (papelera) ──────────────────────────────────────────────────
@bp_archivos.route('/archivos/ver', methods=['GET'])
def ver():
    """GET /archivos/ver?ruta= — entrega el archivo INLINE (para previsualizar en el navegador)."""
    usuario = usuario_actual()
    _ruta_pedida = request.args.get('ruta', '')
    if not _permiso_unidad(usuario, _ruta_pedida, escritura=False):
        return error('No tienes acceso a esta unidad compartida', 403)
    try:
        _usuario_ef, _ruta_ef = _efectivo(usuario, _ruta_pedida)
        fisica = ruta_fisica(_usuario_ef, _ruta_ef)
    except RutaInvalida as excepcion:
        return error(str(excepcion), excepcion.codigo)
    if not os.path.isfile(fisica):
        return error('Archivo no encontrado', 404)
    return _entrega_inline_segura(fisica)


_EXT_IMAGEN = {'jpg', 'jpeg', 'png', 'gif', 'webp', 'bmp', 'svg'}

# Medios que se entregan inline via X-Accel (?accel=1 en descargar): solo
# audio/video — tipos que el navegador REPRODUCE, nunca ejecuta.
_EXT_MEDIOS_ACCEL = {'mp3', 'm4a', 'aac', 'flac', 'wav', 'ogg', 'oga', 'opus',
                     'mp4', 'm4v', 'webm', 'ogv', 'mov', 'mkv', 'avi', '3gp'}

# Tipos "activos": el navegador ejecutaria su contenido si se sirven inline
# (XSS almacenado). Se entregan SIEMPRE como descarga y con tipo neutro.
_EXT_ACTIVAS = {'html', 'htm', 'xhtml', 'xht', 'shtml', 'svg', 'svgz',
                'xml', 'xsl', 'xslt', 'mml', 'js', 'mjs', 'htc'}


def _entrega_inline_segura(fisica):
    """Entrega un archivo para previsualizar en el navegador. Los tipos activos
    (HTML/SVG/XML/JS) se fuerzan a descarga con tipo neutro y 'nosniff', para
    que el navegador nunca los ejecute en el origen del Drive."""
    ext = os.path.splitext(fisica)[1].lstrip('.').lower()
    es_activo = ext in _EXT_ACTIVAS
    resp = send_file(fisica, as_attachment=es_activo,
                     download_name=os.path.basename(fisica))
    resp.headers['X-Content-Type-Options'] = 'nosniff'
    if es_activo:
        resp.headers['Content-Type'] = 'application/octet-stream'
    return resp


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


def _en_hilo_nativo(funcion, *args):
    """(2026-08-13) Ejecuta trabajo de NFS/CPU en un hilo nativo (eventlet.tpool)
    para no congelar el event loop del worker; fuera de eventlet llama directo.
    SOLO para funciones sin sockets ni subprocess (esos deben quedarse en el hub:
    bajo monkey_patch son verdes y no son seguros desde un hilo nativo)."""
    try:
        from eventlet import patcher as _patcher, tpool as _tpool
        if _patcher.is_monkey_patched('socket'):
            return _tpool.execute(funcion, *args)
    except ImportError:
        pass
    return funcion(*args)


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
    except RutaInvalida as excepcion:
        return error(str(excepcion), excepcion.codigo)
    # (2026-08-13) stat sobre NFS fuera del event loop (un NFS con hipo aquí
    # congelaba el worker entero; mismo patrón que nucleo_archivos.listar)
    if not _en_hilo_nativo(os.path.isfile, fisica):
        return error('Sin vista previa', 404)
    ext = os.path.splitext(fisica)[1].lstrip('.').lower()
    if ext in _EXT_IMAGEN:
        if ext == 'svg':
            _r = _respuesta_preview(fisica, 'image/svg+xml')
            _r.headers['Content-Security-Policy'] = "default-src 'none'; style-src 'unsafe-inline'; sandbox"
            _r.headers['X-Content-Type-Options'] = 'nosniff'
            return _r
        try:
            _lado = max(200, min(int(request.args.get('lado', 400)), 2000))
        except (TypeError, ValueError):
            _lado = 400
        png = _en_hilo_nativo(_miniatura_imagen, fisica, _lado)
        if png:
            return _respuesta_preview(png, 'image/jpeg')
        return send_file(fisica, as_attachment=False)
    if ext == 'pdf':
        png = _miniatura_pdf(fisica)
        if png:
            return _respuesta_preview(png)
    if ext == 'drawio':
        # Vista simplificada dibujada del propio XML (12/08/2026): nada externo.
        try:
            from miniatura_drawio import svg_de_drawio
            svg = svg_de_drawio(fisica)
            if svg:
                from flask import Response
                r = Response(svg, mimetype='image/svg+xml')
                r.headers['Cache-Control'] = 'private, max-age=300'
                r.headers['Content-Security-Policy'] = "default-src 'none'; style-src 'unsafe-inline'; sandbox"
                r.headers['X-Content-Type-Options'] = 'nosniff'
                return r
        except Exception:
            pass
        return error('Sin vista previa', 404)
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
    if not _permiso_unidad(usuario, datos.get('carpeta', '/'), escritura=True):
        return error('No tienes acceso de escritura a esta unidad compartida', 403)
    try:
        r = nucleo.crear_acceso_directo(usuario, datos.get('carpeta', '/'),
                                        datos['destino'], datos.get('nombre'))
    except RutaInvalida as e:
        return error(str(e), e.codigo)
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


@bp_archivos.route('/sugeridos', methods=['GET'])
def sugeridos():
    """GET /sugeridos?limit=&offset= — archivos recientes presentados como
    'Sugeridos' (Página principal y banda de Acceso rápido, estilo Drive).
    Reutiliza el motor de 'recientes' y añade un 'motivo' visible por item."""
    usuario = usuario_actual()
    try:
        limite = max(1, min(int(request.args.get('limit', 10)), 50))
    except (TypeError, ValueError):
        limite = 10
    try:
        offset = max(0, int(request.args.get('offset', 0)))
    except (TypeError, ValueError):
        offset = 0

    # 'recientes' ya devuelve ordenado por modificación (más reciente primero).
    # Tolerante a fallos: si el recorrido es lento/falla (NFS, usuarios enormes),
    # devolver vacío en vez de 500 -> la página principal nunca se rompe.
    try:
        todos = nucleo.recientes(usuario, offset + limite + 1)
    except Exception as _exc:
        log.warning('sugeridos: recientes falló para %s: %s', usuario, _exc)
        return jsonify({'success': True, 'sugeridos': [], 'hay_mas': False, 'total': 0})
    ventana = todos[offset:offset + limite]
    hay_mas = len(todos) > offset + limite

    for it in ventana:
        if not it.get('motivo'):
            it['motivo'] = 'Lo editaste recientemente'

    return jsonify({'success': True, 'sugeridos': ventana,
                    'hay_mas': hay_mas, 'total': len(ventana)})


@bp_archivos.route('/archivos', methods=['DELETE'])
@bp_archivos.route('/archivos/eliminar', methods=['POST'])
def eliminar():
    """DELETE /archivos?ruta= — mueve a la papelera (recuperable)."""
    usuario = usuario_actual()
    ruta = request.args.get('ruta') or (request.get_json(silent=True) or {}).get('ruta')
    if not ruta:
        return error('Ruta requerida', 400)
    if _prot.es_carpeta_chat(ruta):
        return _prot.error_carpeta_chat('eliminar')
    if _prot.es_de_correo(ruta):
        return _prot.error_pertenece_al_correo(usuario, ruta)
    if not _permiso_unidad(usuario, ruta, escritura=True):
        return error('No tienes permiso para borrar en esta unidad', 403)
    try:
        _usuario_ef, _ruta_ef = _efectivo(usuario, ruta)
        papelera_id = nucleo.enviar_a_papelera(_usuario_ef, _ruta_ef)
    except RutaInvalida as excepcion:
        return error(str(excepcion), excepcion.codigo)
    except FileNotFoundError:
        return error('No existe el elemento', 404)
    registrar_actividad(usuario, 'elimino', ruta)
    # `papelera_id` es lo que necesita /papelera/restaurar para deshacerlo.
    # Sin el, el navegador solo puede decir "borrado" y quedarse tan ancho.
    # T-18: si es un archivo del chat, avisar al chat (se oculta para este usuario hasta que lo restaure)
    try:
        from hook_chat import avisar_chat, es_de_chat
        avisar_chat(usuario, ruta, 'papelera')
        if es_de_chat(ruta):
            return jsonify({'success': True, 'message': 'Enviado a la papelera', 'papelera_id': papelera_id,
                            'aviso': 'Este archivo también dejará de verse en tu chat. Si lo restauras desde la papelera, vuelve a aparecer.'})
    except Exception:
        pass
    return jsonify({'success': True, 'message': 'Enviado a la papelera',
                    'papelera_id': papelera_id})


# ── mover / copiar / renombrar ──────────────────────────────────────────
@bp_archivos.route('/archivos/mover', methods=['POST'])
def mover():
    """POST /archivos/mover — {origen, destino}."""
    usuario = usuario_actual()
    datos = request.get_json() or {}
    if not datos.get('origen') or not datos.get('destino'):
        return error('origen y destino son requeridos', 400)
    if _prot.es_carpeta_chat(datos['origen']):
        return _prot.error_carpeta_chat('mover')
    if _prot.es_de_correo(datos['origen']) or _prot.es_de_correo(datos['destino']):
        return _prot.error_carpeta_correo('mover')
    # Unidades compartidas: mover exige EDICIÓN en el origen y en el destino
    # (hueco anotado en la auditoría del 28/07, cerrado el 12/08/2026).
    if (not _permiso_unidad(usuario, datos['origen'], escritura=True)
            or not _permiso_unidad(usuario, datos['destino'], escritura=True)):
        return error('No tienes permiso para mover aquí', 403)
    # Y ademas, dentro de una unidad compartida mover es cosa de sus
    # ADMINISTRADORES (31/08/2026, ver permisos_mover.py): un editor crea,
    # sube y edita, pero no reorganiza la unidad de los demas. Se exige en el
    # origen Y en el destino: sacar algo de una unidad es tan estructural como
    # meterlo.
    from permisos_mover import puede_mover, error_no_puede_mover
    if (not puede_mover(usuario, datos['origen'])
            or not puede_mover(usuario, datos['destino'])):
        return error(error_no_puede_mover(), 403)
    try:
        _usuario_ef, _origen_ef = _efectivo(usuario, datos['origen'])
        _usuario_dest, _destino_ef = _efectivo(usuario, datos['destino'])
        if _usuario_ef != _usuario_dest:
            # Mover entre dos espacios distintos sería sacar el archivo del
            # disco de su dueño: eso es copiar, no mover.
            return error('Para llevarlo a otro espacio, cópialo', 400)
        _final_ef = nucleo.mover(
            _usuario_ef, _origen_ef, _destino_ef,
            sobrescribir=bool(datos.get('sobrescribir')),
            conservar_ambos=bool(datos.get('conservar_ambos')))
    except nucleo.DestinoOcupado as choque:
        return jsonify({'success': False, 'conflicto': True,
                        'error': str(choque), 'ruta': choque.ruta}), 409
    except RutaInvalida as excepcion:
        return error(str(excepcion), excepcion.codigo)
    except FileNotFoundError:
        try:  # LOG TEMPORAL para diagnosticar el error al mover
            from seguridad_rutas import unidad_de_ruta as _udr, ruta_fisica as _rf
            import os as _os
            _o = datos.get('origen'); _d = datos.get('destino')
            _fo = _rf(usuario, _o)
            log.warning('MOVER-404 usuario=%s origen=%r unidad_o=%s fisico_o=%r existe=%s | destino=%r',
                        usuario, _o, _udr(_o), _fo, _os.path.exists(_fo), _d)
        except Exception as _e:
            log.warning('MOVER-404 usuario=%s origen=%r destino=%r (log fallo: %s)',
                        usuario, datos.get('origen'), datos.get('destino'), _e)
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
    # Unidades compartidas: copiar exige LECTURA en el origen y EDICIÓN en el
    # destino (12/08/2026).
    if (not _permiso_unidad(usuario, datos['origen'], escritura=False)
            or not _permiso_unidad(usuario, datos['destino'], escritura=True)):
        return error('No tienes permiso para copiar aquí', 403)
    try:
        _usuario_org, _origen_ef = _efectivo(usuario, datos['origen'])
        _usuario_dst, _destino_ef = _efectivo(usuario, datos['destino'])
        if _usuario_org == _usuario_dst:
            nucleo.copiar(_usuario_org, _origen_ef, _destino_ef)
        else:
            # Copia entre espacios (por ejemplo, de lo compartido a Mi unidad):
            # se lee del origen y se escribe en el destino con sus dueños.
            from copia_entre_espacios import copiar_entre_espacios
            copiar_entre_espacios(_usuario_org, _origen_ef,
                                  _usuario_dst, _destino_ef)
    except RutaInvalida as excepcion:
        return error(str(excepcion), excepcion.codigo)
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
    if _prot.es_carpeta_chat(datos['ruta']):
        return _prot.error_carpeta_chat('renombrar')
    if _prot.es_de_correo(datos['ruta']):
        return _prot.error_carpeta_correo('renombrar')
    if not _permiso_unidad(usuario, datos['ruta'], escritura=True):
        return error('No tienes permiso para renombrar aquí', 403)
    try:
        _usuario_ef, _ruta_ef = _efectivo(usuario, datos['ruta'])
        ruta_nueva = nucleo.renombrar(
            _usuario_ef, _ruta_ef, datos['nuevo_nombre'],
            sobrescribir=bool(datos.get('sobrescribir')),
            conservar_ambos=bool(datos.get('conservar_ambos')))
        _pref = _prefijo(datos['ruta'])
        if _pref:
            ruta_nueva = _pref + ruta_nueva
    except nucleo.DestinoOcupado as choque:
        # 409 = «ya hay algo con ese nombre». El explorador lo distingue de un
        # error de verdad y pregunta antes de pisar nada.
        return jsonify({'success': False, 'conflicto': True,
                        'error': str(choque), 'ruta': choque.ruta}), 409
    except RutaInvalida as excepcion:
        return error(str(excepcion), excepcion.codigo)
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
        _usuario_ef, _ruta_ef = _efectivo(usuario, datos.get('ruta', '/'))
        carpeta = nucleo.crear_carpeta(_usuario_ef, _ruta_ef, datos['nombre'])
        _pref = _prefijo(datos.get('ruta', '/'))
        if _pref:
            from vista_compartidos import reprefijar_item
            reprefijar_item(carpeta, _pref)
    except RutaInvalida as excepcion:
        return error(str(excepcion), excepcion.codigo)
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


@bp_archivos.route('/almacenamiento', methods=['GET'])
def almacenamiento():
    """GET /almacenamiento?limit= - archivos de la unidad ordenados por tamano
    (mayor primero), para la vista 'Almacenamiento' estilo Drive."""
    usuario = usuario_actual()
    try:
        limite = max(1, min(int(request.args.get('limit', 200)), 500))
    except (TypeError, ValueError):
        limite = 200
    items = nucleo.por_tamano(usuario, limite)
    return jsonify({'success': True, 'archivos': items, 'total': len(items)})


@bp_archivos.route('/cuota', methods=['GET'])
def cuota():
    """GET /cuota — uso y límite de almacenamiento."""
    usuario = usuario_actual()
    datos = nucleo.cuota(usuario)
    datos['success'] = True
    return jsonify(datos)
