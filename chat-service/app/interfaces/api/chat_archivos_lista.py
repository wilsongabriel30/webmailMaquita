# -*- coding: utf-8 -*-
"""Lista de archivos del chat (T-101, 11/11/2026).

La pestaña «Archivos» de una conversación y la sección «Archivos» necesitan TODOS los archivos, no solo los de los
mensajes cargados en pantalla. Aquí se sacan de `chat_message_media`, solo para conversaciones donde la persona participa.

- GET /api/chat/conversations/<id>/archivos   (alias /conversaciones/<id>/archivos)  → archivos de esa conversación
- GET /api/chat/archivos                                                              → de todas mis conversaciones
  Parámetros: clase = archivos | fotos | todos (por defecto «archivos»), q = texto del nombre, limite (1-100, por
  defecto 50), desde = id del último recibido (para pedir los siguientes).
- GET /chat/archivos                                                                  → la página de la sección

Reglas que se respetan: mensajes borrados fuera; lo anterior a «vaciar conversación» de esa persona fuera; y los adjuntos
que la persona quitó de su Drive (papelera o eliminado) fuera, igual que en el hilo. Cada archivo lleva la ruta de su
reflejo en el Drive de quien consulta, si existe. Solo lectura: no modifica nada.
"""
import os
import re

import psycopg2
import psycopg2.extras
from flask import Blueprint, jsonify, render_template, request

from interfaces.api.chat_base import bp_chat, obtener_usuario_id, requiere_autenticacion

bp_archivos_pagina = Blueprint('chat_archivos_pagina', __name__)

CLASES = {
    'fotos': "md.media_type IN ('image', 'video')",
    'archivos': "md.media_type NOT IN ('image', 'video', 'gif')",
    'todos': "md.media_type <> 'gif'",
}
_PREFIJO_FECHA = re.compile(r'^(\d{8}_\d{9,}_)+')


def _conexion():
    return psycopg2.connect(os.environ['DATABASE_URL'])


def _basename(ruta):
    return (ruta or '').replace('\\', '/').rstrip('/').split('/')[-1]


def _nombre_visible(nombre, ruta):
    """El nombre con el que se envió, sin la marca de fecha que el chat antepone al guardarlo."""
    n = (nombre or '').strip() or _basename(ruta)
    return _PREFIJO_FECHA.sub('', n) or n


def _entero(valor, defecto, minimo, maximo):
    try:
        return max(minimo, min(maximo, int(valor)))
    except (TypeError, ValueError):
        return defecto


