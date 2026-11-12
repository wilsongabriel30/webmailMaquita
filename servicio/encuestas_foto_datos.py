# -*- coding: utf-8 -*-
"""Formularios del Almacén — datos que trae una foto: dónde y cuándo se tomó (11/11/2026).

La app Maquita Datos de Campo sella cada foto (EXIF) con la ubicación del teléfono, la altitud,
la precisión y la fecha y hora. Aquí se leen del archivo recibido y se anotan en su ficha
(`datos`), para que viajen con la respuesta y se vean junto a la foto.

Se lee del archivo, no de lo que diga el teléfono aparte. Si la foto no trae datos, no pasa nada."""
import json
import logging
import os

import encuestas_archivos as archivos

log = logging.getLogger(__name__)
_GPS = 0x8825
_EXIF = 0x8769


def _grados(valor, ref):
    g, m, s = (float(x) for x in valor)
    n = g + m / 60 + s / 3600
    return -n if str(ref).strip().upper() in ('S', 'W') else n


def leer(camino):
    """{lat, lon, altitud, precision, tomada} con lo que traiga la foto, o None."""
    try:
        from PIL import Image
        with Image.open(camino) as imagen:
            exif = imagen.getexif()
            gps = exif.get_ifd(_GPS) or {}
            propio = exif.get_ifd(_EXIF) or {}
            general = dict(exif)
    except Exception:
        return None
    datos = {}
    try:
        lat, lon = _grados(gps[2], gps.get(1, 'N')), _grados(gps[4], gps.get(3, 'E'))
        if -90 <= lat <= 90 and -180 <= lon <= 180 and (lat or lon):
            datos['lat'], datos['lon'] = round(lat, 7), round(lon, 7)
            if 6 in gps:
                altitud = float(gps[6])
                datos['altitud'] = round(-altitud if gps.get(5) in (1, b'\x01') else altitud, 1)
            if 31 in gps:
                datos['precision'] = round(float(gps[31]), 1)
    except (KeyError, TypeError, ValueError, ZeroDivisionError):
        pass
    tomada = propio.get(0x9003) or general.get(0x0132)
    if isinstance(tomada, str) and len(tomada) >= 19:
        datos['tomada'] = tomada[:10].replace(':', '-') + 'T' + tomada[11:19] + str(propio.get(0x9011) or '')[:6]
    return datos or None


def anotar(encuesta_id, ficha):
    """Añade `datos` a la ficha de una foto pendiente (también en disco). Devuelve la ficha."""
    if not isinstance(ficha, dict) or archivos.extension_de(ficha.get('nombre', '')) not in ('jpg', 'jpeg'):
        return ficha
    camino = archivos.camino_pendiente(encuesta_id, ficha.get('id'))
    datos = leer(camino) if camino else None
    if not datos:
        return ficha
    ficha = dict(ficha, datos=datos)
    try:
        with open(os.path.splitext(camino)[0] + '.json', 'w', encoding='utf-8') as salida:
            json.dump(ficha, salida, ensure_ascii=False)
    except OSError as e:
        log.warning('No se pudieron anotar los datos de la foto %s: %s', ficha.get('id'), e)
    return ficha
