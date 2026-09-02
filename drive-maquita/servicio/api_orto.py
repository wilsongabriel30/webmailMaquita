# -*- coding: utf-8 -*-
"""API Ortomosaico del Almacén Maquita — superponer el trabajo de drone en el mapa.
================================================================================
Los vuelos de drone (Metashape) exportan un ORTOMOSAICO georreferenciado (GeoTIFF).
Este módulo lee sus límites geográficos (WGS84) directamente de los tags GeoTIFF con
Pillow —SIN gdal— y sirve una versión REDUCIDA de la imagen para superponerla sobre
el mapa del visor (Leaflet imageOverlay). 100% local, sin dependencias externas.

Solo soporta GeoTIFF ya en WGS84/EPSG:4326 (que es como los exporta Metashape aquí);
si viniera en UTM haría falta reproyectar (no hay pyproj) y se devuelve un aviso.

Autoría: Equipo de Tecnología Maquita — 2026-08-14
"""
import hashlib
import io
import logging
import os
from urllib.parse import quote

from flask import Blueprint, Response, jsonify, request, send_file

from api_archivos import error, usuario_actual
from seguridad_rutas import RutaInvalida, normalizar_ruta_virtual, ruta_fisica

from PIL import Image
Image.MAX_IMAGE_PIXELS = None   # los ortomosaicos son enormes a propósito

log = logging.getLogger('almacen.orto')
bp_orto = Blueprint('almacen_orto', __name__)

CACHE_DIR = '/home/sistemas/almacen-maquita/cache/orto'
EXT_TIF = ('.tif', '.tiff')
EXT_IMG = ('.jpg', '.jpeg', '.png')
MAX_LADO_DEF = 2048
MAX_LADO_TOP = 4096


def _geokeys(gk):
    """Extrae (GTModelType, GeographicType, ProjectedCSType) del GeoKeyDirectory."""
    gk = list(gk)
    model_type = geo_type = proj_type = None
    for idx in range(4, len(gk) - 3, 4):
        key, loc, val = gk[idx], gk[idx + 1], gk[idx + 3]
        if loc != 0:
            continue  # solo claves con valor inline (no las que apuntan a otro tag)
        if key == 1024:
            model_type = val
        elif key == 2048:
            geo_type = val
        elif key == 3072:
            proj_type = val
    return model_type, geo_type, proj_type


def _bounds_geotiff(fisica):
    """Lee los límites geográficos (WGS84) de un GeoTIFF con Pillow. Si el ráster
    está en un CRS proyectado (UTM…), reproyecta las 4 esquinas con pyproj (local).
    Devuelve (bounds, aviso): bounds = [[sur,oeste],[norte,este]] o None; aviso =
    texto para el usuario cuando no se pudo (p. ej. falta pyproj)."""
    try:
        im = Image.open(fisica)
    except Exception:
        return None, None
    w, h = im.size
    t = getattr(im, 'tag_v2', None)
    if not t:
        return None, None
    escala = t.get(33550)     # ModelPixelScale (sx, sy, sz)
    tie = t.get(33922)        # ModelTiepoint (i, j, k, X, Y, Z)
    gk = t.get(34735)         # GeoKeyDirectory
    if not (escala and tie and gk):
        return None, None
    try:
        sx, sy = float(escala[0]), float(escala[1])
        i, j = float(tie[0]), float(tie[1])
        x0, y0 = float(tie[3]), float(tie[4])
    except (TypeError, IndexError, ValueError):
        return None, None
    if sx <= 0 or sy <= 0:
        return None, None

    # Esquinas en coordenadas NATIVAS del ráster (grados o metros según el CRS).
    def px(cx, cy):
        return (x0 + (cx - i) * sx, y0 - (cy - j) * sy)
    esquinas = [px(0, 0), px(w, 0), px(w, h), px(0, h)]

    model_type, geo_type, proj_type = _geokeys(gk)
    if model_type == 2 and geo_type in (4326, 4322, 4979, 0):
        xs = [c[0] for c in esquinas]
        ys = [c[1] for c in esquinas]
    elif model_type == 1 and proj_type:
        # CRS proyectado (UTM u otro): reproyectar a WGS84 con pyproj (local).
        try:
            from pyproj import Transformer
        except Exception:
            return None, ('El ortomosaico está en un sistema proyectado (EPSG:%s) y '
                          'falta pyproj para reproyectarlo.' % proj_type)
        try:
            tr = Transformer.from_crs('EPSG:%d' % int(proj_type), 'EPSG:4326',
                                      always_xy=True)
            pts = [tr.transform(x, y) for (x, y) in esquinas]
        except Exception as exc:
            log.warning('reproyeccion EPSG:%s: %s', proj_type, exc)
            return None, ('No se pudo reproyectar el ortomosaico (EPSG:%s).' % proj_type)
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
    else:
        return None, 'El ortomosaico no trae georreferencia reconocible.'

    s, n = min(ys), max(ys)
    o, e = min(xs), max(xs)
    if not (-90 <= s <= 90 and -90 <= n <= 90 and -180 <= o <= 180 and -180 <= e <= 180):
        return None, None
    return [[s, o], [n, e]], None


