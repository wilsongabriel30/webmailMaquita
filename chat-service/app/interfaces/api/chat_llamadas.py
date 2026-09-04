# -*- coding: utf-8 -*-
"""Token LiveKit/TURN e historial de llamadas.
Extraído de controlador_chat.py (líneas 2780-3030) el 28/08/2026 sin cambios en las rutas. Las rutas se registran en
bp_chat al importar este módulo (lo hace controlador_chat.py, que sigue siendo el punto de entrada)."""
from interfaces.api.chat_base import *  # noqa: F401,F403  (bp_chat, request, jsonify, servicio, autenticación…)

# =============================================================================
# LLAMADAS EN VIVO - LiveKit (CT 210)
# El cliente pide un token para unirse a la sala de la llamada; la media
# viaja por el SFU LiveKit (wss://datos.maquita.com.ec/livekit).
# Documentacion: (documentacion interna)
# =============================================================================

def _livekit_jwt(api_key: str, api_secret: str, claims: dict) -> str:
    """Genera un JWT HS256 para LiveKit sin dependencias externas."""
    import hmac as _hmac
    import hashlib as _hashlib
    import base64 as _base64
    import json as _json

    def _b64url(datos: bytes) -> bytes:
        return _base64.urlsafe_b64encode(datos).rstrip(b'=')

    cabecera = _b64url(_json.dumps({'alg': 'HS256', 'typ': 'JWT'}).encode())
    cuerpo = _b64url(_json.dumps(claims).encode())
    mensaje = cabecera + b'.' + cuerpo
    firma = _b64url(_hmac.new(api_secret.encode(), mensaje, _hashlib.sha256).digest())
    return (mensaje + b'.' + firma).decode()


def _turn_ice_servers():
    """Genera iceServers (STUN+TURN) con credenciales temporales TURN REST
    contra el coturn compartido de Jitsi (CT 201). Devuelve [] si no esta configurado.
    El cliente lo usa SOLO como respaldo (iceTransportPolicy:all): si la conexion
    directa funciona, el TURN no se toca."""
    import os, time, hmac, hashlib, base64
    secret = os.environ.get('LIVEKIT_TURN_SECRET')
    if not secret:
        return []
    udp_host = os.environ.get('LIVEKIT_TURN_UDP_HOST', '179.49.24.167')
    tls_host = os.environ.get('LIVEKIT_TURN_TLS_HOST', 'meet.maquita.com.ec')
    expiry = int(time.time()) + 12 * 3600  # credencial valida 12 h
    username = '%d:livekit' % expiry
    cred = base64.b64encode(
        hmac.new(secret.encode(), username.encode(), hashlib.sha1).digest()
    ).decode()
    return [
        {'urls': 'stun:%s:3478' % udp_host},
        {'urls': 'turn:%s:3478?transport=udp' % udp_host,
         'username': username, 'credential': cred},
        {'urls': 'turns:%s:5349?transport=tcp' % tls_host,
         'username': username, 'credential': cred},
    ]


@bp_chat.route('/llamada/token', methods=['GET'])
@requiere_autenticacion
def obtener_token_llamada():
    """
    Token de acceso a la sala LiveKit de una llamada del chat.

    Query params:
        room: nombre de la sala. Para llamadas 1 a 1 el formato es
              llamada_<idMenor>_<idMayor> y el usuario DEBE ser uno de los dos.

    Returns:
        { exito, url, token, sala, identidad }
    """
    import os
    import re as _re
    import time as _time

    usuario_id = obtener_usuario_id()
    sala = (request.args.get('room') or '').strip()

    if not sala or len(sala) > 100 or not _re.match(r'^[a-zA-Z0-9_\-]+$', sala):
        return jsonify({'exito': False, 'error': 'Sala invalida'}), 400

    # Solo salas de llamada 1 a 1 o de conferencia del chat
    if sala.startswith('llamada_'):
        # 1 a 1: solo los dos participantes pueden pedir token
        partes = sala.split('_')[1:]
        if len(partes) != 2 or str(usuario_id) not in partes:
            return jsonify({'exito': False, 'error': 'No autorizado para esta sala'}), 403
    elif sala.startswith('conf_'):
        # Conferencias: sala efimera con id aleatorio compartido por invitacion
        pass
    else:
        return jsonify({'exito': False, 'error': 'Tipo de sala no permitido'}), 403

    api_key = os.environ.get('LIVEKIT_API_KEY')
    api_secret = os.environ.get('LIVEKIT_API_SECRET')
    ws_url = os.environ.get('LIVEKIT_WS_URL', 'wss://datos.maquita.com.ec/livekit')
    if not api_key or not api_secret:
        return jsonify({'exito': False, 'error': 'LiveKit no configurado'}), 503

    ahora = int(_time.time())
    nombre = session.get('usuario_nombre') or session.get('username') or f'Usuario {usuario_id}'
    token = _livekit_jwt(api_key, api_secret, {
        'iss': api_key,
        'sub': str(usuario_id),
        'name': nombre,
        'nbf': ahora - 10,
        'exp': ahora + 7200,  # 2 horas (duracion maxima de una llamada)
        'video': {
            'room': sala,
            'roomJoin': True,
            'canPublish': True,
            'canSubscribe': True,
        },
    })

    return jsonify({
        'exito': True,
        'url': ws_url,
        'token': token,
        'sala': sala,
        'identidad': str(usuario_id),
        'ice_servers': _turn_ice_servers(),
    })


