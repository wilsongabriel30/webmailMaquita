# -*- coding: utf-8 -*-
"""API de «Sin acceso a esta carpeta» en las unidades compartidas (26/11/2026).

  GET    /unidades/<id>/bloqueos-carpeta?ruta=/Sub   bloqueos que afectan a esa carpeta
  POST   /unidades/<id>/bloqueos-carpeta             {ruta, usuario_id}: quitar el acceso
  DELETE /unidades/<id>/bloqueos-carpeta             {ruta, usuario_id}: devolverlo

Solo un administrador de la unidad (o el master). La regla está en `bloqueos_carpeta`.
"""
import logging

from flask import Blueprint, jsonify, request

import bloqueos_carpeta as bloqueos
from api_archivos import error, usuario_actual
from registro import registrar_actividad
from roles_unidad import rol_en_unidad

log = logging.getLogger('almacen.api_bloqueos_carpeta')

bp_bloqueos_carpeta = Blueprint('almacen_bloqueos_carpeta', __name__)


def _exigir_admin(usuario, unidad_id):
    if rol_en_unidad(usuario, unidad_id) != 'manager':
        return error('Solo un administrador de la unidad puede gestionar el acceso por carpeta.', 403)
    return None


@bp_bloqueos_carpeta.route('/unidades/<int:unidad_id>/bloqueos-carpeta', methods=['GET'])
def listar_bloqueos(unidad_id):
    usuario = usuario_actual()
    negado = _exigir_admin(usuario, unidad_id)
    if negado:
        return negado
    return jsonify({'success': True,
                    'bloqueos': bloqueos.listar_para_carpeta(unidad_id, request.args.get('ruta') or '/')})


def _datos():
    datos = request.get_json(silent=True) or {}
    ruta = (datos.get('ruta') or '').strip()
    destino = datos.get('usuario_id')
    return ruta, (int(destino) if str(destino or '').isdigit() else None)


@bp_bloqueos_carpeta.route('/unidades/<int:unidad_id>/bloqueos-carpeta', methods=['POST'])
def bloquear(unidad_id):
    usuario = usuario_actual()
    negado = _exigir_admin(usuario, unidad_id)
    if negado:
        return negado
    ruta, destino = _datos()
    if not ruta or ruta.strip('/') == '' or not destino:
        return error('Indique la carpeta y la persona.', 400)
    try:
        r = bloqueos.bloquear(unidad_id, ruta, destino, creado_por=usuario)
    except ValueError as excepcion:
        return error(str(excepcion), 400)
    registrar_actividad(usuario, 'acceso_carpeta_quitado', '/unidades/%s%s' % (unidad_id, r['ruta']),
                        'a %s' % destino)
    log.info('Sin acceso: unidad=%s ruta=%s usuario=%s por %s', unidad_id, r['ruta'], destino, usuario)
    return jsonify({'success': True, 'bloqueo': r}), 201


@bp_bloqueos_carpeta.route('/unidades/<int:unidad_id>/bloqueos-carpeta', methods=['DELETE'])
def desbloquear(unidad_id):
    usuario = usuario_actual()
    negado = _exigir_admin(usuario, unidad_id)
    if negado:
        return negado
    ruta, destino = _datos()
    if not ruta or not destino:
        return error('Indique la carpeta y la persona.', 400)
    bloqueos.desbloquear(unidad_id, ruta, destino)
    registrar_actividad(usuario, 'acceso_carpeta_devuelto', '/unidades/%s/%s' % (unidad_id, ruta.strip('/')),
                        'a %s' % destino)
    log.info('Acceso devuelto: unidad=%s ruta=%s usuario=%s por %s', unidad_id, ruta, destino, usuario)
    return jsonify({'success': True})
