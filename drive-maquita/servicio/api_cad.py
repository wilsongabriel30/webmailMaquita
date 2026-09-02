# -*- coding: utf-8 -*-
"""API CAD del Almacén Maquita — visor de planos AutoCAD (.dwg/.dxf).
================================================================
Convierte planos a SVG vectorial con un contenedor LibreDWG+ezdxf (VM131,
http://193.16.0.211:8790) y los muestra en el navegador con zoom/paneo. 100 %
libre, SIN licencias de AutoCAD. Es un VISOR (solo lectura).

El SVG se cachea por hash de contenido: la 2.ª apertura es instantánea y las
conversiones no se repiten (los planos terminados no cambian). El candado maestro
de /api/almacen* y /archivos-almacen* (integracion_faro) protege el acceso.

Autoría: Equipo de Tecnología Maquita — 2026-07-24
"""
import hashlib
import logging
import os
import re
import urllib.error
import urllib.request

from flask import Blueprint, Response, jsonify, request, send_file

from api_archivos import error, usuario_actual
from seguridad_rutas import RutaInvalida, normalizar_ruta_virtual, ruta_fisica

log = logging.getLogger('almacen.cad')

bp_cad = Blueprint('almacen_cad', __name__)
bp_cad_web = Blueprint('almacen_cad_web', __name__)

CONVERSOR_URL = os.environ.get('CAD_CONVERSOR_URL',
                               'http://193.16.0.211:8790/convert')
CACHE_DIR = '/home/sistemas/almacen-maquita/cache/cad'
EXT_CAD = {'dwg', 'dxf'}
MAX_BYTES = 200 * 1024 * 1024  # 200 MB

def _asegurar_render(svg):
    """LibreDWG a veces deja TODA la geometria dentro de <defs> (bloques 'raiz'
    del Model_Space que nunca se instancian) y el unico elemento de nivel superior
    es un *Paper_Space vacio -> el plano se ve EN BLANCO. Detecta ese caso e
    instancia las raices con <use> de nivel superior. Es idempotente y no toca los
    SVG que ya renderizan. Devuelve bytes (o el original si no aplica)."""
    try:
        txt = svg.decode('utf-8', 'replace') if isinstance(svg, (bytes, bytearray)) else svg
    except Exception:
        return svg
    d0 = txt.find('<defs>')
    d1 = txt.find('</defs>')
    cierre = txt.rfind('</svg>')
    if d0 < 0 or d1 < 0 or cierre < 0:
        return svg
    d1 += len('</defs>')
    fuera = txt[:d0] + txt[d1:]
    # Si ya hay algo dibujable de nivel superior, el plano se ve: no tocar.
    if re.search(r'<use\b', fuera) or re.search(
            r'<(path|circle|line|polyline|polygon|ellipse|text|rect|image)\b', fuera):
        return svg
    defs = txt[d0:d1]
    definidos = re.findall(r'<g id="(symbol-[0-9A-Fa-f]+)"', defs)
    referidos = set(re.findall(r'xlink:href="#(symbol-[0-9A-Fa-f]+)"', txt))
    top = set(re.findall(r'<g id="(symbol-[0-9A-Fa-f]+)"', txt[:d0]))
    raices = [d for d in definidos if d not in referidos and d not in top]
    if not raices:
        return svg
    usos = ''.join('<use xlink:href="#%s"/>' % r for r in raices)
    nuevo = txt[:cierre] + usos + txt[cierre:]
    return nuevo.encode('utf-8')



def _hash_archivo(fisica):
    h = hashlib.sha1()
    with open(fisica, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


@bp_cad.route('/cad/svg', methods=['GET'])
def cad_svg():
    """GET /api/almacen/cad/svg?ruta= — devuelve el plano renderizado a SVG."""
    usuario = usuario_actual()
    try:
        ruta = normalizar_ruta_virtual(request.args.get('ruta', ''))
        fisica = ruta_fisica(usuario, ruta)
    except RutaInvalida as excepcion:
        return error(str(excepcion), 400)
    if not os.path.isfile(fisica):
        return error('Archivo no encontrado', 404)
    ext = ruta.rsplit('.', 1)[-1].lower() if '.' in ruta else ''
    if ext not in EXT_CAD:
        return error('No es un plano CAD (.dwg/.dxf)', 400)
    tam = os.path.getsize(fisica)
    if tam == 0:
        return error('El plano está vacío', 400)
    if tam > MAX_BYTES:
        return error('Plano demasiado grande para previsualizar', 413)

    # Caché por hash de contenido (los planos terminados no cambian)
    try:
        clave = _hash_archivo(fisica)
    except Exception:
        clave = None
    cache_path = os.path.join(CACHE_DIR, clave + '.svg') if clave else None
    # reparar el SVG cacheado en sitio (planos viejos con render en blanco)
    if cache_path and os.path.isfile(cache_path) and os.path.getsize(cache_path) > 0:
        try:
            with open(cache_path, 'rb') as _f:
                _cont = _f.read()
            _fix = _asegurar_render(_cont)
            if _fix != _cont:
                _tmp = cache_path + '.tmp'
                with open(_tmp, 'wb') as _f:
                    _f.write(_fix)
                os.replace(_tmp, cache_path)
        except Exception:
            pass
        return send_file(cache_path, mimetype='image/svg+xml',
                         conditional=True, max_age=86400)

    # Convertir vía el contenedor LibreDWG (urllib: sin dependencias extra)
    try:
        with open(fisica, 'rb') as f:
            datos = f.read()
        req = urllib.request.Request(
            CONVERSOR_URL + '?type=' + ext, data=datos, method='POST',
            headers={'Content-Type': 'application/octet-stream'})
        with urllib.request.urlopen(req, timeout=120) as resp:   # 75s: falla rapido si el conversor se atasca (antes 300s = 5 min colgado)
            contenido = resp.read()
            estado = resp.status
    except urllib.error.HTTPError as excepcion:
        cuerpo = b''
        try:
            cuerpo = excepcion.read()
        except Exception:
            pass
        log.error('cad convert %s -> HTTP %s %s', ruta, excepcion.code,
                  cuerpo[:300])
        return error('No se pudo convertir el plano (código %s). '
                     'Puede ser una versión de DWG no soportada.' % excepcion.code,
                     502)
    except Exception as excepcion:
        log.error('cad conversor %s: %s', ruta, excepcion)
        return error('El servicio de conversión CAD no responde', 502)

    if estado != 200 or not contenido:
        return error('No se pudo convertir el plano', 502)

    # Reparar planos que salen 'en blanco' (geometria atrapada en <defs>).
    contenido = _asegurar_render(contenido)

    # Guardar en caché (escritura atómica)
    if cache_path:
        try:
            os.makedirs(CACHE_DIR, exist_ok=True)
            tmp = cache_path + '.tmp'
            with open(tmp, 'wb') as f:
                f.write(contenido)
            os.replace(tmp, cache_path)
        except Exception as excepcion:
            log.warning('cad cache %s: %s', ruta, excepcion)
    return Response(contenido, mimetype='image/svg+xml')


@bp_cad_web.route('/archivos-almacen/plano')
def visor_plano():
    """Página del visor de planos CAD. La ruta del .dwg/.dxf viaja en ?ruta=.
    Protegida por el candado maestro de /archivos-almacen*."""
    plantilla = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                             'plantillas', 'visor_cad.html')
    _r = send_file(plantilla, mimetype='text/html')
    _r.headers['Permissions-Policy'] = 'unload=*'
    return _r
