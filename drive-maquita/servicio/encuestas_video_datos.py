# -*- coding: utf-8 -*-
"""Formularios del Almacén — datos que trae un video: cuándo, dónde y con qué se grabó (11/11/2026).

Sirve para los videos del teléfono y para los de DRON subidos desde el computador: se leen del
archivo (con ffprobe) la duración, el tamaño de imagen, la fecha y hora de grabación, la ubicación
y altitud de despegue si el equipo la guardó, y la marca y modelo. Si el archivo no trae un dato,
ese dato no aparece. Nunca se cree lo que diga el navegador aparte."""
import json
import re
import subprocess

EXTENSIONES = ('mp4', 'mov', 'm4v', '3gp', 'mkv', 'webm', 'avi')
_ISO6709 = re.compile(r'^([+-]\d+(?:\.\d+)?)([+-]\d+(?:\.\d+)?)([+-]\d+(?:\.\d+)?)?')
_UBICACION = ('location', 'location-eng', 'com.apple.quicktime.location.iso6709')
_MARCA = ('make', 'com.android.manufacturer', 'com.apple.quicktime.make')
_MODELO = ('model', 'com.android.model', 'com.apple.quicktime.model')


def _primero(etiquetas, claves):
    for clave in claves:
        if etiquetas.get(clave):
            return str(etiquetas[clave]).strip()[:80]
    return ''


def leer(camino):
    """{duracion, ancho, alto, cuadros, tomada, lat, lon, altitud, equipo} con lo que traiga el video, o None."""
    try:
        salida = subprocess.run(
            ['ffprobe', '-v', 'error', '-print_format', 'json', '-show_format', '-show_streams', camino],
            capture_output=True, timeout=20, check=True).stdout
        dato = json.loads(salida.decode('utf-8', 'replace'))
    except (OSError, ValueError, subprocess.SubprocessError):
        return None
    formato = dato.get('format') or {}
    video = next((s for s in dato.get('streams') or [] if s.get('codec_type') == 'video'), None)
    if not video:
        return None
    etiquetas = {str(k).lower(): v for k, v in (formato.get('tags') or {}).items()}
    datos = {}
    try:
        datos['duracion'] = int(round(float(formato.get('duration') or video.get('duration') or 0)))
        datos['ancho'], datos['alto'] = int(video['width']), int(video['height'])
        n, _, d = str(video.get('avg_frame_rate') or '').partition('/')
        if float(d or 0):
            datos['cuadros'] = round(float(n) / float(d), 1)
    except (KeyError, TypeError, ValueError):
        pass
    tomada = str(etiquetas.get('creation_time') or '')
    if len(tomada) >= 19 and not tomada.startswith('1970') and not tomada.startswith('1904'):
        datos['tomada'] = tomada[:19] + ('Z' if tomada.rstrip().endswith('Z') else '')
    donde = _ISO6709.match(_primero(etiquetas, _UBICACION))
    if donde:
        lat, lon = float(donde.group(1)), float(donde.group(2))
        if -90 <= lat <= 90 and -180 <= lon <= 180 and (lat or lon):
            datos['lat'], datos['lon'] = round(lat, 7), round(lon, 7)
            if donde.group(3):
                datos['altitud'] = round(float(donde.group(3)), 1)
    equipo = ' '.join(x for x in (_primero(etiquetas, _MARCA), _primero(etiquetas, _MODELO)) if x)
    if equipo:
        datos['equipo'] = equipo
    return datos or None
