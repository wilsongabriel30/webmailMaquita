# -*- coding: utf-8 -*-
"""
Información del grupo: permisos de edición, administradores y foto (T-94, 09/11/2026).
=======================================================================================
Se suma a `grupos_api.py` (mismo blueprint, se importa al final de ese módulo):

    PUT    /api/chat/conversations/<id>/grupo/permisos      {edicion: 'admins'|'todos'}  → solo administradores
    PUT    /api/chat/conversations/<id>/miembros/<uid>/rol  {admin: true|false}          → solo administradores
    DELETE /api/chat/conversations/<id>/avatar                                            → quien pueda editar

Quién puede cambiar nombre, descripción y foto: por omisión, los administradores (quien creó el grupo y los
nombrados administradores). Un administrador puede abrirlo a «todos los miembros», como en WhatsApp. La preferencia
vive en `chat_conversations.settings.edicion`.
"""
import json

import psycopg2.extras
from flask import jsonify, request

from interfaces.api.grupos_api import NOTAS_DESC, _conexion, _emitir, _es_admin, _es_miembro, _uid, bp_grupos

EDICION_VALIDAS = ('admins', 'todos')


def edicion_de(cur, conv_id):
    cur.execute("SELECT COALESCE(settings->>'edicion', 'admins') FROM chat_conversations WHERE id=%s", (conv_id,))
    fila = cur.fetchone()
    valor = fila[0] if fila else 'admins'
    return valor if valor in EDICION_VALIDAS else 'admins'


def puede_editar(cur, conv_id, uid):
    """Administrador, o miembro si el grupo permite que todos editen."""
    if _es_admin(cur, conv_id, uid):
        return True
    return edicion_de(cur, conv_id) == 'todos' and _es_miembro(cur, conv_id, uid)


@bp_grupos.route('/<int:conv_id>/grupo/permisos', methods=['PUT'])
def cambiar_permisos(conv_id):
    uid = _uid()
    if not uid:
        return jsonify({'success': False, 'error': 'No autenticado'}), 401
    edicion = ((request.get_json(silent=True) or {}).get('edicion') or '').strip()
    if edicion not in EDICION_VALIDAS:
        return jsonify({'success': False, 'error': "Valor no válido: use 'admins' o 'todos'"}), 400
    with _conexion() as con, con.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
        if not _es_admin(cur, conv_id, uid):
            return jsonify({'success': False, 'error': 'Solo un administrador puede cambiar quién edita el grupo'}), 403
        cur.execute("""UPDATE chat_conversations
                          SET settings = COALESCE(settings, '{}'::jsonb) || %s::jsonb, updated_at = NOW()
                        WHERE id=%s AND conversation_type='group' AND COALESCE(description,'') <> %s RETURNING id""",
                    (json.dumps({'edicion': edicion}), conv_id, NOTAS_DESC))
        if not cur.fetchone():
            return jsonify({'success': False, 'error': 'Grupo no encontrado'}), 404
    _emitir(conv_id, 'conversation_updated', {'conversation_id': conv_id, 'edicion': edicion, 'by': uid})
    return jsonify({'success': True, 'edicion': edicion})


@bp_grupos.route('/<int:conv_id>/miembros/<int:miembro_id>/rol', methods=['PUT'])
def cambiar_rol(conv_id, miembro_id):
    uid = _uid()
    if not uid:
        return jsonify({'success': False, 'error': 'No autenticado'}), 401
    hacer_admin = bool((request.get_json(silent=True) or {}).get('admin'))
    with _conexion() as con, con.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
        if not _es_admin(cur, conv_id, uid):
            return jsonify({'success': False, 'error': 'Solo un administrador puede nombrar o quitar administradores'}), 403
        cur.execute("SELECT created_by FROM chat_conversations WHERE id=%s AND conversation_type='group'", (conv_id,))
        conv = cur.fetchone()
        if not conv:
            return jsonify({'success': False, 'error': 'Grupo no encontrado'}), 404
        if not hacer_admin and miembro_id == conv['created_by']:
            return jsonify({'success': False, 'error': 'Quien creó el grupo siempre es administrador'}), 400
        if not _es_miembro(cur, conv_id, miembro_id):
            return jsonify({'success': False, 'error': 'Esa persona no es miembro del grupo'}), 404
        cur.execute("UPDATE chat_participants SET role=%s WHERE conversation_id=%s AND user_id=%s AND is_active",
                    ('admin' if hacer_admin else 'member', conv_id, miembro_id))
    _emitir(conv_id, 'conversation_updated', {'conversation_id': conv_id, 'miembro_id': miembro_id,
                                              'admin': hacer_admin, 'by': uid})
    return jsonify({'success': True, 'miembro_id': miembro_id, 'admin': hacer_admin})


@bp_grupos.route('/<int:conv_id>/avatar', methods=['DELETE'])
def quitar_avatar(conv_id):
    uid = _uid()
    if not uid:
        return jsonify({'success': False, 'error': 'No autenticado'}), 401
    with _conexion() as con, con.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
        if not puede_editar(cur, conv_id, uid):
            return jsonify({'success': False, 'error': 'No tienes permiso para cambiar la foto de este grupo'}), 403
        cur.execute("UPDATE chat_conversations SET avatar_path=NULL, updated_at=NOW() WHERE id=%s AND conversation_type='group' RETURNING id",
                    (conv_id,))
        if not cur.fetchone():
            return jsonify({'success': False, 'error': 'Grupo no encontrado'}), 404
    _emitir(conv_id, 'conversation_updated', {'conversation_id': conv_id, 'avatar': None, 'by': uid})
    return jsonify({'success': True, 'avatar': None})
