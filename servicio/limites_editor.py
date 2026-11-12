# -*- coding: utf-8 -*-
"""
Límite de tamaño para abrir archivos en línea y aviso a Tecnología (20/10/2026).
===============================================================================
QUÉ PASÓ: el Document Server (OnlyOffice, VM 131) venía de fábrica con un tope de
100 MB por archivo (maxDownloadBytes). Dos informes de 138 y 188 MB no abrían en
línea y el editor solo decía «Error del editor: {errorCode: -4}». Nadie se enteró
hasta que lo reportaron las personas.

QUÉ HACE ESTE MÓDULO:
  - limite_bytes(): el tope vigente (1 GiB, el mismo que se puso en el Document
    Server con /opt/onlyoffice/limites-maquita/asegurar.sh en la VM 131). Se puede
    cambiar sin tocar código con la clave `onlyoffice_max_bytes` de config_kv,
    pero SIEMPRE a la par del servidor de documentos.
  - mensaje_si_excede(): texto claro para la persona si el archivo pasa del tope
    (en vez del error mudo).
  - presupuesto_segundos(): cuánto esperar una conversión según el tamaño.
  - avisar_tecnologia(): correo a Tecnología (uno por asunto cada 30 min
    por proceso) y línea en el registro. Lo usan api_onlyoffice y
    api_editor_errores. Nunca lanza.

Ver también: conversion_ds.py, api_editor_errores.py, documentación
02-MODULOS/NUBE-MAQUITA/sesiones/sesion-20261020-onlyoffice-archivos-grandes.md
Autoría: Equipo de Tecnología Maquita — 2026-10-20
"""
import html
import logging
import os
import time

import config_almacen  # noqa: F401  (al importarse carga el .env del servidor)

log = logging.getLogger('almacen.limites_editor')

# 1 GiB: igual que FileConverter.converter.maxDownloadBytes del Document Server.
LIMITE_BYTES_DEFECTO = 1024 ** 3
# El correo real va en el .env del servidor (ALMACEN_CORREO_TECNOLOGIA), fuera del repositorio.
CORREO_TECNOLOGIA = os.getenv('ALMACEN_CORREO_TECNOLOGIA', 'tecnologia@example.org')
_PAUSA_AVISO = 30 * 60          # segundos entre dos correos del mismo asunto

_cache = {'valor': 0, 'hasta': 0.0}
_avisos = {}


def limite_bytes() -> int:
    """Tope configurado (config_kv `onlyoffice_max_bytes`; si no, 1 GiB).
    Se consulta a la base como mucho una vez por minuto."""
    ahora = time.time()
    if _cache['valor'] and _cache['hasta'] > ahora:
        return _cache['valor']
    valor = LIMITE_BYTES_DEFECTO
    try:
        from almacen_bd import consultar
        filas = consultar("SELECT valor FROM config_kv WHERE clave = 'onlyoffice_max_bytes'")
        if filas and str(filas[0]['valor']).strip().isdigit():
            valor = int(str(filas[0]['valor']).strip())
    except Exception as excepcion:
        log.debug('límite del editor: se usa el valor por defecto (%s)', excepcion)
    _cache.update(valor=valor, hasta=ahora + 60)
    return valor


def humano(cantidad) -> str:
    """188100000 → '188 MB' (base 1024, como lo muestra el Drive)."""
    cantidad = float(cantidad or 0)
    for unidad in ('bytes', 'KB', 'MB', 'GB', 'TB'):
        if cantidad < 1024 or unidad == 'TB':
            return ('%d %s' if unidad == 'bytes' or cantidad >= 100 else '%.1f %s') % (cantidad, unidad)
        cantidad /= 1024.0
    return '%d bytes' % cantidad


def mensaje_si_excede(fisica: str, nombre: str = None):
    """Texto para la persona si el archivo pesa más de lo que el editor acepta;
    None si cabe (o si no se pudo medir: entonces se intenta abrir igual)."""
    try:
        tamano = os.path.getsize(fisica)
    except OSError:
        return None
    tope = limite_bytes()
    if tamano <= tope:
        return None
    nombre = nombre or os.path.basename(fisica)
    return ('«%s» pesa %s y el máximo para abrirlo en línea es %s. Descárgalo para '
            'trabajarlo en tu computador, o escribe a %s si necesitas editarlo en línea.'
            % (nombre, humano(tamano), humano(tope), CORREO_TECNOLOGIA))


def presupuesto_segundos(tamano_bytes) -> int:
    """Cuánto esperar a que el Document Server convierta un archivo: 90 s más
    2 s por cada MB, con tope de 15 min (un .xls de 188 MB tarda unos minutos)."""
    return int(min(900, 90 + 2 * float(tamano_bytes or 0) / (1024 * 1024)))


def avisar_tecnologia(asunto: str, detalle: str) -> bool:
    """Correo a Tecnología con el detalle, y siempre una línea en el registro.
    Un correo por asunto cada 30 min (por proceso) para no inundar. Nunca lanza."""
    log.error('[editor] %s — %s', asunto, detalle)
    ahora = time.time()
    if _avisos.get(asunto, 0) > ahora:
        return False
    _avisos[asunto] = ahora + _PAUSA_AVISO
    try:
        import correo_almacen
        cuerpo = ('<p><b>%s</b></p><pre style="white-space:pre-wrap">%s</pre>'
                  '<p>Dónde mirar: <code>journalctl -u faro-maquita</code> (VM 101) y '
                  '<code>/opt/onlyoffice/logs/documentserver/docservice/out.log</code> (VM 131). '
                  'Límite vigente del editor: %s.</p>'
                  % (html.escape(asunto), html.escape(detalle), humano(limite_bytes())))
        return bool(correo_almacen.enviar(CORREO_TECNOLOGIA, '[Drive Maquita] ' + asunto, cuerpo))
    except Exception as excepcion:
        log.warning('no se pudo avisar a Tecnología (%s): %s', asunto, excepcion)
        return False
