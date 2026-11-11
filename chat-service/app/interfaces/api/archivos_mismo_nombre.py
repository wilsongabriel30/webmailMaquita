# -*- coding: utf-8 -*-
"""Archivos del chat con el MISMO NOMBRE (T-101, 11/11/2026).

Antes de subir un archivo, el chat pregunta si en esa conversación ya hay uno con ese nombre. Si lo hay y el contenido es
distinto, la persona decide: reemplazar (en el Drive queda como versión nueva), guardar los dos, o enviar el anterior.

- GET  /api/chat/conversations/<id>/archivos/existe?nombre=…&bytes=…&sha256=…
       → {existe, mismo_contenido, archivo: {id, nombre, bytes, fecha, remitente, propio}, nombre_libre}
- POST /api/chat/conversations/<id>/archivos/<id_archivo>/reenviar
       → envía de nuevo ese archivo como mensaje (misma copia física, sin subir nada)
"""
import mimetypes
import os
from datetime import datetime

import psycopg2
import psycopg2.extras
from flask import jsonify, request, session
from werkzeug.utils import secure_filename

from interfaces.api.chat_base import bp_chat, obtener_usuario_id, requiere_autenticacion
from interfaces.api.chat_archivos_lista import _basename, _nombre_visible

LIMITE_HUELLA = 200 * 1024 * 1024


def _conexion():
    return psycopg2.connect(os.environ['DATABASE_URL'])


def _archivos_visibles(cur, conversacion_id, usuario_id):
    """Archivos (no GIF) de la conversación que esta persona puede ver, del más reciente al más antiguo. None = sin acceso."""
    cur.execute("SELECT cleared_at FROM chat_participants WHERE conversation_id = %s AND user_id = %s AND is_active",
                (conversacion_id, usuario_id))
    fila = cur.fetchone()
    if not fila:
        return None
    cur.execute("""SELECT DISTINCT nombre_chat FROM chat_media_drive
                   WHERE usuario_id = %s AND estado IN ('papelera', 'eliminado')""", (usuario_id,))
    ocultos = {f[0] for f in cur.fetchall()}
    cur.execute("""SELECT md.id, md.media_type, md.file_path, md.file_name, md.file_size, md.mime_type, md.created_at, m.sender_id,
                          COALESCE(NULLIF(TRIM(u.full_name), ''), u.username, 'Usuario') AS remitente
                   FROM chat_message_media md
                   JOIN chat_messages m ON m.id = md.message_id
                   LEFT JOIN usuarios u ON u.id = m.sender_id
                   WHERE m.conversation_id = %s AND NOT COALESCE(m.is_deleted, FALSE) AND md.media_type <> 'gif'
                     AND (%s::timestamptz IS NULL OR m.created_at > %s::timestamptz)
                   ORDER BY md.id DESC LIMIT 2000""", (conversacion_id, fila['cleared_at'], fila['cleared_at']))
    return [f for f in cur.fetchall() if _basename(f['file_path']) not in ocultos]


def _huella_guardada(cur, ruta):
    from interfaces.api.adjuntos_dedup import _abs, huella
    cur.execute("SELECT sha256 FROM chat_adjuntos_huellas WHERE ruta = %s ORDER BY id DESC LIMIT 1", (ruta,))
    f = cur.fetchone()
    if f:
        return f[0].strip()
    absoluta = _abs(ruta)
    if os.path.isfile(absoluta) and os.path.getsize(absoluta) <= LIMITE_HUELLA:
        return huella(absoluta)
    return None


def _nombre_libre(nombre, usados):
    base, ext = os.path.splitext(nombre)
    n = 2
    while f'{base} ({n}){ext}'.lower() in usados:
        n += 1
    return f'{base} ({n}){ext}'


