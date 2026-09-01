# -*- coding: utf-8 -*-
"""
Responder / citar mensajes (chat institucional).
=================================================
El backend ya guardaba `respuesta_a_id`; este módulo lo hace visible:
  - `enriquecer_citas(mensajes, servicio)`: agrega `reply_to` {id, sender_name,
    content, message_type} a cada mensaje del listado que responde a otro.
  - GET /api/chat/messages/<id>/cita: la cita de un mensaje suelto (para los que
    llegan en vivo por WebSocket y cuyo original no está en pantalla).
"""
import os

import psycopg2
from flask import Blueprint, jsonify

bp_citas = Blueprint('citas_chat', __name__, url_prefix='/api/chat')

_ETIQUETA_TIPO = {
    'gif': 'GIF', 'image': 'Imagen', 'imagen': 'Imagen', 'video': 'Video',
    'audio': 'Audio', 'document': 'Archivo', 'documento': 'Archivo', 'file': 'Archivo',
}
_cache_nombres = {}


def _nombre_usuario(uid):
    if uid in _cache_nombres:
        return _cache_nombres[uid]
    nombre = 'Usuario'
    try:
        con = psycopg2.connect(os.getenv('USERS_DB_URL') or os.environ['DATABASE_URL'])
        cur = con.cursor()
        cur.execute("SELECT COALESCE(NULLIF(TRIM(full_name), ''), email) FROM usuarios WHERE id = %s", (uid,))
        fila = cur.fetchone()
        con.close()
        if fila and fila[0]:
            nombre = fila[0]
    except Exception:
        pass
    _cache_nombres[uid] = nombre
    return nombre


def _cita_desde_mensaje(m):
    """m: dict del listado (claves en inglés) o entidad Mensaje del dominio."""
    if isinstance(m, dict):
        mid, tipo, contenido, remitente = m.get('id'), m.get('message_type') or 'text', m.get('content'), m.get('sender_id')
        nombre = m.get('sender_name') or _nombre_usuario(remitente)
        eliminado = m.get('is_deleted')
    else:
        mid = m.id
        tipo = m.tipo.value if hasattr(m.tipo, 'value') else str(m.tipo)
        contenido, remitente = m.contenido, m.remitente_id
        nombre = getattr(m, 'remitente_nombre', None) or _nombre_usuario(remitente)
        eliminado = getattr(m, 'eliminado', False)
    if eliminado:
        texto = 'Mensaje eliminado'
    elif tipo in ('text', 'texto', 'reply', 'respuesta') and contenido:
        texto = contenido
    else:
        texto = _ETIQUETA_TIPO.get(tipo, tipo.capitalize()) + ((': ' + contenido) if contenido and contenido not in ('GIF',) else '')
    return {'id': mid, 'sender_id': remitente, 'sender_name': nombre, 'content': (texto or '')[:200], 'message_type': tipo}


def enriquecer_citas(mensajes, servicio):
    """Rellena `reply_to` en los mensajes que tienen `reply_to_id`. Primero busca el
    original en la misma página; si no está, lo pide al repositorio."""
    por_id = {m.get('id'): m for m in mensajes if m.get('id')}
    for m in mensajes:
        rid = m.get('reply_to_id')
        if not rid:
            continue
        original = por_id.get(rid)
        if original is not None:
            m['reply_to'] = _cita_desde_mensaje(original)
            continue
        try:
            ent = servicio._repo_mensaje.buscar_por_id(rid)
            m['reply_to'] = _cita_desde_mensaje(ent) if ent else {'id': rid, 'sender_name': '', 'content': 'Mensaje no disponible', 'message_type': 'text'}
        except Exception:
            m['reply_to'] = {'id': rid, 'sender_name': '', 'content': 'Mensaje no disponible', 'message_type': 'text'}
    return mensajes


@bp_citas.route('/messages/<int:mensaje_id>/cita', methods=['GET'])
def obtener_cita(mensaje_id):
    from interfaces.api.controlador_chat import obtener_servicio_chat
    try:
        ent = obtener_servicio_chat()._repo_mensaje.buscar_por_id(mensaje_id)
    except Exception:
        ent = None
    if not ent:
        return jsonify({'success': False, 'mensaje': 'Mensaje no encontrado'}), 404
    return jsonify({'success': True, 'cita': _cita_desde_mensaje(ent)})
