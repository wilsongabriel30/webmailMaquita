# -*- coding: utf-8 -*-
"""
API de versiones y estilo de carpeta del Almacén Maquita.
=========================================================
Historial de versiones de archivo (como Google Drive) y color/icono de carpeta.

Autoría: Equipo de Tecnología Maquita — 2026-07-03
"""
import logging

from flask import Blueprint, jsonify, request

import nucleo_archivos as nucleo
from api_archivos import error, usuario_actual

log = logging.getLogger('almacen.versiones')

bp_versiones = Blueprint('almacen_versiones', __name__)


@bp_versiones.route('/versiones/<file_id>', methods=['GET'])
def listar_versiones(file_id):
    """GET /versiones/<file_id> — historial de versiones de un archivo.
    file_id es el identificador estable del archivo (el que trae cada item al listar)."""
    usuario = usuario_actual()
    versiones = nucleo.listar_versiones(usuario, file_id)
    return jsonify({'success': True, 'file_id': file_id,
                    'versiones': versiones, 'total': len(versiones)})


@bp_versiones.route('/versiones/<file_id>/restaurar', methods=['POST'])
def restaurar_version(file_id):
    """POST /versiones/<file_id>/restaurar — {version_id}. Vuelve a una versión anterior.
    El contenido actual se conserva como versión nueva (no se pierde nada)."""
    usuario = usuario_actual()
    datos = request.get_json() or {}
    version_id = datos.get('version_id')
    if not version_id:
        return error('version_id requerido', 400)
    try:
        nucleo.restaurar_version(usuario, file_id, int(version_id))
    except FileNotFoundError:
        return error('Versión no encontrada', 404)
    return jsonify({'success': True, 'message': 'Versión restaurada correctamente'})


@bp_versiones.route('/versiones/<file_id>/fijar', methods=['POST'])
def fijar_version(file_id):
    """POST /versiones/<file_id>/fijar — {version_id, fijar} : marca/desmarca "mantener siempre"
    (las versiones fijadas NO se podan nunca)."""
    usuario = usuario_actual()
    from almacen_bd import ejecutar
    datos = request.get_json() or {}
    version_id = datos.get('version_id')
    if not version_id:
        return error('version_id requerido', 400)
    fijar = datos.get('fijar', True) is not False
    ejecutar("""
        UPDATE versiones SET guardar_siempre = %s
        WHERE id = %s AND usuario_id = %s AND file_id = %s
    """, (fijar, int(version_id), usuario, file_id))
    return jsonify({'success': True, 'guardar_siempre': fijar})


@bp_versiones.route('/carpetas/estilo', methods=['POST'])
def cambiar_estilo_carpeta():
    """
    POST /carpetas/estilo — {folder_id, color, icono}
    Cambia color y/o icono de una carpeta (como los colores de carpeta de Drive).
    color/icono: None = no cambiar, "" = quitar, valor = fijar.
    """
    usuario = usuario_actual()
    datos = request.get_json() or {}
    folder_id = datos.get('folder_id')
    if not folder_id:
        return error('folder_id requerido', 400)
    color = datos.get('color')
    if color and not (color.startswith('#') and len(color) <= 9):
        return error('Color inválido', 400)
    nucleo.set_estilo_carpeta(usuario, folder_id, color, datos.get('icono'))
    return jsonify({'success': True, 'message': 'Estilo actualizado'})
