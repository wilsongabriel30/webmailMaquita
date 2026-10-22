# -*- coding: utf-8 -*-
"""
Creación de documentos en blanco (menú «Nuevo» del explorador).
===============================================================
`POST /api/almacen/archivos/crear` — {ruta, tipo} → crea el archivo vacío y lo guarda
con `nucleo.subir()` (cuota, deduplicación, permisos de unidad).

Faltaba en el Almacén del webmail (solo existía en el motor del sistema central,
`drive-maquita/servicio/api_crear.py`): la petición caía en el comodín
`/api/almacen/<path>`, que solo admitía GET, y Flask respondía 405 Method Not Allowed
a «Nuevo → Documento (Word)» y al resto del menú.

- Office (docx/xlsx/pptx): paquete en blanco de `plantillas_office`.
- Diagrama (drawio): lienzo vacío.
- Texto (txt) u otra extensión: archivo vacío.

No pisa: si ya hay un archivo con ese nombre responde 409 (subir() lo guardaría como
versión nueva y el usuario perdería de vista su documento).
"""
import io
import os

from flask import Blueprint, jsonify, request

import nucleo_archivos as nucleo
import plantillas_office
from api_archivos import _permiso_unidad, error, usuario_actual
from registro import registrar_actividad
from seguridad_rutas import RutaInvalida, normalizar_ruta_virtual, ruta_fisica

bp_crear = Blueprint('almacen_crear', __name__)

TIPO_EXT = {'documento': 'docx', 'hoja': 'xlsx', 'presentacion': 'pptx',
            'texto': 'txt', 'diagrama': 'drawio'}

DIAGRAMA_VACIO = ('<mxGraphModel dx="800" dy="600" grid="1" gridSize="10" '
                  'guides="1" tooltips="1" connect="1" arrows="1" fold="1" '
                  'page="1" pageScale="1" pageWidth="850" pageHeight="1100" '
                  'math="0" shadow="0"><root>'
                  '<mxCell id="0"/><mxCell id="1" parent="0"/>'
                  '</root></mxGraphModel>')


def contenido_vacio(extension: str) -> bytes:
    """Bytes iniciales del archivo nuevo según su extensión."""
    extension = (extension or '').lower()
    if extension in plantillas_office.EXTENSIONES:
        return plantillas_office.documento_vacio(extension)
    if extension == 'drawio':
        return DIAGRAMA_VACIO.encode('utf-8')
    return b''


# Mismo prefijo que el resto del contrato: /api/almacen (app_webmail) y
# /api/nextcloud (app_almacen).
@bp_crear.route('/archivos/crear', methods=['POST'])
def crear_documento():
    usuario = usuario_actual()
    datos = request.get_json(silent=True) or {}
    pedida = str(datos.get('ruta') or '')
    if not pedida.strip('/ ') or pedida.endswith('/'):
        return error('Ruta inválida', 400)   # sin nombre de archivo (o es una carpeta)
    try:
        ruta = normalizar_ruta_virtual(pedida)
    except RutaInvalida as excepcion:
        return error(str(excepcion), excepcion.codigo)
    if ruta == '/':
        return error('Ruta inválida', 400)

    tipo = (datos.get('tipo') or '').strip()
    carpeta, nombre = ruta.rsplit('/', 1)
    carpeta = carpeta or '/'
    if '.' not in nombre and TIPO_EXT.get(tipo):
        nombre = '%s.%s' % (nombre, TIPO_EXT[tipo])
        ruta = ('' if carpeta == '/' else carpeta) + '/' + nombre
    if not _permiso_unidad(usuario, carpeta, escritura=True):
        return error('No tienes permiso para crear aquí. Pide edición de esta '
                     'carpeta a quien administra la unidad.', 403)
    try:
        if os.path.lexists(ruta_fisica(usuario, ruta)):
            return error('Ya existe un archivo con ese nombre en esta carpeta', 409)
        extension = nombre.rsplit('.', 1)[-1] if '.' in nombre else ''
        r = nucleo.subir(usuario, carpeta, nombre, io.BytesIO(contenido_vacio(extension)))
    except RutaInvalida as excepcion:
        return error(str(excepcion), excepcion.codigo)
    except (nucleo.CuotaExcedida, nucleo.SinEspacio) as excepcion:
        return error(str(excepcion), excepcion.codigo)
    registrar_actividad(usuario, 'subio', r.get('ruta', ruta), r.get('tamano_humano', ''))
    return jsonify({'success': True, 'ruta': r.get('ruta', ruta), 'nombre': nombre}), 201
