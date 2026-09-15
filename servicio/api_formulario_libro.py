# -*- coding: utf-8 -*-
"""«Crear formulario» desde una hoja de cálculo abierta en el editor.

Es la puerta de entrada de lo que hace Google Sheets: estando en un Excel, se
crea un formulario y sus respuestas van cayendo en una hoja nueva de ese mismo
libro. Un segundo formulario crea otra hoja.

Aquí solo está el trámite de crearlo todo de una vez:

  1. crea el `.forma` (la definición del formulario) junto al libro;
  2. lo registra y le prepara su archivo de respuestas, que desde el
     10/09/2026 va a la carpeta interna `.formularios` (oculta): en el
     Drive solo se ven el Excel y el formulario, como en Google;
  3. crea en el libro una hoja con el nombre del formulario y la deja
     vinculada (`formularios_libro.enlazar`).

El libro suele estar ABIERTO en OnlyOffice cuando esto ocurre (el botón
vive en el editor), y lo que se escriba en disco lo pisa el siguiente
guardado del editor. Por eso la respuesta lleva `hoja` y `cabeceras`: el
complemento crea la hoja dentro de la sesión viva, y al cerrarse el editor
el callback de OnlyOffice vuelve a aplicar el vínculo (`refrescar_por_destino`).

El motor y el porqué del diseño están en `formularios_libro.py`.

Tiene blueprint propio, y no cuelga del de encuestas, por un motivo concreto:
estas rutas las llama el botón del editor sin token CSRF, así que necesitan la
exención que ya tienen las demás API del Almacén (`bp_vinculos` y compañía).
Colgarlas del blueprint de encuestas obligaría a eximirlo entero, y ahí viven
rutas que sí deben pedir el token.
"""

import io
import json
import logging
import os
import uuid

from flask import Blueprint, jsonify, request

import encuestas_bd as ebd
import encuestas_hoja as hoja_mod
import formularios_libro as flibro
import formularios_nombres as nombres
import nucleo_archivos as nucleo
from api_encuestas import error, usuario_actual
from encuestas_modelo import formulario_vacio
from urllib.parse import quote

from seguridad_rutas import normalizar_ruta_virtual, RutaInvalida

log = logging.getLogger('almacen.formulario_libro')

bp_formulario_libro = Blueprint('formulario_libro', __name__)

EXTENSIONES_LIBRO = ('.xlsx', '.xlsm')


def _titulo_libre(usuario, carpeta, base):
    """«Formulario de X», «Formulario de X 2»… evitando pisar uno existente."""
    from seguridad_rutas import ruta_fisica
    intento, titulo = 1, base
    while True:
        ruta = (('' if carpeta == '/' else carpeta) + '/' + titulo + '.forma')
        try:
            if not os.path.exists(ruta_fisica(usuario, ruta)):
                return titulo
        except RutaInvalida:
            return titulo
        intento += 1
        titulo = '%s %d' % (base, intento)


@bp_formulario_libro.route('/formularios/desde-libro', methods=['POST'])
def desde_libro():
    """Crea un formulario y le deja su hoja de respuestas dentro del libro.

    JSON: {"ruta": "/carpeta/Mi libro.xlsx"}
    """
    usuario = usuario_actual()
    datos = request.get_json(silent=True) or {}
    try:
        ruta_libro = normalizar_ruta_virtual(datos.get('ruta', ''))
    except RutaInvalida as excepcion:
        return error(str(excepcion), excepcion.codigo)
    if not ruta_libro.lower().endswith(EXTENSIONES_LIBRO):
        return error('Esto solo funciona desde una hoja de cálculo', 400)

    carpeta = ruta_libro.rsplit('/', 1)[0] or '/'
    from permisos_accion import puede_escribir, MOTIVO_LECTOR
    if not puede_escribir(usuario, carpeta):
        return error(MOTIVO_LECTOR, 403)

    nombre_libro = os.path.splitext(ruta_libro.rsplit('/', 1)[-1])[0]
    titulo = _titulo_libre(usuario, carpeta, 'Formulario de ' + nombre_libro)

    try:
        # 1. La definición del formulario, junto al libro.
        definicion = formulario_vacio(titulo)
        contenido = json.dumps(definicion, ensure_ascii=False,
                               indent=2).encode('utf-8')
        nucleo.subir(usuario, carpeta, titulo + '.forma', io.BytesIO(contenido))
        ruta_forma = (('' if carpeta == '/' else carpeta) + '/' + titulo + '.forma')

        # 2. Registro y archivo de respuestas (vacío, con sus cabeceras).
        encuesta_id = definicion.get('id') or uuid.uuid4().hex
        definicion['id'] = encuesta_id
        ebd.registrar(encuesta_id, usuario, ruta_forma, titulo)
        fila = ebd.obtener(encuesta_id)

        respuestas = hoja_mod.construir(fila, definicion)
        if respuestas is None:
            return error('No se pudo preparar la hoja de respuestas', 500)
        nombre_respuestas = nombres.nombre_archivo_respuestas(titulo)
        carpeta_oculta = nombres.carpeta_respuestas(carpeta)
        nucleo.subir(usuario, carpeta_oculta, nombre_respuestas, respuestas)
        ruta_respuestas = carpeta_oculta + '/' + nombre_respuestas
        hoja_mod.vincular(encuesta_id, ruta_respuestas)

        # 3. La hoja dentro del libro, ya vinculada.
        hoja = flibro.enlazar(usuario, encuesta_id, ruta_libro)
    except flibro.SinHoja as excepcion:
        return error(str(excepcion), 400)
    except Exception as excepcion:
        log.error('desde-libro %s: %s', ruta_libro, excepcion)
        return error('No se pudo crear el formulario: %s' % excepcion, 500)

    log.info('formulario %s creado desde %s (hoja %s)', titulo, ruta_libro, hoja)
    return jsonify({
        'success': True,
        'titulo': titulo,
        'hoja': hoja,
        # Para que el complemento cree la hoja EN EL EDITOR ABIERTO con sus
        # cabeceras, sin esperar a que se cierre el libro.
        'cabeceras': hoja_mod.cabeceras(fila, definicion),
        'ruta_forma': ruta_forma,
        # El editor visual del formulario, para escribir las preguntas. NO el
        # explorador: llevaba al inicio de la unidad y no al formulario recién
        # creado (09/09/2026).
        'url_editar': '/archivos-almacen/formulario?ruta=' + quote(ruta_forma),
        'mensaje': 'Formulario creado. Sus respuestas llegarán a la hoja «%s» '
                   'de este libro.' % hoja,
    })


@bp_formulario_libro.route('/formularios/del-libro', methods=['GET'])
def del_libro():
    """Qué hojas de este libro reciben respuestas (para no crear duplicados)."""
    usuario_actual()
    try:
        ruta_libro = normalizar_ruta_virtual(request.args.get('ruta', ''))
    except RutaInvalida as excepcion:
        return error(str(excepcion), excepcion.codigo)
    return jsonify({'success': True, 'hojas': flibro.hojas_enlazadas(ruta_libro)})
