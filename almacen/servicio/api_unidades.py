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

from almacen_bd import consultar, ejecutar, es_master
from api_archivos import error, usuario_actual
from registro import registrar_actividad
from seguridad_rutas import unidad_de_ruta

log = logging.getLogger('almacen.unidades')

bp_unidades = Blueprint('almacen_unidades', __name__)

ROLES = ('manager', 'editor', 'viewer')


def rol_en_unidad(usuario_id, unidad_id):
    """Rol del usuario en la unidad, o None si no es miembro. master ve todo como manager."""
    filas = consultar("SELECT rol FROM unidad_miembros WHERE unidad_id = %s AND usuario_id = %s",
                      (unidad_id, usuario_id))
    if filas:
        return filas[0]['rol']
    return 'manager' if es_master(usuario_id) else None


def permiso_unidad(usuario_id, ruta, escritura=False):
    """¿Puede el usuario leer (o escribir) esta ruta si es de una unidad compartida?
    Devuelve True/False. Para rutas personales devuelve True (no aplica)."""
    unidad_id, _sub = unidad_de_ruta(ruta)
    if unidad_id is None:
        return True   # ruta personal: la seguridad personal ya aplica
    rol = rol_en_unidad(usuario_id, unidad_id)
    if rol is None:
        return False
    if escritura and rol == 'viewer':
        return False
    return True


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
    filas = consultar("""
        SELECT m.usuario_id, m.rol,
               COALESCE(t.nombres || ' ' || t.apellidos, u.full_name, u.username) AS nombre,
               u.username
        FROM unidad_miembros m
        JOIN usuarios u ON u.id = m.usuario_id
        LEFT JOIN trabajadores t ON u.trabajador_id = t.id
        WHERE m.unidad_id = %s ORDER BY m.rol, nombre
    """, (unidad_id,), nomina=True)
    return jsonify({'success': True, 'miembros': [dict(f) for f in filas]})


@bp_unidades.route('/unidades/<int:unidad_id>/miembros', methods=['POST'])
def agregar_miembro(unidad_id):
    """POST — {usuario_id, rol} : agrega/actualiza un miembro (solo manager/master)."""
    usuario = usuario_actual()
    if rol_en_unidad(usuario, unidad_id) != 'manager':
        return error('Solo un manager puede gestionar miembros', 403)
    datos = request.get_json() or {}
    nuevo = datos.get('usuario_id')
    rol = (datos.get('rol') or 'editor').strip()
    if not nuevo or rol not in ROLES:
        return error('usuario_id y rol válido requeridos', 400)
    ejecutar("""
        INSERT INTO unidad_miembros (unidad_id, usuario_id, rol) VALUES (%s, %s, %s)
        ON CONFLICT (unidad_id, usuario_id) DO UPDATE SET rol = EXCLUDED.rol
    """, (unidad_id, int(nuevo), rol))
    return jsonify({'success': True, 'message': 'Miembro agregado'})


@bp_unidades.route('/unidades/<int:unidad_id>/miembros/<int:miembro_id>', methods=['DELETE'])
def quitar_miembro(unidad_id, miembro_id):
    """DELETE — quita un miembro (solo manager/master)."""
    usuario = usuario_actual()
    if rol_en_unidad(usuario, unidad_id) != 'manager':
        return error('Solo un manager puede gestionar miembros', 403)
    ejecutar("DELETE FROM unidad_miembros WHERE unidad_id = %s AND usuario_id = %s",
             (unidad_id, miembro_id))
    return jsonify({'success': True, 'message': 'Miembro removido'})


@bp_unidades.route('/unidades/<int:unidad_id>', methods=['DELETE'])
def eliminar_unidad(unidad_id):
    """DELETE — elimina la unidad (solo master; borra su registro, no los archivos físicos)."""
    usuario = usuario_actual()
    if not es_master(usuario):
        return error('Solo un master puede eliminar unidades', 403)
    ejecutar("DELETE FROM unidades_compartidas WHERE id = %s", (unidad_id,))
    return jsonify({'success': True, 'message': 'Unidad eliminada'})
