# -*- coding: utf-8 -*-
"""
Grupos y «Mis notas» (Teams Maquita T-09 / T-12).
==================================================
    POST /api/chat/conversations/notas                → obtiene o crea el chat con uno mismo («Mis notas»)
    GET  /api/chat/conversations/<id>/grupo           → detalle editable del grupo (miembros, roles, foto)
    PUT  /api/chat/conversations/<id>/grupo           → renombrar / descripción (solo administradores)
    POST /api/chat/conversations/<id>/avatar          → foto del grupo (png/jpg/webp ≤ 5 MB), solo administradores
Agregar/quitar miembros y salir: endpoints ya existentes (`/participants`, `/leave`).
"""
import os
import uuid
from datetime import datetime

import psycopg2
import psycopg2.extras
from flask import Blueprint, jsonify, request, session

bp_grupos = Blueprint('grupos_chat', __name__, url_prefix='/api/chat/conversations')

_BASE = os.path.dirname(os.path.abspath(__file__))
DIR_FOTOS = os.path.normpath(os.path.join(_BASE, '..', 'web', 'estaticos', 'grupos'))
URL_FOTOS = '/static/grupos'
NOTAS_DESC = 'notas-personales'
MAGIC = {b'\x89PNG': '.png', b'\xff\xd8\xff': '.jpg', b'RIFF': '.webp', b'GIF8': '.gif'}


def _conexion():
    return psycopg2.connect(os.environ['DATABASE_URL'])


def _uid():
    u = session.get('usuario_id')
    return int(u) if u else None


def _emitir(conv_id, evento, datos):
    try:
        from interfaces.websocket.manejador_websocket import emitir_a_conversacion
        emitir_a_conversacion(conv_id, evento, datos)
    except Exception:
        pass


def _es_admin(cur, conv_id, uid):
    cur.execute("""SELECT 1 FROM chat_conversations c
                   LEFT JOIN chat_participants p ON p.conversation_id = c.id AND p.user_id = %s AND p.is_active
                   WHERE c.id = %s AND (c.created_by = %s OR lower(COALESCE(p.role,'')) IN ('admin','owner','administrador'))""",
                (uid, conv_id, uid))
    return cur.fetchone() is not None


def _es_miembro(cur, conv_id, uid):
    cur.execute("SELECT 1 FROM chat_participants WHERE conversation_id=%s AND user_id=%s AND is_active", (conv_id, uid))
    return cur.fetchone() is not None


# ---------------------------------------------------------------- Mis notas
@bp_grupos.route('/notas', methods=['POST'])
def notas():
    uid = _uid()
    if not uid:
        return jsonify({'success': False, 'error': 'No autenticado'}), 401
    with _conexion() as con, con.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
        cur.execute("""SELECT c.id, c.name FROM chat_conversations c
                       JOIN chat_participants p ON p.conversation_id = c.id AND p.user_id = %s AND p.is_active
                       WHERE c.conversation_type = 'group' AND c.description = %s AND c.is_active
                       ORDER BY c.id LIMIT 1""", (uid, NOTAS_DESC))
        fila = cur.fetchone()
        creada = False
        if not fila:
            cur.execute("""INSERT INTO chat_conversations (public_id, conversation_type, name, description, created_by, created_at, updated_at, is_active)
                           VALUES (%s, 'group', 'Mis notas', %s, %s, NOW(), NOW(), TRUE) RETURNING id, name""",
                        (str(uuid.uuid4()), NOTAS_DESC, uid))
            fila = cur.fetchone()
            cur.execute("""INSERT INTO chat_participants (conversation_id, user_id, role, is_active, joined_at, unread_count)
                           VALUES (%s, %s, 'admin', TRUE, NOW(), 0)""", (fila['id'], uid))
            creada = True
    return jsonify({'success': True, 'id': fila['id'], 'nombre': 'Mis notas', 'creada': creada, 'notas': True})


# ---------------------------------------------------------------- Detalle / edición de grupo
@bp_grupos.route('/<int:conv_id>/grupo', methods=['GET'])
def detalle(conv_id):
    uid = _uid()
    if not uid:
        return jsonify({'success': False, 'error': 'No autenticado'}), 401
    with _conexion() as con, con.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
        if not _es_miembro(cur, conv_id, uid):
            return jsonify({'success': False, 'error': 'No eres miembro de este grupo'}), 403
        cur.execute("SELECT id, name, description, avatar_path, created_by, created_at FROM chat_conversations WHERE id=%s AND conversation_type='group'", (conv_id,))
        c = cur.fetchone()
        if not c:
            return jsonify({'success': False, 'error': 'Grupo no encontrado'}), 404
        cur.execute("""SELECT p.user_id, p.role, u.email, COALESCE(NULLIF(TRIM(u.full_name), ''), u.username, u.email) AS nombre, u.profile_picture
                       FROM chat_participants p JOIN usuarios u ON u.id = p.user_id
                       WHERE p.conversation_id = %s AND p.is_active ORDER BY nombre""", (conv_id,))
        miembros = []
        for m in cur.fetchall():
            foto = (m['profile_picture'] or '').strip()
            if foto and not foto.startswith(('http', '/')):
                foto = '/static/uploads/profiles/' + foto if not foto.startswith('uploads/') else '/static/' + foto
            miembros.append({'id': m['user_id'], 'nombre': m['nombre'], 'email': m['email'], 'foto': foto or None,
                             'rol': (m['role'] or 'miembro'), 'es_yo': m['user_id'] == uid,
                             'es_admin': m['user_id'] == c['created_by'] or (m['role'] or '').lower() in ('admin', 'owner', 'administrador')})
        soy_admin = _es_admin(cur, conv_id, uid)
    return jsonify({'success': True, 'grupo': {
        'id': c['id'], 'nombre': c['name'], 'descripcion': c['description'] or '', 'avatar': c['avatar_path'],
        'creado_por': c['created_by'], 'notas': c['description'] == NOTAS_DESC, 'miembros': miembros, 'soy_admin': soy_admin}})