def _buscar_en_carpeta(usuario, ruta_virtual, exts):
    """Devuelve (ruta_virtual, fisica) del primer archivo con esas extensiones en la
    carpeta de `ruta_virtual`, priorizando nombres con 'ort' (ortomosaico)."""
    carpeta_virtual = ruta_virtual.rsplit('/', 1)[0] if '/' in ruta_virtual else ''
    try:
        fisica_carpeta = ruta_fisica(usuario, carpeta_virtual)
    except RutaInvalida:
        return None
    if not os.path.isdir(fisica_carpeta):
        return None
    candidatos = []
    for nombre in os.listdir(fisica_carpeta):
        low = nombre.lower()
        if low.endswith(exts):
            prioridad = 0 if ('ort' in low or 'orto' in low) else 1
            candidatos.append((prioridad, nombre))
    if not candidatos:
        return None
    candidatos.sort()
    elegido = candidatos[0][1]
    vv = (carpeta_virtual + '/' + elegido) if carpeta_virtual else ('/' + elegido)
    return (normalizar_ruta_virtual(vv), os.path.join(fisica_carpeta, elegido))


@bp_orto.route('/orto/info', methods=['GET'])
def orto_info():
    """GET /api/almacen/orto/info?ruta= — busca el ortomosaico (GeoTIFF) hermano del
    archivo/carpeta indicado, devuelve sus límites y la URL de la imagen reducida."""
    usuario = usuario_actual()
    try:
        ruta = normalizar_ruta_virtual(request.args.get('ruta', ''))
    except RutaInvalida as exc:
        return error(str(exc), 400)
    tif = _buscar_en_carpeta(usuario, ruta, EXT_TIF)
    if not tif:
        return jsonify({'success': False, 'error': 'No hay ortomosaico (GeoTIFF) en la carpeta'}), 404
    bounds, aviso = _bounds_geotiff(tif[1])
    if not bounds:
        return jsonify({'success': False,
                        'error': aviso or 'El ortomosaico no está georreferenciado'}), 422
    img = _buscar_en_carpeta(usuario, ruta, EXT_IMG)
    if not img:
        return jsonify({'success': False,
                        'error': 'No hay imagen (.jpg/.png) del ortomosaico para superponer'}), 404
    return jsonify({
        'success': True,
        'bounds': bounds,
        'img': '/api/almacen/orto/img?ruta=' + quote(img[0], safe=''),
        'nombre': img[0].rsplit('/', 1)[-1],
    })


@bp_orto.route('/orto/img', methods=['GET'])
def orto_img():
    """GET /api/almacen/orto/img?ruta=&max= — imagen reducida (JPEG) para overlay."""
    usuario = usuario_actual()
    try:
        ruta = normalizar_ruta_virtual(request.args.get('ruta', ''))
        fisica = ruta_fisica(usuario, ruta)
    except RutaInvalida as exc:
        return error(str(exc), 400)
    if not os.path.isfile(fisica):
        return error('Imagen no encontrada', 404)
    if not fisica.lower().endswith(EXT_IMG):
        return error('Formato no admitido', 400)
    try:
        lado = int(request.args.get('max', MAX_LADO_DEF))
    except ValueError:
        lado = MAX_LADO_DEF
    lado = max(512, min(MAX_LADO_TOP, lado))

    st = os.stat(fisica)
    clave = hashlib.sha1(('%s|%s|%s|%s' % (fisica, st.st_mtime_ns, st.st_size, lado))
                         .encode('utf-8')).hexdigest()
    destino = os.path.join(CACHE_DIR, clave + '.jpg')
    if os.path.isfile(destino) and os.path.getsize(destino) > 0:
        return send_file(destino, mimetype='image/jpeg', conditional=True, max_age=86400)

    try:
        im = Image.open(fisica)
        try:
            im.draft('RGB', (lado, lado))   # acelera muchísimo la decodificación JPEG
        except Exception:
            pass
        im = im.convert('RGB')
        im.thumbnail((lado, lado), Image.LANCZOS)
        buf = io.BytesIO()
        im.save(buf, 'JPEG', quality=82, optimize=True)
        datos = buf.getvalue()
    except Exception as exc:
        log.error('orto/img %s: %s', ruta, exc)
        return error('No se pudo generar la vista del ortomosaico', 500)

    try:
        os.makedirs(CACHE_DIR, exist_ok=True)
        tmp = destino + '.tmp'
        with open(tmp, 'wb') as f:
            f.write(datos)
        os.replace(tmp, destino)
    except Exception as exc:
        log.warning('orto cache %s: %s', ruta, exc)
    return Response(datos, mimetype='image/jpeg')
