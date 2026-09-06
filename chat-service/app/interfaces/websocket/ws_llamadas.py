# -*- coding: utf-8 -*-
"""Señalización de llamadas 1a1 (invite/accept/offer/answer/ice/hangup/reject). Extraído de manejador_websocket._registrar_eventos (líneas 1374-1503) el 28/08/2026 sin cambios.
Los manejadores se registran al llamar registrar(socketio) desde manejador_websocket._registrar_eventos()."""
from interfaces.websocket.manejador_websocket import *  # noqa: F401,F403


def registrar(socketio):
    # =========================================================================
    # LLAMADAS WebRTC P2P (senalizacion)
    # =========================================================================

    @socketio.on('call_invite')
    def manejar_call_invite(data):
        """Reenvia invitacion de llamada al usuario destino."""
        logger.debug("[WebRTC] call_invite destino=%s", data.get('target_user_id'))
        usuario_id = session.get('usuario_id')
        if not usuario_id:
            print(f"[WebRTC] call_invite rechazado: no autenticado")
            return
        target_user_id = data.get('target_user_id')
        if not target_user_id:
            print(f"[WebRTC] call_invite rechazado: sin target_user_id")
            return
        print(f"[WebRTC] Emitiendo call_incoming de {usuario_id} a user_{target_user_id}")
        try:
            from interfaces.websocket.notificaciones_globales import avatar_usuario, emitir, URL_BASE
            _avatar = avatar_usuario(usuario_id)
        except Exception:
            _avatar, emitir, URL_BASE = None, None, 'https://mail.maquita.org'
        socketio.emit('call_incoming', {
            'caller_id': usuario_id,
            'caller_name': data.get('caller_name', session.get('usuario_nombre', 'Usuario')),
            'tipo': data.get('tipo', 'audio'),
            'chat_id': data.get('chat_id'),
            'avatar': _avatar
        }, room=f"user_{target_user_id}")
        # Canal único (app de escritorio): notificación nativa con opción de contestar
        try:
            if emitir:
                _nombre = data.get('caller_name', session.get('usuario_nombre', 'Usuario'))
                _tipo = data.get('tipo', 'audio')
                emitir([int(target_user_id)], 'llamada', _nombre,
                       ('Videollamada' if _tipo == 'video' else 'Llamada de voz') + ' entrante · toca para contestar',
                       f"{URL_BASE}/chat/llamada?role=callee&tipo={_tipo}&peer_id={usuario_id}&peer_name={_nombre}&conv={data.get('chat_id') or ''}",
                       {'origen': 'llamadas', 'avatar': _avatar, 'llamada': {'tipo': _tipo, 'peer_id': usuario_id, 'peer_name': _nombre, 'conversacion_id': data.get('chat_id')}})
        except Exception as _e:
            print(f"[notificaciones] llamada: {_e}")
        logger.info(f"[WebRTC] call_invite de {usuario_id} a {target_user_id}")

    @socketio.on('call_accepted')
    def manejar_call_accepted(data):
        """Notifica al llamante que la llamada fue aceptada."""
        usuario_id = session.get('usuario_id')
        logger.debug("[WebRTC] call_accepted user=%s destino=%s", usuario_id, data.get('target_user_id'))
        if not usuario_id:
            return
        target_user_id = data.get('target_user_id')
        if not target_user_id:
            return
        print(f"[WebRTC] Emitiendo call_accepted a user_{target_user_id}")
        socketio.emit('call_accepted', {
            'accepted_by': usuario_id
        }, room=f"user_{target_user_id}")

    @socketio.on('call_offer')
    def manejar_call_offer(data):
        """Reenvia SDP offer al usuario destino."""
        usuario_id = session.get('usuario_id')
        print(f"[WebRTC] call_offer de user {usuario_id} a user_{data.get('target_user_id')}")
        if not usuario_id:
            return
        target_user_id = data.get('target_user_id')
        if not target_user_id:
            return
        socketio.emit('call_offer', {
            'from': usuario_id,
            'sdp': data.get('sdp')
        }, room=f"user_{target_user_id}")

    @socketio.on('call_answer')
    def manejar_call_answer(data):
        """Reenvia SDP answer al usuario destino."""
        usuario_id = session.get('usuario_id')
        print(f"[WebRTC] call_answer de user {usuario_id} a user_{data.get('target_user_id')}")
        if not usuario_id:
            return
        target_user_id = data.get('target_user_id')
        if not target_user_id:
            return
        socketio.emit('call_answer', {
            'from': usuario_id,
            'sdp': data.get('sdp')
        }, room=f"user_{target_user_id}")

    @socketio.on('ice_candidate')
    def manejar_ice_candidate(data):
        """Reenvia ICE candidate al usuario destino."""
        usuario_id = session.get('usuario_id')
        if not usuario_id:
            return
        target_user_id = data.get('target_user_id')
        if not target_user_id:
            return
        print(f"[WebRTC] ice_candidate de user {usuario_id} a user_{target_user_id}")
        socketio.emit('ice_candidate', {
            'from': usuario_id,
            'candidate': data.get('candidate')
        }, room=f"user_{target_user_id}")

    @socketio.on('call_hangup')
    def manejar_call_hangup(data):
        """Notifica al otro usuario que la llamada fue colgada."""
        usuario_id = session.get('usuario_id')
        if not usuario_id:
            return
        target_user_id = data.get('target_user_id')
        if not target_user_id:
            return
        socketio.emit('call_hangup', {
            'from': usuario_id
        }, room=f"user_{target_user_id}")
        logger.info(f"[WebRTC] call_hangup de {usuario_id} a {target_user_id}")

    @socketio.on('call_reject')
    def manejar_call_reject(data):
        """Notifica al llamante que la llamada fue rechazada."""
        usuario_id = session.get('usuario_id')
        if not usuario_id:
            return
        target_user_id = data.get('target_user_id')
        if not target_user_id:
            return
        socketio.emit('call_rejected', {
            'rejected_by': usuario_id
        }, room=f"user_{target_user_id}")
        logger.info(f"[WebRTC] call_reject de {usuario_id} a {target_user_id}")