@bp_grupos.route('/<int:conv_id>/grupo', methods=['PUT'])
def editar(conv_id):
    uid = _uid()
    if not uid:
        return jsonify({'success': False, 'error': 'No autenticado'}), 401
    d = request.get_json(silent=True) or {}
    nombre = (d.get('nombre') or d.get('name') or '').strip()[:60]
    descripcion = (d.get('descripcion') or d.get('description') or '').strip()[:120]
    if not nombre:
        return jsonify({'success': False, 'error': 'El nombre es obligatorio'}), 400
    with _conexion() as con, con.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
        if not _es_admin(cur, conv_id, uid):
            return jsonify({'success': False, 'error': 'Solo un administrador del grupo puede editarlo'}), 403
        cur.execute("SELECT description FROM chat_conversations WHERE id=%s", (conv_id,))
        act = cur.fetchone()
        if act and act['description'] == NOTAS_DESC:
            descripcion = NOTAS_DESC   # el chat de notas conserva su marca
        cur.execute("UPDATE chat_conversations SET name=%s, description=%s, updated_at=NOW() WHERE id=%s AND conversation_type='group' RETURNING id",
                    (nombre, descripcion, conv_id))
        if not cur.fetchone():
            return jsonify({'success': False, 'error': 'Grupo no encontrado'}), 404
    _emitir(conv_id, 'conversation_updated', {'conversation_id': conv_id, 'name': nombre, 'description': descripcion, 'by': uid})
    return jsonify({'success': True, 'grupo': {'id': conv_id, 'nombre': nombre, 'descripcion': descripcion}})


@bp_grupos.route('/<int:conv_id>/avatar', methods=['POST'])
def avatar(conv_id):
    uid = _uid()
    if not uid:
        return jsonify({'success': False, 'error': 'No autenticado'}), 401
    f = request.files.get('file') or request.files.get('avatar')
    if not f:
        return jsonify({'success': False, 'error': 'Falta el archivo'}), 400
    datos = f.read()
    if len(datos) > 5 * 1024 * 1024:
        return jsonify({'success': False, 'error': 'La imagen supera los 5 MB'}), 400
    ext = next((e for m, e in MAGIC.items() if datos.startswith(m)), None)
    if not ext:
        return jsonify({'success': False, 'error': 'Formato no válido (png, jpg, webp, gif)'}), 400
    with _conexion() as con, con.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
        if not _es_admin(cur, conv_id, uid):
            return jsonify({'success': False, 'error': 'Solo un administrador del grupo puede cambiar la foto'}), 403
        os.makedirs(DIR_FOTOS, exist_ok=True)
        nombre = f"{conv_id}_{uuid.uuid4().hex[:10]}{ext}"
        with open(os.path.join(DIR_FOTOS, nombre), 'wb') as out:
            out.write(datos)
        url = f"{URL_FOTOS}/{nombre}"
        cur.execute("UPDATE chat_conversations SET avatar_path=%s, updated_at=NOW() WHERE id=%s RETURNING id", (url, conv_id))
        if not cur.fetchone():
            return jsonify({'success': False, 'error': 'Grupo no encontrado'}), 404
    _emitir(conv_id, 'conversation_updated', {'conversation_id': conv_id, 'avatar': url, 'by': uid})
    return jsonify({'success': True, 'avatar': url})


# ---------------------------------------------------------------- Identidad del usuario (riel de la app)
from flask import Blueprint as _Bp
bp_yo = _Bp('yo_chat', __name__, url_prefix='/api/chat')


@bp_yo.route('/yo', methods=['GET'])
def yo():
    """Quién soy: nombre, correo, avatar (URL absoluta) para el riel/perfil del cliente de escritorio."""
    uid = _uid()
    if not uid:
        return jsonify({'success': False, 'error': 'No autenticado'}), 401
    from interfaces.websocket.notificaciones_globales import avatar_usuario, URL_BASE
    with _conexion() as con, con.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
        cur.execute("""SELECT id, email, username, role, COALESCE(NULLIF(TRIM(full_name), ''), username, email) AS nombre
                       FROM usuarios WHERE id = %s""", (uid,))
        u = cur.fetchone()
    if not u:
        return jsonify({'success': False, 'error': 'Usuario no encontrado'}), 404
    nombre = u['nombre'] or ''
    iniciales = ''.join(p[0] for p in nombre.split()[:2]).upper() or (u['email'] or 'U')[:1].upper()
    return jsonify({'success': True, 'usuario': {
        'id': u['id'], 'nombre': nombre, 'correo': u['email'], 'usuario': u['username'], 'rol': u['role'],
        'iniciales': iniciales, 'avatar': avatar_usuario(uid),
        'perfil_url': 'https://datos.maquita.com.ec/auth/perfil?app=1', 'chat_url': URL_BASE + '/chat/'}})