def _listar(usuario_id, conversacion_id=None):
    clase = (request.args.get('clase') or 'archivos').strip().lower()
    if clase not in CLASES:
        clase = 'archivos'
    texto = (request.args.get('q') or '').strip()[:80]
    limite = _entero(request.args.get('limite'), 50, 1, 100)
    desde = _entero(request.args.get('desde'), 0, 0, 2 ** 62)

    donde = ["p.user_id = %s", "p.is_active", "NOT COALESCE(m.is_deleted, FALSE)",
             "(p.cleared_at IS NULL OR m.created_at > p.cleared_at)", CLASES[clase]]
    valores = [usuario_id]
    if conversacion_id is not None:
        donde.append("m.conversation_id = %s"); valores.append(conversacion_id)
    if texto:
        donde.append("md.file_name ILIKE %s"); valores.append('%' + texto.replace('%', r'\%').replace('_', r'\_') + '%')
    if desde:
        donde.append("md.id < %s"); valores.append(desde)

    with _conexion() as con, con.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
        if conversacion_id is not None:
            cur.execute("SELECT 1 FROM chat_participants WHERE conversation_id = %s AND user_id = %s AND is_active",
                        (conversacion_id, usuario_id))
            if not cur.fetchone():
                return None
        # lo que esta persona quitó de su Drive no se le enseña (mismo criterio que en el hilo)
        cur.execute("""SELECT DISTINCT nombre_chat FROM chat_media_drive
                       WHERE usuario_id = %s AND estado IN ('papelera', 'eliminado')""", (usuario_id,))
        ocultos = {f[0] for f in cur.fetchall()}
        cur.execute(f"""
            SELECT md.id, md.message_id, md.media_type, md.file_path, md.file_name, md.file_size, md.mime_type, md.created_at,
                   m.conversation_id, m.sender_id,
                   COALESCE(NULLIF(TRIM(u.full_name), ''), u.username, 'Usuario') AS remitente,
                   c.name AS conv_nombre, c.conversation_type, c.description AS conv_descripcion
            FROM chat_message_media md
            JOIN chat_messages m ON m.id = md.message_id
            JOIN chat_participants p ON p.conversation_id = m.conversation_id
            JOIN chat_conversations c ON c.id = m.conversation_id
            LEFT JOIN usuarios u ON u.id = m.sender_id
            WHERE {' AND '.join(donde)}
            ORDER BY md.id DESC
            LIMIT %s""", valores + [limite + 1 + len(ocultos)])
        filas = [f for f in cur.fetchall() if _basename(f['file_path']) not in ocultos]
        hay_mas = len(filas) > limite
        filas = filas[:limite]

        convs = sorted({f['conversation_id'] for f in filas})
        nombres_directos, rutas_drive = {}, {}
        if convs:
            cur.execute("""SELECT p.conversation_id, COALESCE(NULLIF(TRIM(u.full_name), ''), u.username) AS nombre
                           FROM chat_participants p JOIN usuarios u ON u.id = p.user_id
                           WHERE p.conversation_id = ANY(%s) AND p.user_id <> %s AND p.is_active""", (convs, usuario_id))
            for f in cur.fetchall():
                nombres_directos.setdefault(f['conversation_id'], f['nombre'])
            cur.execute("""SELECT conversation_id, nombre_chat, ruta_drive FROM chat_media_drive
                           WHERE usuario_id = %s AND estado = 'activo' AND conversation_id = ANY(%s)""", (usuario_id, convs))
            for f in cur.fetchall():
                rutas_drive[(f['conversation_id'], f['nombre_chat'])] = f['ruta_drive']

    def nombre_conversacion(f):
        if f['conv_descripcion'] == 'notas-personales':
            return 'Mis notas'
        if f['conversation_type'] == 'group':
            return f['conv_nombre'] or 'Grupo'
        return nombres_directos.get(f['conversation_id']) or 'Chat'

    archivos = [{
        'id': f['id'],
        'mensaje_id': f['message_id'],
        'conversacion_id': f['conversation_id'],
        'conversacion': nombre_conversacion(f),
        'nombre': _nombre_visible(f['file_name'], f['file_path']),
        'clase': f['media_type'],
        'tipo_mime': f['mime_type'] or '',
        'bytes': int(f['file_size'] or 0),
        'url': '/' + (f['file_path'] or '').lstrip('/'),
        'remitente': f['remitente'],
        'propio': f['sender_id'] == usuario_id,
        'fecha': f['created_at'].isoformat() if f['created_at'] else None,
        'ruta_drive': rutas_drive.get((f['conversation_id'], _basename(f['file_path']))),
    } for f in filas]
    return {'exito': True, 'success': True, 'archivos': archivos, 'hay_mas': hay_mas,
            'siguiente': archivos[-1]['id'] if (hay_mas and archivos) else None}


@bp_chat.route('/conversations/<int:conversacion_id>/archivos', methods=['GET'])
@bp_chat.route('/conversaciones/<int:conversacion_id>/archivos', methods=['GET'])
@requiere_autenticacion
def archivos_de_conversacion(conversacion_id: int):
    try:
        datos = _listar(obtener_usuario_id(), conversacion_id)
    except Exception as e:
        print(f'[chat-archivos] error: {e}')
        return jsonify({'exito': False, 'success': False, 'mensaje': 'No se pudo obtener la lista de archivos'}), 500
    if datos is None:
        return jsonify({'exito': False, 'success': False, 'mensaje': 'No tienes acceso a esta conversacion'}), 403
    return jsonify(datos)


@bp_chat.route('/archivos', methods=['GET'])
@requiere_autenticacion
def archivos_de_mis_conversaciones():
    try:
        return jsonify(_listar(obtener_usuario_id()))
    except Exception as e:
        print(f'[chat-archivos] error: {e}')
        return jsonify({'exito': False, 'success': False, 'mensaje': 'No se pudo obtener la lista de archivos'}), 500


@bp_archivos_pagina.route('/chat/archivos')
def pagina_archivos():
    """Sección «Archivos». La sesión la valida el before_request del servicio, como en el resto de páginas del chat."""
    return render_template('chat/archivos.html')
