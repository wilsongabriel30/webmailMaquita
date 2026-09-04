# -*- coding: utf-8 -*-
"""
Canal ÚNICO de notificaciones (Teams Maquita, T-03).
=====================================================
Evento Socket.IO `notificacion` en la sala `user_<id>` de cada destinatario,
con payload uniforme para que cualquier cliente (web, app Windows) muestre
una notificación nativa y abra el módulo correcto:

    {"tipo": "chat" | "mencion" | "reunion" | "sistema" | ...,
     "titulo": "...", "texto": "...", "url": "https://...",
     "fecha": "ISO-8601", "origen": "chat", ...extra}

Fuentes: mensajes nuevos del chat (automático) y el endpoint REST
POST /api/chat/notificaciones (para FARO, reuniones, calendario…).
"""
import os
import re
from datetime import datetime

import psycopg2
import psycopg2.extras

URL_BASE = os.getenv('CHAT_URL_PUBLICA', 'https://mail.maquita.org').rstrip('/')
_ETIQUETA_TIPO = {'gif': '🎞️ GIF', 'image': '🖼️ Imagen', 'video': '🎬 Video', 'audio': '🎤 Audio',
                  'document': '📎 Archivo', 'file': '📎 Archivo'}


def _socketio():
    from interfaces.websocket import manejador_websocket as mw
    return mw.socketio


def _conexion():
    return psycopg2.connect(os.environ['DATABASE_URL'])


def emitir(usuario_ids, tipo, titulo, texto, url, extra=None):
    """Emite `notificacion` a cada usuario. Devuelve cuántos destinatarios recibieron el evento."""
    sio = _socketio()
    if not sio:
        return 0
    payload = {
        'tipo': tipo or 'sistema',
        'titulo': (titulo or 'Maquita')[:120],
        'texto': (texto or '')[:300],
        'url': url or URL_BASE + '/chat/',
        'fecha': datetime.now().isoformat(timespec='seconds'),
        'origen': (extra or {}).get('origen', 'chat'),
        'avatar': (extra or {}).get('avatar'),   # T-08: foto del remitente (URL absoluta) o null
    }
    if extra:
        for k, v in extra.items():
            payload.setdefault(k, v)
    n = 0
    urgente = (tipo or '') in ('mencion', 'llamada', 'reunion')
    for uid in {int(u) for u in usuario_ids if u}:
        # T-48: si esa persona pidio "No molestar", el aviso LLEGA igual (contrato T-47)
        # pero marcado como silencioso, para que el cliente no suene ni saque globito.
        # Las menciones y las llamadas se consideran urgentes y no se silencian.
        propio = payload
        if not urgente and _esta_en_no_molestar(uid):
            propio = dict(payload)
            propio['silencioso'] = True
        sio.emit('notificacion', propio, room=f'user_{uid}')
        n += 1
    return n


def _esta_en_no_molestar(usuario_id):
    """Si esa persona tiene puesto «No molestar» ahora mismo."""
    try:
        from interfaces.websocket import estado_presencia
        return estado_presencia.estado_de(usuario_id) == estado_presencia.NO_MOLESTAR
    except Exception:
        return False


def avatar_usuario(usuario_id):
    """URL ABSOLUTA (dominio público) de la foto de perfil del usuario, o None (T-08)."""
    if not usuario_id:
        return None
    try:
        with _conexion() as con, con.cursor() as cur:
            cur.execute("SELECT profile_picture FROM usuarios WHERE id = %s", (int(usuario_id),))
            fila = cur.fetchone()
    except Exception:
        return None
    foto = (fila[0] or '').strip() if fila else ''
    if not foto:
        return None
    if foto.startswith('http://') or foto.startswith('https://'):
        return foto
    if foto.startswith('/'):
        ruta = foto
    elif foto.startswith('uploads/'):
        ruta = '/static/' + foto
    elif foto.startswith('static/'):
        ruta = '/' + foto
    else:
        ruta = '/static/uploads/profiles/' + foto
    return URL_BASE + ruta


def usuarios_por_correo(correos):
    if not correos:
        return []
    with _conexion() as con, con.cursor() as cur:
        cur.execute("SELECT id FROM usuarios WHERE lower(email) = ANY(%s) AND active = TRUE",
                    ([c.strip().lower() for c in correos],))
        return [r[0] for r in cur.fetchall()]


def _contexto_conversacion(conversacion_id, remitente_id):
    with _conexion() as con, con.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
        cur.execute("SELECT name, conversation_type FROM chat_conversations WHERE id = %s", (conversacion_id,))
        conv = cur.fetchone()
        cur.execute("""SELECT user_id FROM chat_participants
                       WHERE conversation_id = %s AND is_active = TRUE AND user_id <> %s
                         AND COALESCE(is_muted, FALSE) = FALSE""", (conversacion_id, remitente_id))
        destinatarios = [r[0] for r in cur.fetchall()]
    return (conv['name'] if conv else None), (conv['conversation_type'] if conv else 'direct'), destinatarios


def notificar_mensaje(conversacion_id, remitente_id, nombre_remitente, contenido, tipo_mensaje='text',
                      mensaje_id=None, menciones=None):
    """Notificación automática por mensaje nuevo (la llama el servidor al guardar un mensaje)."""
    try:
        nombre_conv, tipo_conv, destinatarios = _contexto_conversacion(conversacion_id, remitente_id)
        if not destinatarios:
            return 0
        texto = (contenido or '').strip()
        if tipo_mensaje not in ('text', 'texto', 'reply', 'respuesta') or not texto:
            texto = _ETIQUETA_TIPO.get(tipo_mensaje, texto or 'Mensaje nuevo')
        texto = re.sub(r'\s+', ' ', texto)[:140]
        es_grupo = tipo_conv in ('group', 'grupo', 'broadcast')
        titulo = f'{nombre_remitente} · {nombre_conv}' if es_grupo and nombre_conv else (nombre_remitente or 'Mensaje nuevo')
        url = f'{URL_BASE}/chat/conversation/{conversacion_id}'
        extra = {'origen': 'chat', 'conversacion_id': conversacion_id, 'mensaje_id': mensaje_id,
                 'remitente_id': remitente_id, 'es_grupo': es_grupo, 'avatar': avatar_usuario(remitente_id)}
        mencionados = {int(m) for m in (menciones or []) if str(m).isdigit()}
        n = 0
        if mencionados:
            n += emitir([u for u in destinatarios if u in mencionados], 'mencion', f'{nombre_remitente} te mencionó', texto, url, extra)
        n += emitir([u for u in destinatarios if u not in mencionados], 'chat', titulo, texto, url, extra)
        return n
    except Exception as e:
        print(f'[notificaciones] error al notificar mensaje: {e}')
        return 0