@bp_chat.route('/conversations/<int:conversacion_id>/archivos/existe', methods=['GET'])
@requiere_autenticacion
def archivo_con_ese_nombre(conversacion_id: int):
    usuario_id = obtener_usuario_id()
    nombre = (request.args.get('nombre') or '').strip()[:255]
    if not nombre:
        return jsonify({'exito': True, 'existe': False}), 200
    try:
        with _conexion() as con, con.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            filas = _archivos_visibles(cur, conversacion_id, usuario_id)
            if filas is None:
                return jsonify({'exito': False, 'mensaje': 'No tienes acceso a esta conversacion'}), 403
            visibles = [(_nombre_visible(f['file_name'], f['file_path']), f) for f in filas]
            previo = next((f for n, f in visibles if n.lower() == nombre.lower()), None)
            if not previo:
                return jsonify({'exito': True, 'existe': False}), 200
            mismo = False
            sha = (request.args.get('sha256') or '').strip().lower()
            try:
                bytes_nuevo = int(request.args.get('bytes') or -1)
            except ValueError:
                bytes_nuevo = -1
            if len(sha) == 64 and bytes_nuevo == int(previo['file_size'] or 0):
                mismo = _huella_guardada(cur, previo['file_path']) == sha
            usados = {n.lower() for n, _ in visibles}
        return jsonify({'exito': True, 'existe': True, 'mismo_contenido': mismo,
                        'archivo': {'id': previo['id'], 'nombre': _nombre_visible(previo['file_name'], previo['file_path']),
                                    'bytes': int(previo['file_size'] or 0),
                                    'fecha': previo['created_at'].isoformat() if previo['created_at'] else None,
                                    'remitente': previo['remitente'], 'propio': previo['sender_id'] == usuario_id},
                        'nombre_libre': _nombre_libre(nombre, usados)}), 200
    except Exception as e:
        print(f'[mismo-nombre] existe: {e}')
        return jsonify({'exito': True, 'existe': False}), 200      # ante la duda, no estorbar el envío


@bp_chat.route('/conversations/<int:conversacion_id>/archivos/<int:archivo_id>/reenviar', methods=['POST'])
@requiere_autenticacion
def reenviar_archivo(conversacion_id: int, archivo_id: int):
    """Envía otra vez un archivo que ya está en la conversación (enlace a la misma copia física)."""
    from interfaces.api.adjuntos_dedup import RAIZ, _abs, _rel, registrar_archivos
    usuario_id = obtener_usuario_id()
    with _conexion() as con, con.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
        filas = _archivos_visibles(cur, conversacion_id, usuario_id)
    if filas is None:
        return jsonify({'exito': False, 'success': False, 'mensaje': 'No tienes acceso a esta conversacion'}), 403
    previo = next((f for f in filas if f['id'] == archivo_id), None)
    if not previo or not os.path.isfile(_abs(previo['file_path'])):
        return jsonify({'exito': False, 'success': False, 'mensaje': 'Ese archivo ya no está disponible'}), 404
    nombre = _nombre_visible(previo['file_name'], previo['file_path'])
    tipo = previo['media_type'] if previo['media_type'] in ('image', 'video', 'audio', 'document') else 'document'
    carpeta = os.path.join(RAIZ, 'static', 'uploads', 'chat', str(conversacion_id))
    os.makedirs(carpeta, exist_ok=True)
    destino = os.path.join(carpeta, datetime.now().strftime('%Y%m%d_%H%M%S%f_') + secure_filename(nombre))
    try:
        os.link(_abs(previo['file_path']), destino)
    except OSError:
        import shutil
        shutil.copy2(_abs(previo['file_path']), destino)
    mime = previo['mime_type'] or mimetypes.guess_type(nombre)[0] or 'application/octet-stream'
    from interfaces.api.controlador_chat import obtener_servicio_chat
    from interfaces.websocket import emitir_mensaje_nuevo
    res = obtener_servicio_chat().enviar_mensaje_con_archivos(
        conversacion_id=conversacion_id, remitente_id=int(usuario_id), tipo_media=tipo, contenido=None,
        archivos=[{'ruta': _rel(destino), 'nombre': nombre, 'tamanio': os.path.getsize(destino), 'tipo_mime': mime}])
    if not res.exito:
        return jsonify({'exito': False, 'success': False, 'mensaje': res.mensaje}), 400
    registrar_archivos(conversacion_id, usuario_id, [(destino, nombre)])
    try:
        from interfaces.api.drive_chat import reflejar_en_drive
        reflejar_en_drive(conversacion_id, int(usuario_id), [(destino, nombre)])
    except Exception as e:
        print(f'[mismo-nombre] drive: {e}')
    msg = (res.datos or {}).get('mensaje') or {}
    mensaje = {'id': msg.get('id'), 'content': msg.get('contenido'), 'message_type': tipo, 'sender_id': int(usuario_id),
               'created_at': msg.get('creado_en'), 'is_own_message': True,
               'media': [{'file_path': a.get('ruta'), 'media_type': tipo, 'file_name': a.get('nombre'), 'file_size': a.get('tamanio')}
                         for a in msg.get('archivos', [])]}
    try:
        copia = dict(msg); copia['remitente'] = {'id': int(usuario_id), 'nombre': session.get('usuario_nombre', 'Usuario')}
        emitir_mensaje_nuevo(conversacion_id, copia)
    except Exception as e:
        print(f'[mismo-nombre] emitir: {e}')
    return jsonify({'exito': True, 'success': True, 'message': mensaje, 'reutilizado': True}), 200
