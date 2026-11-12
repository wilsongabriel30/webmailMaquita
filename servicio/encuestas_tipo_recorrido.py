# -*- coding: utf-8 -*-
"""Formularios del Almacén — pregunta «Video con recorrido» y «Solo recorrido» (11/11/2026).

Se responde SOLO desde la app Maquita Datos de Campo: el teléfono graba el camino con el GPS
(y, si la pregunta lo pide, un video de hasta 5 minutos al mismo tiempo) y sube dos archivos:

  · el recorrido, un GeoJSON (LineString) con la hora y la precisión de cada punto;
  · el video (.mp4), por partes y reanudable, porque en el campo la señal se corta.

Los dos llegan como adjuntos pendientes (`encuestas_archivos.py`) y, al aceptar la respuesta,
pasan al Drive del dueño. La respuesta guarda sus fichas y un resumen (puntos, metros, duración)
calculado AQUÍ con el archivo recibido: lo que diga el teléfono no cuenta.

Sirve a cualquier encuesta del Drive (Agro, Social y Cooperación u otra área)."""
import json
import math

import encuestas_archivos as archivos

MINUTOS_MAX = 5
VIDEO_MB = 100
RECORRIDO_MB = 5
PUNTOS_MAX = 50000


def completar(pregunta, bruto):
    pregunta['recorrido_video'] = bool(bruto.get('recorrido_video', True))
    try:
        minutos = int(bruto.get('recorrido_minutos') or MINUTOS_MAX)
    except (TypeError, ValueError):
        minutos = MINUTOS_MAX
    pregunta['recorrido_minutos'] = min(max(minutos, 1), MINUTOS_MAX)
    return pregunta


def _metros(a, b):
    """Distancia entre dos puntos [lon, lat] (haversine)."""
    lat1, lat2 = math.radians(a[1]), math.radians(b[1])
    dlat, dlon = lat2 - lat1, math.radians(b[0] - a[0])
    h = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return 2 * 6371000 * math.asin(min(1, math.sqrt(h)))


def area(puntos):
    """(metros cuadrados, perímetro) si el camino se cierra sobre sí mismo (vuelve cerca del inicio); si no, None.

    Sirve para medir un lote caminando su lindero. «Cerca» = a menos de 15 m o del 10 % de lo caminado."""
    if len(puntos) < 4:
        return None
    largo = sum(_metros(puntos[i - 1], puntos[i]) for i in range(1, len(puntos)))
    cierre = _metros(puntos[-1], puntos[0])
    if cierre > max(15.0, largo * 0.10):
        return None
    lat0 = math.radians(puntos[0][1])
    plano = [(math.radians(p[0] - puntos[0][0]) * 6371000 * math.cos(lat0), math.radians(p[1] - puntos[0][1]) * 6371000) for p in puntos]
    doble = sum(plano[i][0] * plano[(i + 1) % len(plano)][1] - plano[(i + 1) % len(plano)][0] * plano[i][1] for i in range(len(plano)))
    return abs(doble) / 2, largo + cierre


def tipo_para_ver(camino, nombre):
    """Tipo con que se puede mostrar en el visor (no solo bajar) un archivo de recorrido, o None.

    Solo un video MP4 de verdad o un camino GeoJSON válido: cualquier otra cosa se sigue sirviendo como descarga."""
    extension = archivos.extension_de(nombre or '')
    try:
        if extension == 'mp4':
            with open(camino, 'rb') as f:
                return 'video/mp4' if f.read(12)[4:8] == b'ftyp' else None
        if extension == 'geojson':
            return 'application/geo+json' if leer(camino)[0] else None
    except OSError:
        return None
    return None


def leer(camino):
    """(puntos [[lon, lat, alt], …], propiedades) del GeoJSON, o (None, None) si no es un recorrido."""
    try:
        with open(camino, encoding='utf-8') as f:
            dato = json.load(f)
        puntos = dato['geometry']['coordinates']
        if dato['geometry']['type'] != 'LineString' or not isinstance(puntos, list) or len(puntos) > PUNTOS_MAX:
            return None, None
        limpios = []
        for p in puntos:
            lon, lat = float(p[0]), float(p[1])
            if not (-90 <= lat <= 90 and -180 <= lon <= 180):
                return None, None
            limpios.append([lon, lat, float(p[2]) if len(p) > 2 else 0.0])
        return limpios, dato.get('properties') if isinstance(dato.get('properties'), dict) else {}
    except (OSError, ValueError, KeyError, TypeError, IndexError):
        return None, None


