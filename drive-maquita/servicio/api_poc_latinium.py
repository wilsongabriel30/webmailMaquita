# -*- coding: utf-8 -*-
"""Botón «Actualizar ahora» de la prueba de concepto Latinium → Drive (28/10/2026).

Los libros de la carpeta «Pruebas de concepto» (unidad 12, «Planificación ASC»)
los rehace el cron cada 15 minutos en horario laboral. Para quien necesita el
dato al instante, la carpeta muestra una barra con la última actualización y un
botón que lanza la misma pasada:

    GET  /api/almacen/poc-latinium/estado      → última pasada y si hay una en curso
    POST /api/almacen/poc-latinium/actualizar  → lanza una pasada (si no hay otra)

Regla de la casa: nada pesado dentro de gunicorn. La pasada corre en un proceso
aparte, como root, por el guion /usr/local/bin/poc-latinium-asc-actualizar (sudo
sin clave, solo para ese guion); el mismo cerrojo del cron evita que se pisen.
Pueden usarlo los miembros de la unidad 12 (el permiso lo decide la unidad).
"""
import json
import logging
import os
import subprocess
from datetime import datetime

from flask import Blueprint, jsonify

from api_archivos import error, usuario_actual

log = logging.getLogger('almacen.poc_latinium')

bp_poc_latinium = Blueprint('poc_latinium', __name__)

CARPETA = '/unidades/12/Pruebas de concepto'
ESTADO = '/var/lib/poc-latinium-asc/estado.json'
GUION = '/usr/local/bin/poc-latinium-asc-actualizar'


def _puede(usuario):
    from api_unidades import permiso_unidad
    return permiso_unidad(usuario, CARPETA)


def _leer_estado():
    try:
        with open(ESTADO, encoding='utf-8') as fichero:
            return json.load(fichero)
    except Exception:
        return {}


def _hace(fecha_iso):
    """'2026-10-28T14:10:02' → ('28/10/2026 14:10', 'hace 3 min')."""
    try:
        fecha = datetime.fromisoformat(fecha_iso)
    except (TypeError, ValueError):
        return None, None
    minutos = int((datetime.now() - fecha).total_seconds() // 60)
    if minutos < 1:
        hace = 'hace un momento'
    elif minutos < 60:
        hace = 'hace %d min' % minutos
    elif minutos < 60 * 24:
        hace = 'hace %d h %02d min' % divmod(minutos, 60)
    else:
        hace = 'hace %d días' % (minutos // (60 * 24))
    return fecha.strftime('%d/%m/%Y %H:%M'), hace


def estado_publico():
    estado = _leer_estado()
    en_curso = bool(estado.get('en_curso'))
    fecha, hace = _hace(estado.get('inicio') if en_curso else estado.get('fin'))
    return {
        'success': True, 'carpeta': CARPETA, 'en_curso': en_curso,
        'resultado': estado.get('resultado'), 'origen': estado.get('origen'),
        'actualizados': estado.get('actualizados', 0), 'segundos': estado.get('segundos', 0),
        'fecha': fecha, 'hace': hace,
    }


@bp_poc_latinium.route('/poc-latinium/estado', methods=['GET'])
def estado():
    usuario = usuario_actual()
    if not _puede(usuario):
        return error('Sin acceso a la carpeta de la prueba de concepto', 403)
    return jsonify(estado_publico())


@bp_poc_latinium.route('/poc-latinium/actualizar', methods=['POST'])
def actualizar():
    usuario = usuario_actual()
    if not _puede(usuario):
        return error('Sin acceso a la carpeta de la prueba de concepto', 403)
    if _leer_estado().get('en_curso'):
        return jsonify(dict(estado_publico(), lanzada=False,
                            mensaje='Ya hay una actualización en curso; en un momento estará lista.'))
    if not os.access(GUION, os.X_OK):
        return error('El guion de actualización no está disponible', 503)
    try:
        subprocess.Popen(['sudo', '-n', GUION, 'web:%d' % int(usuario)],
                         stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL, start_new_session=True)
    except Exception as excepcion:
        log.warning('poc-latinium: no se pudo lanzar la actualización: %s', excepcion)
        return error('No se pudo lanzar la actualización', 500)
    log.info('poc-latinium: actualización pedida por el usuario %s', usuario)
    return jsonify(dict(estado_publico(), lanzada=True, en_curso=True,
                        mensaje='Actualizando desde Latinium…')), 202
