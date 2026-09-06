# -*- coding: utf-8 -*-
"""
T-18 fase 2 — sincronía Drive ↔ chat.
=====================================
- Tabla `chat_media_drive`: qué archivo del chat está reflejado en qué ruta del Drive de cada usuario y su estado
  (`activo` | `papelera` | `eliminado`). La escribe `drive_chat` al reflejar.
- `POST /api/chat/drive/evento` (cabecera X-Notif-Secret, solo el Almacén): {usuario_id, ruta, evento} cuando el
  usuario manda a la papelera / restaura / elimina algo de «Archivos del chat». Actualiza el estado y avisa al usuario
  por el canal `notificacion`.
- `aplicar_ocultos(mensajes, usuario_id)`: en el listado, para ESE usuario, oculta los adjuntos que él quitó de su
  Drive (los demás participantes los siguen viendo) y deja una marca en el mensaje.
"""
import hmac
import os
import re

import psycopg2
import psycopg2.extras
from flask import Blueprint, jsonify, request

bp_drive_eventos = Blueprint('drive_eventos_chat', __name__, url_prefix='/api/chat/drive')
CARPETA = '/Archivos del chat'


def _conexion():
    return psycopg2.connect(os.environ['DATABASE_URL'])


def asegurar_tabla():
    with _conexion() as con, con.cursor() as cur:
        cur.execute("""CREATE TABLE IF NOT EXISTS chat_media_drive (
                           id SERIAL PRIMARY KEY,
                           usuario_id INTEGER NOT NULL,
                           conversation_id INTEGER NOT NULL,
                           nombre_chat VARCHAR(300) NOT NULL,      -- nombre del archivo como quedó en el chat (basename de file_path)
                           ruta_drive TEXT NOT NULL,               -- ruta virtual en el Drive del usuario
                           estado VARCHAR(20) NOT NULL DEFAULT 'activo',
                           creado_en TIMESTAMP NOT NULL DEFAULT NOW(),
                           actualizado_en TIMESTAMP NOT NULL DEFAULT NOW());
                       CREATE INDEX IF NOT EXISTS ix_cmd_usuario_conv ON chat_media_drive (usuario_id, conversation_id, estado);
                       CREATE INDEX IF NOT EXISTS ix_cmd_ruta ON chat_media_drive (usuario_id, ruta_drive);""")


def registrar_vinculo(usuario_id, conversation_id, nombre_chat, ruta_drive):
    try:
        with _conexion() as con, con.cursor() as cur:
            cur.execute("""INSERT INTO chat_media_drive (usuario_id, conversation_id, nombre_chat, ruta_drive, estado)
                           VALUES (%s, %s, %s, %s, 'activo')""", (usuario_id, conversation_id, nombre_chat, ruta_drive))
    except Exception as e:
        print(f'[drive-chat] no se pudo registrar el vínculo: {e}')


def _basename(p):
    return (p or '').replace('\\', '/').rstrip('/').split('/')[-1]


def aplicar_ocultos(mensajes, usuario_id):
    """Oculta, para `usuario_id`, los adjuntos que él envió a la papelera/eliminó de su Drive."""
    try:
        with _conexion() as con, con.cursor() as cur:
            cur.execute("""SELECT DISTINCT nombre_chat FROM chat_media_drive
                           WHERE usuario_id = %s AND estado IN ('papelera', 'eliminado')""", (usuario_id,))
            ocultos = {r[0] for r in cur.fetchall()}
    except Exception:
        return mensajes
    if not ocultos:
        return mensajes
    for m in mensajes:
        media = m.get('media') or []
        if not media:
            continue
        visibles = [a for a in media if _basename(a.get('file_path')) not in ocultos]
        if len(visibles) != len(media):
            m['media'] = visibles
            m['adjuntos_ocultos'] = len(media) - len(visibles)
            if not visibles and not (m.get('content') or '').strip():
                m['content'] = '📎 Archivo quitado de tu Drive (restáuralo desde la papelera para volver a verlo)'
                m['message_type'] = 'text'
    return mensajes


def _notificar(usuario_id, titulo, texto):
    try:
        from interfaces.websocket.notificaciones_globales import emitir, URL_BASE
        emitir([int(usuario_id)], 'sistema', titulo, texto, 'https://datos.maquita.com.ec/archivos-almacen?app=1', {'origen': 'drive'})
    except Exception as e:
        print(f'[drive-chat] aviso: {e}')


@bp_drive_eventos.route('/evento', methods=['POST'])
def evento():
    secreto = os.getenv('NOTIF_SECRET', '')
    recibido = request.headers.get('X-Notif-Secret', '')
    if not secreto or not hmac.compare_digest(secreto, recibido):
        return jsonify({'success': False, 'error': 'No autorizado'}), 403
    d = request.get_json(silent=True) or {}
    try:
        uid = int(d.get('usuario_id'))
    except (TypeError, ValueError):
        return jsonify({'success': False, 'error': 'usuario_id inválido'}), 400
    ruta = '/' + str(d.get('ruta') or '').strip().strip('/')
    ev = (d.get('evento') or '').strip().lower()
    if ev not in ('papelera', 'restaurado', 'eliminado'):
        return jsonify({'success': False, 'error': 'evento inválido'}), 400
    if not ruta.lower().startswith(CARPETA.lower() + '/'):
        return jsonify({'success': True, 'afectados': 0, 'mensaje': 'fuera de Archivos del chat'})
    estado = {'papelera': 'papelera', 'restaurado': 'activo', 'eliminado': 'eliminado'}[ev]
    with _conexion() as con, con.cursor() as cur:
        # archivo exacto o carpeta completa (subcarpeta de una conversación)
        cur.execute("""UPDATE chat_media_drive SET estado = %s, actualizado_en = NOW()
                       WHERE usuario_id = %s AND (ruta_drive = %s OR ruta_drive LIKE %s) RETURNING nombre_chat""",
                    (estado, uid, ruta, ruta + '/%'))
        afectados = [r[0] for r in cur.fetchall()]
    n = len(afectados)
    if n:
        nombre = _basename(ruta)
        if ev == 'papelera':
            _notificar(uid, 'Archivo del chat enviado a la papelera',
                       f'«{nombre}» dejará de verse en tu chat. Si lo restauras desde la papelera del Drive, vuelve a aparecer.')
        elif ev == 'restaurado':
            _notificar(uid, 'Archivo del chat restaurado', f'«{nombre}» vuelve a verse en tu chat.')
        else:
            _notificar(uid, 'Archivo del chat eliminado', f'«{nombre}» se quitó definitivamente de tu Drive y de tu chat.')
    return jsonify({'success': True, 'afectados': n, 'estado': estado})
