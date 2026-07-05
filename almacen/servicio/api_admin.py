# -*- coding: utf-8 -*-
"""
API de administración del Almacén Maquita — RECUPERACIÓN GLOBAL.
================================================================
Solo usuarios master / master_admin. Permite ver los archivos y la papelera
de CUALQUIER persona y restaurar lo que borró por error, en minutos — sin
depender de un soporte externo que tarda días.

Toda acción queda registrada (auditoría): quién miró/recuperó qué y de quién.

Autoría: Equipo de Tecnología Maquita — 2026-07-03
"""
import logging

from flask import Blueprint, jsonify, request, abort

import nucleo_archivos as nucleo
from almacen_bd import consultar, es_master
from api_archivos import error, usuario_actual

log = logging.getLogger('almacen.admin')

bp_admin = Blueprint('almacen_admin', __name__)


def _exigir_master() -> int:
    """Devuelve el id del usuario si es master; si no, corta con 403."""
    usuario = usuario_actual()
    if not es_master(usuario):
        abort(403)
    return usuario


@bp_admin.route('/admin/usuarios', methods=['GET'])
def admin_buscar_usuarios():
    """
    GET /admin/usuarios?q= — busca personas para elegir de quién recuperar.
    Devuelve id el sistema central (el que usa el Almacén como carpeta), nombre y usuario.
    """
    _exigir_master()
    consulta = (request.args.get('q') or '').strip()
    if len(consulta) < 2:
        return jsonify({'success': True, 'usuarios': []})
    filas = consultar("""
        SELECT u.id, u.username,
               COALESCE(t.nombres || ' ' || t.apellidos, u.full_name, u.username) AS nombre
        FROM usuarios u
        LEFT JOIN trabajadores t ON u.trabajador_id = t.id
        WHERE u.active = TRUE
          AND (LOWER(u.username) LIKE LOWER(%s) || '%%'
               OR LOWER(COALESCE(t.nombres, '')) LIKE LOWER(%s) || '%%'
               OR LOWER(COALESCE(t.apellidos, '')) LIKE LOWER(%s) || '%%')
        ORDER BY u.username LIMIT 15
    """, (consulta, consulta, consulta), nomina=True)
    return jsonify({'success': True, 'usuarios': [dict(f) for f in filas]})


@bp_admin.route('/admin/archivos', methods=['GET'])
def admin_listar_archivos():
    """GET /admin/archivos?usuario_id=X&ruta=/ — explora la unidad de otra persona."""
    admin = _exigir_master()
    objetivo = request.args.get('usuario_id', type=int)
    ruta = request.args.get('ruta', '/')
    if not objetivo:
        return error('usuario_id requerido', 400)
    try:
        carpetas, archivos = nucleo.listar(objetivo, ruta)
    except FileNotFoundError:
        return error('Carpeta no encontrada', 404)
    log.info('[AUDIT] master %s exploró archivos de usuario %s ruta %s', admin, objetivo, ruta)
    return jsonify({'success': True, 'usuario_id': objetivo, 'ruta_actual': ruta,
                    'carpetas': carpetas, 'archivos': archivos,
                    'total_carpetas': len(carpetas), 'total_archivos': len(archivos)})


@bp_admin.route('/admin/papelera', methods=['GET'])
def admin_listar_papelera():
    """GET /admin/papelera?usuario_id=X — papelera de otra persona (lo que borró)."""
    admin = _exigir_master()
    objetivo = request.args.get('usuario_id', type=int)
    if not objetivo:
        return error('usuario_id requerido', 400)
    carpetas, archivos = nucleo.listar_papelera(objetivo)
    log.info('[AUDIT] master %s revisó la papelera de usuario %s', admin, objetivo)
    return jsonify({'success': True, 'usuario_id': objetivo,
                    'carpetas': carpetas, 'archivos': archivos,
                    'total': len(carpetas) + len(archivos)})


@bp_admin.route('/admin/restaurar', methods=['POST'])
def admin_restaurar():
    """
    POST /admin/restaurar — {usuario_id, ruta}
    Restaura un elemento de la PAPELERA de esa persona (por si prefiere que lo
    haga el master). Nota: si el usuario aún tiene el archivo en su papelera,
    normalmente lo recupera él mismo; esto es un apoyo.
    """
    admin = _exigir_master()
    datos = request.get_json() or {}
    objetivo = datos.get('usuario_id')
    identificador = datos.get('ruta')
    if not objetivo or not identificador:
        return error('usuario_id y ruta son requeridos', 400)
    try:
        restaurada = nucleo.restaurar_de_papelera(int(objetivo), identificador)
    except FileNotFoundError:
        return error('No está en la papelera de esa persona', 404)
    log.info('[AUDIT] master %s RESTAURÓ "%s" al usuario %s', admin, restaurada, objetivo)
    return jsonify({'success': True, 'ruta_restaurada': restaurada,
                    'message': f'Recuperado y devuelto a la unidad del usuario {objetivo}'})


@bp_admin.route('/admin/retencion', methods=['GET'])
def admin_listar_retencion():
    """
    GET /admin/retencion?usuario_id=X — lo que un usuario VACIÓ de su papelera
    y sigue recuperable (hasta 90 días). Sin usuario_id: de todos.
    Este es el caso principal de "recuperación en minutos": el usuario ya
    vació su papelera y solo un master puede rescatarlo.
    """
    admin = _exigir_master()
    objetivo = request.args.get('usuario_id', type=int)
    items = nucleo.listar_retencion(objetivo)
    log.info('[AUDIT] master %s consultó retención (usuario %s)', admin, objetivo or 'TODOS')
    return jsonify({'success': True, 'usuario_id': objetivo,
                    'elementos': items, 'total': len(items)})


@bp_admin.route('/admin/retencion/restaurar', methods=['POST'])
def admin_restaurar_retencion():
    """
    POST /admin/retencion/restaurar — {usuario_id, ruta}
    Rescata de la retención (papelera vaciada) y lo devuelve a la unidad del
    dueño. La recuperación que Google demora días y nosotros hacemos en minutos.
    """
    admin = _exigir_master()
    datos = request.get_json() or {}
    objetivo = datos.get('usuario_id')
    identificador = datos.get('ruta')
    if not objetivo or not identificador:
        return error('usuario_id y ruta son requeridos', 400)
    try:
        restaurada = nucleo.restaurar_de_retencion(int(objetivo), identificador)
    except FileNotFoundError:
        return error('No está en la retención de esa persona', 404)
    log.info('[AUDIT] master %s RECUPERÓ de retención "%s" al usuario %s',
             admin, restaurada, objetivo)
    return jsonify({'success': True, 'ruta_restaurada': restaurada,
                    'message': f'Recuperado de la retención y devuelto al usuario {objetivo}'})
