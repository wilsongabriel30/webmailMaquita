# -*- coding: utf-8 -*-
"""
API drawio del Almacén Maquita (edición de diagramas .drawio).
==============================================================
Integra el editor open-source drawio (motor Docker en VM131, publicado bajo
datos.maquita.com.ec/drawio/) con el explorador del Almacén. Un `.drawio` es un
archivo XML: se carga su contenido, se edita en el iframe de drawio (modo embed,
protocolo postMessage) y al guardar se reescribe con nucleo.subir() → hereda
versionado y dedup, igual que cualquier documento.

NO usa Document Server ni JWT (a diferencia de OnlyOffice): el editor corre en el
navegador y habla con estos endpoints con la sesión de FARO. El candado maestro de
/api/almacen* y /archivos-almacen* (integracion_faro) protege el acceso.

Autoría: Equipo de Tecnología Maquita — 2026-07-23
"""
import io
import logging
import os

from flask import Blueprint, jsonify, request, send_file

import nucleo_archivos as nucleo
from api_archivos import error, usuario_actual
from registro import registrar_actividad
from seguridad_rutas import (RutaInvalida, normalizar_ruta_virtual, ruta_fisica)

log = logging.getLogger('almacen.drawio')

bp_drawio = Blueprint('almacen_drawio', __name__)
bp_drawio_web = Blueprint('almacen_drawio_web', __name__)

# Diagrama vacío (drawio lo entiende como lienzo en blanco)
DIAGRAMA_VACIO = ('<mxGraphModel dx="800" dy="600" grid="1" gridSize="10" '
                  'guides="1" tooltips="1" connect="1" arrows="1" fold="1" '
                  'page="1" pageScale="1" pageWidth="850" pageHeight="1100" '
                  'math="0" shadow="0"><root>'
                  '<mxCell id="0"/><mxCell id="1" parent="0"/>'
                  '</root></mxGraphModel>')

EXT_DRAWIO = {'drawio', 'xml'}


@bp_drawio.route('/drawio/cargar', methods=['GET'])
def drawio_cargar():
    """GET /api/almacen/drawio/cargar?ruta= — devuelve el XML del .drawio.
    Si el archivo está vacío (recién creado) devuelve un lienzo en blanco."""
    usuario = usuario_actual()
    try:
        ruta = normalizar_ruta_virtual(request.args.get('ruta', ''))
        fisica = ruta_fisica(usuario, ruta)
    except RutaInvalida as excepcion:
        return error(str(excepcion), excepcion.codigo)
    if not os.path.isfile(fisica):
        return error('Archivo no encontrado', 404)
    try:
        with open(fisica, 'r', encoding='utf-8', errors='replace') as f:
            xml = f.read()
    except Exception as excepcion:
        log.error('drawio cargar %s: %s', ruta, excepcion)
        return error('No se pudo leer el diagrama', 500)
    if not xml.strip():
        xml = DIAGRAMA_VACIO
    return jsonify({'success': True, 'xml': xml,
                    'nombre': ruta.rsplit('/', 1)[-1]})


@bp_drawio.route('/drawio/guardar', methods=['POST'])
def drawio_guardar():
    """POST /api/almacen/drawio/guardar?ruta= {xml} — guarda el diagrama.
    Usa nucleo.subir(): versiona el contenido anterior y deduplica."""
    usuario = usuario_actual()
    try:
        ruta = normalizar_ruta_virtual(request.args.get('ruta', ''))
    except RutaInvalida as excepcion:
        return error(str(excepcion), excepcion.codigo)
    datos = request.get_json(silent=True) or {}
    xml = datos.get('xml')
    if xml is None:
        return error('Falta el contenido del diagrama', 400)
    contenido = xml.encode('utf-8')
    carpeta = ruta.rsplit('/', 1)[0] or '/'
    nombre = ruta.rsplit('/', 1)[-1]
    # Guardar un diagrama es escribir un archivo: pide el mismo permiso que
    # subirlo (01/09/2026 — un lector podia sobrescribir cualquier diagrama de
    # la unidad, y un editor podia hacerlo fuera de su carpeta).
    from permisos_accion import puede_escribir, MOTIVO_LECTOR
    if not puede_escribir(usuario, carpeta):
        return error(MOTIVO_LECTOR, 403)
    try:
        nucleo.subir(usuario, carpeta, nombre, io.BytesIO(contenido))
    except Exception as excepcion:
        log.error('drawio guardar %s: %s', ruta, excepcion)
        return error('No se pudo guardar el diagrama', 500)
    try:
        registrar_actividad(usuario, 'edito', ruta, nucleo.tamano_humano(len(contenido)))
    except Exception:
        pass
    return jsonify({'success': True})


@bp_drawio_web.route('/archivos-almacen/diagrama')
def editor_drawio():
    """Página del editor de diagramas. La ruta del .drawio viaja en ?ruta= y el
    JS embebe drawio (/drawio/?embed=1) hablando con /api/almacen/drawio/*.
    Protegida por el candado maestro de /archivos-almacen*."""
    plantilla = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                             'plantillas', 'editor_drawio.html')
    _r = send_file(plantilla, mimetype='text/html'); _r.headers['Permissions-Policy'] = 'unload=*'; return _r
