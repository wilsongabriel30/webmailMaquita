# -*- coding: utf-8 -*-
"""
API de UNIDADES COMPARTIDAS del Almacén Maquita.
================================================
Drives de equipo, propiedad de la ORGANIZACIÓN (no de una persona), con miembros
y roles — el equivalente a las "Unidades compartidas" de Google Drive / SharePoint
(que Drive cobra desde Business Standard). Aquí, gratis.

Roles: manager (gestiona miembros y todo), editor (sube/edita/borra), viewer (solo ve).

Autoría: Equipo de Tecnología Maquita — 2026-07-03
"""
import logging

from flask import Blueprint, jsonify, request

from almacen_bd import consultar, ejecutar, es_master, conexion
import gobierno_unidad
from api_archivos import error, usuario_actual
from registro import registrar_actividad
from seguridad_rutas import unidad_de_ruta

log = logging.getLogger('almacen.unidades')

bp_unidades = Blueprint('almacen_unidades', __name__)

ROLES = ('manager', 'editor', 'viewer')


# La regla vive en `permisos_unidad` (sin Flask): la usa también seguridad_rutas.
# Se reexporta para que todo lo que ya la llamaba siga igual.
from permisos_unidad import permiso_unidad, rol_en_unidad   # noqa: F401,E402


@bp_unidades.route('/unidades', methods=['GET'])
def listar_unidades():
    """GET /unidades — unidades compartidas donde soy miembro (con mi rol)."""
    usuario = usuario_actual()
    filas = consultar("""
        SELECT u.id, u.nombre, u.creado_en, m.rol,
               (SELECT COUNT(*) FROM unidad_miembros mm WHERE mm.unidad_id = u.id) AS miembros
        FROM unidades_compartidas u
        JOIN unidad_miembros m ON m.unidad_id = u.id
        WHERE m.usuario_id = %s
        ORDER BY u.nombre
    """, (usuario,))
    return jsonify({'success': True, 'unidades': [{
        'id': f['id'], 'nombre': f['nombre'], 'mi_rol': f['rol'],
        'miembros': f['miembros'], 'ruta': f'/unidades/{f["id"]}',
        'creado_en': f['creado_en'].isoformat(),
    } for f in filas]})


@bp_unidades.route('/unidades', methods=['POST'])
def crear_unidad():
    """POST /unidades — {nombre} : crea una unidad compartida (solo master). El creador
    queda como manager."""
    usuario = usuario_actual()
    if not es_master(usuario):
        return error('Solo un master puede crear unidades compartidas', 403)
    datos = request.get_json() or {}
    nombre = (datos.get('nombre') or '').strip()[:150]
    if not nombre:
        return error('Nombre requerido', 400)
    fila = ejecutar("INSERT INTO unidades_compartidas (nombre, creado_por) VALUES (%s, %s) RETURNING id",
                    (nombre, usuario))
    ejecutar("INSERT INTO unidad_miembros (unidad_id, usuario_id, rol) VALUES (%s, %s, 'manager')",
             (fila['id'], usuario))
    registrar_actividad(usuario, 'creo_carpeta', f'/unidades/{fila["id"]}', f'Unidad: {nombre}')
    return jsonify({'success': True, 'id': fila['id'], 'nombre': nombre,
                    'ruta': f'/unidades/{fila["id"]}'}), 201


@bp_unidades.route('/unidades/<int:unidad_id>/miembros', methods=['GET'])
def listar_miembros(unidad_id):
    """GET — miembros de la unidad (cualquier miembro puede ver la lista)."""
    usuario = usuario_actual()
    if rol_en_unidad(usuario, unidad_id) is None:
        return error('No eres miembro de esta unidad', 403)
    # Dos consultas: la membresía vive en la BD del almacén y los nombres en el
    # directorio (otra BD) — no se pueden JOINear entre bases en PostgreSQL.
    membresia = consultar("""
        SELECT usuario_id, rol FROM unidad_miembros WHERE unidad_id = %s
    """, (unidad_id,))
    if not membresia:
        return jsonify({'success': True, 'miembros': []})
    ids = tuple({int(m['usuario_id']) for m in membresia})
    personas = consultar("""
        SELECT u.id, u.username,
               COALESCE(t.nombres || ' ' || t.apellidos, u.full_name, u.username) AS nombre
        FROM usuarios u
        LEFT JOIN trabajadores t ON u.trabajador_id = t.id
        WHERE u.id IN %s
    """, (ids,), nomina=True)
    por_id = {p['id']: p for p in personas}
    miembros = [{
        'usuario_id': m['usuario_id'], 'rol': m['rol'],
        'nombre': (por_id.get(m['usuario_id']) or {}).get('nombre') or f"Usuario {m['usuario_id']}",
        'username': (por_id.get(m['usuario_id']) or {}).get('username') or '',
    } for m in membresia]
    miembros.sort(key=lambda x: (x['rol'], x['nombre'].lower()))
    return jsonify({'success': True, 'miembros': miembros})


@bp_unidades.route('/unidades/<int:unidad_id>/miembros', methods=['POST'])
def agregar_miembro(unidad_id):
    """POST — {usuario_id, rol} : agrega/actualiza un miembro. Puede un manager de la unidad
    o, como override explícito, un master. [F-11] Degradar al ÚLTIMO manager se rechaza (409)."""
    usuario = usuario_actual()
    if not (es_master(usuario) or rol_en_unidad(usuario, unidad_id) == 'manager'):
        return error('Solo un manager (o un master) puede gestionar miembros', 403)
    datos = request.get_json() or {}
    nuevo = datos.get('usuario_id')
    rol = (datos.get('rol') or 'editor').strip()
    if not nuevo or rol not in ROLES:
        return error('usuario_id y rol válido requeridos', 400)
    try:
        gobierno_unidad.asignar_rol(conexion, unidad_id, int(nuevo), rol)
    except gobierno_unidad.UltimoManager:
        return error('No puedes degradar al último manager de la unidad: nombra otro primero', 409)
    return jsonify({'success': True, 'message': 'Miembro agregado'})


@bp_unidades.route('/unidades/<int:unidad_id>/miembros/<int:miembro_id>', methods=['DELETE'])
def quitar_miembro(unidad_id, miembro_id):
    """DELETE — quita un miembro (manager de la unidad o, como override explícito, un master).
    [F-11] Quitar al ÚLTIMO manager (incluido uno mismo) se rechaza (409)."""
    usuario = usuario_actual()
    if not (es_master(usuario) or rol_en_unidad(usuario, unidad_id) == 'manager'):
        return error('Solo un manager (o un master) puede gestionar miembros', 403)
    try:
        gobierno_unidad.quitar(conexion, unidad_id, int(miembro_id))
    except gobierno_unidad.UltimoManager:
        return error('No puedes quitar al último manager de la unidad: nombra otro primero', 409)
    return jsonify({'success': True, 'message': 'Miembro removido'})


@bp_unidades.route('/unidades/<int:unidad_id>', methods=['DELETE'])
def eliminar_unidad(unidad_id):
    """DELETE — elimina la unidad (solo master; borra su registro, no los archivos físicos)."""
    usuario = usuario_actual()
    if not es_master(usuario):
        return error('Solo un master puede eliminar unidades', 403)
    ejecutar("DELETE FROM unidades_compartidas WHERE id = %s", (unidad_id,))
    return jsonify({'success': True, 'message': 'Unidad eliminada'})