# =============================================================================
# HISTORIAL DE LLAMADAS (tabla chat_llamadas) + notificacion de perdidas
# Las ventanas de llamada/conferencia registran aqui al finalizar.
# =============================================================================

@bp_chat.route('/llamadas/registrar', methods=['POST'])
@requiere_autenticacion
def registrar_llamada_historial():
    """
    Registra una llamada finalizada (la registra el LLAMANTE / host).

    Body: { room, tipo: audio|video|conferencia, peer_id (opcional en conferencia),
            conversation_id (opcional), estado: completada|sin_respuesta|rechazada,
            duracion: segundos }
    Si la llamada no fue contestada/rechazada, crea notificacion de campanita
    al destinatario ("Llamada perdida de ...").
    """
    from sqlalchemy import text as _text

    usuario_id = obtener_usuario_id()
    datos = request.get_json(silent=True) or {}

    tipo = datos.get('tipo')
    estado = datos.get('estado')
    room = (datos.get('room') or '')[:120]
    if tipo not in ('audio', 'video', 'conferencia') or estado not in ('completada', 'sin_respuesta', 'rechazada'):
        return jsonify({'exito': False, 'error': 'tipo o estado invalido'}), 400

    try:
        peer_id = int(datos.get('peer_id')) if datos.get('peer_id') else None
    except (TypeError, ValueError):
        peer_id = None
    try:
        conversation_id = int(datos.get('conversation_id')) if datos.get('conversation_id') else None
    except (TypeError, ValueError):
        conversation_id = None
    try:
        duracion = max(0, int(datos.get('duracion') or 0))
    except (TypeError, ValueError):
        duracion = 0

    db_session = g.get('db_session_chat')
    if not db_session:
        gestor = obtener_gestor()
        db_session = gestor.session()
        g.db_session_chat = db_session

    db_session.execute(_text("""
        INSERT INTO chat_llamadas (room, tipo, caller_id, callee_id, conversation_id, estado, duracion_segundos)
        VALUES (:room, :tipo, :caller, :callee, :conv, :estado, :dur)
    """), {'room': room, 'tipo': tipo, 'caller': usuario_id, 'callee': peer_id,
           'conv': conversation_id, 'estado': estado, 'dur': duracion})
    db_session.commit()

    # Llamada perdida -> aviso en el CHAT (no en la campanita). Se empuja al room
    # del destinatario para que el badge del chat se actualice en vivo (toast opcional).
    if estado in ('sin_respuesta', 'rechazada') and peer_id and tipo != 'conferencia':
        try:
            nombre = session.get('usuario_nombre') or 'Un compañero'
            etiqueta = 'videollamada' if tipo == 'video' else 'llamada'
            from interfaces.websocket import manejador_websocket as _ws
            if _ws.socketio:
                _ws.socketio.emit('chat_llamada_perdida', {
                    'de_nombre': nombre,
                    'etiqueta': etiqueta,
                    'conversation_id': conversation_id
                }, room=f'user_{peer_id}')
        except Exception:
            pass  # nunca debe romper el registro

    return jsonify({'exito': True}), 200


@bp_chat.route('/llamadas/historial', methods=['GET'])
@requiere_autenticacion
def historial_llamadas():
    """
    Historial de llamadas del usuario (entrantes y salientes), mas recientes primero.

    Query: limit (default 50, max 200)
    Cada item: { id, tipo, estado, direccion: saliente|entrante, perdida: bool,
                 duracion_segundos, creado_en, otro: {id, nombre, foto},
                 conversation_id }
    """
    from sqlalchemy import text as _text

    usuario_id = obtener_usuario_id()
    try:
        limite = min(200, max(1, int(request.args.get('limit', 50))))
    except (TypeError, ValueError):
        limite = 50

    db_session = g.get('db_session_chat')
    if not db_session:
        gestor = obtener_gestor()
        db_session = gestor.session()
        g.db_session_chat = db_session

    filas = db_session.execute(_text("""
        SELECT l.id, l.tipo, l.estado, l.caller_id, l.callee_id, l.conversation_id,
               l.duracion_segundos, l.creado_en,
               u.id AS otro_id, u.full_name, u.username,
               u.profile_picture, t.foto_perfil
        FROM chat_llamadas l
        LEFT JOIN usuarios u
               ON u.id = CASE WHEN l.caller_id = :uid THEN l.callee_id ELSE l.caller_id END
        LEFT JOIN trabajadores t ON u.trabajador_id = t.id
        WHERE l.caller_id = :uid OR l.callee_id = :uid
        ORDER BY l.creado_en DESC
        LIMIT :lim
    """), {'uid': usuario_id, 'lim': limite}).fetchall()

    llamadas = []
    for f in filas:
        es_saliente = f[3] == usuario_id
        otro_nombre = f[9] or f[10] or ('Conferencia' if f[1] == 'conferencia' else 'Usuario')
        llamadas.append({
            'id': f[0],
            'tipo': f[1],
            'estado': f[2],
            'direccion': 'saliente' if es_saliente else 'entrante',
            'perdida': (not es_saliente) and f[2] in ('sin_respuesta', 'rechazada'),
            'conversation_id': f[5],
            'duracion_segundos': f[6] or 0,
            'creado_en': f[7].isoformat() if f[7] else None,
            'otro': {
                'id': f[8],
                'nombre': otro_nombre,
                'foto': obtener_foto_usuario_con_fallback(f[11], f[12]) if f[8] else None
            }
        })

    return jsonify({'exito': True, 'llamadas': llamadas}), 200

