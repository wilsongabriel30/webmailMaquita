# -*- coding: utf-8 -*-
"""
API de creación de documentos en blanco del Almacén Maquita.
============================================================
`POST /api/almacen/archivos/crear` — crea un archivo vacío del tipo pedido y lo
guarda con nucleo.subir() (versionado/dedup). El explorador (menú "Nuevo") lo usa
para Documento/Hoja/Presentación/Texto/Diagrama. Sin este endpoint, en modo
Almacén el "Nuevo" caía en el catch-all (404) y no se creaba nada.

- Office (docx/xlsx/pptx): se copia la plantilla vacía de FARO (recursos/plantillas).
- Diagrama (drawio): lienzo en blanco (reusa DIAGRAMA_VACIO de api_drawio).
- Formulario (forma): definición JSON semilla (reusa formulario_vacio de
  api_encuestas), para que el editor de formularios abra listo para escribir.
- Texto (txt): archivo vacío.

Autoría: Equipo de Tecnología Maquita — 2026-07-23
"""
import io
import os

from flask import Blueprint, jsonify, request

import nucleo_archivos as nucleo
from api_archivos import _permiso_unidad, error, usuario_actual
from api_drawio import DIAGRAMA_VACIO
from seguridad_rutas import RutaInvalida, normalizar_ruta_virtual

bp_crear = Blueprint('almacen_crear', __name__)

# Plantillas office vacías de FARO (el motor corre embebido en FARO)
DIR_PLANTILLAS = '/home/sistemas/Maquita/modulos/nextcloud/recursos/plantillas'
TIPO_EXT = {'documento': 'docx', 'hoja': 'xlsx', 'presentacion': 'pptx',
            'texto': 'txt', 'diagrama': 'drawio', 'formulario': 'forma'}
OFFICE = {'docx', 'xlsx', 'pptx'}


@bp_crear.route('/archivos/crear', methods=['POST'])
def crear_documento():
    usuario = usuario_actual()
    datos = request.get_json(silent=True) or {}
    try:
        ruta = normalizar_ruta_virtual(datos.get('ruta', ''))
    except RutaInvalida as excepcion:
        return error(str(excepcion), excepcion.codigo)
    if ruta == '/' or ruta.endswith('/'):
        return error('Ruta inválida', 400)

    tipo = (datos.get('tipo') or '').strip()
    nombre = ruta.rsplit('/', 1)[-1]
    carpeta = ruta.rsplit('/', 1)[0] or '/'
    # En unidades compartidas solo crea quien tiene EDICIÓN ahí (12/08/2026:
    # un lector podía crear documentos en cualquier carpeta de la unidad).
    if not _permiso_unidad(usuario, carpeta, escritura=True):
        return error('No tienes permiso para crear aquí. Pide edición de esta '
                     'carpeta a quien administra la unidad.', 403)
    # Con un tipo conocido, el nombre SIEMPRE termina en su extensión (26/11/2026): un nombre con puntos
    # («E11.R2A2.Calidad…») se tomaba como si ya tuviera extensión, el archivo quedaba sin ella, vacío, no abría
    # en el editor y chocaba con una carpeta del mismo nombre. Carpeta «X» y archivo «X.docx» pueden convivir.
    if tipo in TIPO_EXT:
        ext = TIPO_EXT[tipo]
        if not nombre.lower().endswith('.' + ext):
            nombre = nombre.strip() + '.' + ext
            ruta = (carpeta.rstrip('/') + '/' + nombre)
    else:
        ext = nombre.rsplit('.', 1)[-1].lower() if '.' in nombre else ''
    # «Crear» nunca pisa un archivo que ya existe (16/11/2026): crear otra encuesta con el mismo nombre
    # sobrescribía la anterior y dejaba varios registros de encuesta con la misma ruta.
    try:
        if os.path.exists(nucleo.ruta_fisica(usuario, ruta, escritura=True)):
            return error('Ya existe «%s» en esta carpeta. Ábralo para editarlo o use otro nombre.' % nombre, 409)
    except RutaInvalida as excepcion:
        return error(str(excepcion), excepcion.codigo)

    if ext == 'forma' or tipo == 'formulario':
        # Un .forma es la definición del formulario en JSON. Se siembra con
        # una pregunta para que el editor abra con algo con lo que trabajar.
        import json as _json
        from api_encuestas import formulario_vacio
        semilla = formulario_vacio(nombre[:-6] if nombre.lower().endswith('.forma')
                                   else nombre)
        contenido = _json.dumps(semilla, ensure_ascii=False,
                                indent=2).encode('utf-8')
    elif ext == 'drawio' or tipo == 'diagrama':
        contenido = DIAGRAMA_VACIO.encode('utf-8')
    elif ext in OFFICE:
        plantilla = os.path.join(DIR_PLANTILLAS, 'vacio.' + ext)
        if not os.path.isfile(plantilla):
            return error('Plantilla no disponible para .' + ext, 400)
        with open(plantilla, 'rb') as f:
            contenido = f.read()
    else:
        contenido = b''   # texto u otros: archivo vacío

    try:
        nucleo.subir(usuario, carpeta, nombre, io.BytesIO(contenido))
    except Exception as excepcion:
        return error('No se pudo crear el archivo: ' + str(excepcion), 500)
    return jsonify({'success': True, 'ruta': ruta, 'nombre': nombre})