def resumen(camino):
    """{puntos, metros, segundos, inicio, fin} del recorrido guardado en `camino`, o None."""
    puntos, propiedades = leer(camino)
    if not puntos:
        return None
    tiempos = propiedades.get('tiempos_ms') if isinstance(propiedades.get('tiempos_ms'), list) else []
    try:
        segundos = int(round((float(tiempos[-1]) - float(tiempos[0])) / 1000)) if len(tiempos) == len(puntos) else 0
    except (TypeError, ValueError):
        segundos = 0
    metros = sum(_metros(puntos[i - 1], puntos[i]) for i in range(1, len(puntos)))
    altitudes = [p[2] for p in puntos if p[2]]
    cerrado = area(puntos)
    return {'puntos': len(puntos), 'metros': int(round(metros)), 'segundos': max(segundos, 0),
            'altitud_min': round(min(altitudes), 1) if altitudes else None,
            'altitud_max': round(max(altitudes), 1) if altitudes else None,
            'grabado': str(propiedades.get('inicio') or '')[:25],
            'area_m2': int(round(cerrado[0])) if cerrado else None,
            'perimetro_m': int(round(cerrado[1])) if cerrado else None,
            'inicio': '%.7f %.7f' % (puntos[0][1], puntos[0][0]), 'fin': '%.7f %.7f' % (puntos[-1][1], puntos[-1][0])}


def _ficha(encuesta_id, entrada):
    return archivos.ficha(encuesta_id, entrada.get('id')) if isinstance(entrada, dict) else None


def valor_limpio(pregunta, bruto, titulo):
    """(valor, error). El valor lleva las fichas de los dos archivos y el resumen del camino."""
    if bruto is None or bruto == '' or bruto == {}:
        return None, None
    if not isinstance(bruto, dict):
        return None, f'«{titulo}»: el recorrido no es válido. Vuelve a grabarlo en la app.'
    encuesta_id = pregunta.get('_encuesta_id')
    recorrido = _ficha(encuesta_id, bruto.get('recorrido'))
    if not recorrido:
        return None, f'«{titulo}»: el recorrido no llegó a Raíces. Vuelve a enviarlo desde la app.'
    datos = resumen(archivos.camino_pendiente(encuesta_id, recorrido['id']) or '')
    if not datos or datos['puntos'] < 2:
        return None, f'«{titulo}»: el recorrido no tiene puntos suficientes. Vuelve a grabarlo a cielo abierto.'
    video = _ficha(encuesta_id, bruto.get('video'))
    if pregunta.get('recorrido_video') and not video:
        return None, f'«{titulo}»: falta el video del recorrido.'
    return dict(datos, recorrido=recorrido, video=video), None


def fichas(valor):
    """Las fichas de archivo que lleva una respuesta de recorrido."""
    if not isinstance(valor, dict):
        return []
    return [f for f in (valor.get('recorrido'), valor.get('video')) if isinstance(f, dict)]


def texto(valor):
    if not isinstance(valor, dict):
        return ''
    metros, segundos = valor.get('metros') or 0, valor.get('segundos') or 0
    largo = ('%.1f km' % (metros / 1000)).replace('.', ',') if metros >= 1000 else '%d m' % metros
    tiempo = '%d min %02d s' % (segundos // 60, segundos % 60) if segundos else ''
    superficie = valor.get('area_m2')
    if superficie:
        superficie = ('%.2f ha' % (superficie / 10000)).replace('.', ',') if superficie >= 10000 else '%d m²' % superficie
    return 'Recorrido de %s%s%s%s' % (largo, ' en ' + tiempo if tiempo else '', ', área %s' % superficie if superficie else '',
                                    ', con video' if valor.get('video') else '')
