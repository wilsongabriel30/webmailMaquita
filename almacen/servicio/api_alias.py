# -*- coding: utf-8 -*-
"""
API de administración de alias de correo.
=========================================
Solo administradores (las rutas van bajo /admin/ → el candado de la app
exige rol master, y aquí se re-valida por defensa en profundidad).

| Método | Ruta                      | Cuerpo / query                    |
|--------|---------------------------|-----------------------------------|
| GET    | /admin/alias-correo       | —  (lista todos)                  |
| POST   | /admin/alias-correo       | {"alias": "...", "canonico": "..."} |
| DELETE | /admin/alias-correo       | ?alias=...                        |

Ejemplo (con la cookie de un administrador):
  curl -X POST https://SU-DOMINIO/api/almacen/admin/alias-correo \
       -H 'Content-Type: application/json' \
       -d '{"alias":"usuario@dominio.org","canonico":"usuario@dominio.com.ec"}'
"""
from flask import Blueprint, jsonify, request

import alias_correo
from almacen_bd import es_master
from api_archivos import usuario_actual

bp_alias = Blueprint('almacen_alias', __name__)


def _exigir_master():
    return es_master(usuario_actual())


@bp_alias.route('/admin/alias-correo', methods=['GET'])
def listar():
    """GET /admin/alias-correo — todos los alias registrados."""
    if not _exigir_master():
        return jsonify({'success': False, 'error': 'No autorizado'}), 403
    return jsonify({'success': True, 'alias': alias_correo.listar_alias()})


@bp_alias.route('/admin/alias-correo', methods=['POST'])
def crear():
    """POST /admin/alias-correo — {alias, canonico}."""
    if not _exigir_master():
        return jsonify({'success': False, 'error': 'No autorizado'}), 403
    datos = request.get_json() or {}
    ok, mensaje = alias_correo.crear_alias(datos.get('alias'), datos.get('canonico'))
    if not ok:
        return jsonify({'success': False, 'error': mensaje}), 400
    return jsonify({'success': True, 'message': mensaje}), 201


@bp_alias.route('/admin/alias-correo', methods=['DELETE'])
def eliminar():
    """DELETE /admin/alias-correo?alias=... — elimina un alias."""
    if not _exigir_master():
        return jsonify({'success': False, 'error': 'No autorizado'}), 403
    if not alias_correo.eliminar_alias(request.args.get('alias', '')):
        return jsonify({'success': False, 'error': 'Alias no encontrado'}), 404
    return jsonify({'success': True, 'message': 'Alias eliminado'})
