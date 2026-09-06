# -*- coding: utf-8 -*-
"""Conferencias grupales (invite/join/offer/answer/ice/leave/reject). Extraído de manejador_websocket._registrar_eventos (líneas 1504-1735) el 28/08/2026 sin cambios.
Los manejadores se registran al llamar registrar(socketio) desde manejador_websocket._registrar_eventos()."""
from interfaces.websocket.manejador_websocket import *  # noqa: F401,F403
from interfaces.websocket.manejador_websocket import _es_participante  # noqa: F401


def _marcar_llamada(usuario_id, en_llamada):
    """Avisa a la regla de presencia (T-48). Nunca debe tumbar la llamada: si algo falla
    con Redis, la conferencia sigue su curso y solo se pierde el puntito."""
    try:
        from interfaces.websocket import estado_presencia
        estado_presencia.marcar_en_llamada(usuario_id, en_llamada)
    except Exception:
        pass


def registrar(socketio):
    # =========================================================================
    # AUDIOCONFERENCIA GRUPAL WebRTC (Full Mesh)
    # =========================================================================

    # Tracking en memoria de conferencias activas
    # { room_id: { 'creator': user_id, 'participants': {user_id: user_name, ...}, 'conversation_id': int|None, 'created_at': timestamp } }
    active_conferences = {}

    @socketio.on('conference_invite')
    def manejar_conference_invite(data):
        """
        Inicia una conferencia e invita participantes.
        data: { room_id, room_name, conversation_id (opt), participants: [{id, name}, ...] }
        """
        usuario_id = session.get('usuario_id')
        usuario_nombre = session.get('usuario_nombre', 'Usuario')
        if not usuario_id:
            return

        room_id = data.get('room_id')
        room_name = data.get('room_name', 'Conferencia')
        conversation_id = data.get('conversation_id')
        participants = data.get('participants', [])
        tipo_llamada = 'video' if data.get('tipo') == 'video' else 'audio'   # T-15

        if not room_id or not participants:
            emit('error', {'message': 'room_id y participants requeridos'})
            return
        # [M-04] Si la conferencia nace de una conversacion, quien invita tiene que estar en ella.
        if conversation_id and not _es_participante(usuario_id, conversation_id):
            emit('error', {'message': 'No autorizado'})
            return
        if room_id in active_conferences and active_conferences[room_id].get('creator') != usuario_id:
            emit('error', {'message': 'Esa sala ya existe'})
            return

        # Crear sala de conferencia. [M-04] Se guardan los invitados: solo ellos pueden unirse.
        active_conferences[room_id] = {
            'creator': usuario_id,
            'participants': {str(usuario_id): usuario_nombre},
            'invitados': {str(p.get('id', '')) for p in participants if str(p.get('id', ''))} | {str(usuario_id)},
            'conversation_id': conversation_id,
            'created_at': time.time(),
            'room_name': room_name
        }

        # [A-5] Dejar constancia de quien estuvo: es lo que despues decide quien
        # puede tocar la grabacion de esta conferencia.
        try:
            from interfaces.api.conferencia_miembros import registrar as _registrar_conf
            _registrar_conf(room_id, usuario_id)
        except Exception as _e:
            logger.warning(f"[Conference] no se pudo registrar al creador: {_e}")

        # El creador se une a la sala Socket.IO
        join_room(f"conference_{room_id}")
        # T-48: en una llamada o reunion, el puntito pasa a OCUPADO solo
        _marcar_llamada(usuario_id, True)

        logger.info(f"[Conference] {usuario_nombre} ({usuario_id}) creo conferencia {room_id} con {len(participants)} invitados")

        # Notificar a cada participante invitado
        try:
            from interfaces.websocket.notificaciones_globales import avatar_usuario, emitir, URL_BASE
            _avatar = avatar_usuario(usuario_id)
        except Exception:
            _avatar, emitir, URL_BASE = None, None, 'https://mail.maquita.org'
        _ids = []
        for p in participants:
            p_id = str(p.get('id', ''))
            if p_id and p_id != str(usuario_id):
                socketio.emit('conference_incoming', {
                    'room_id': room_id,
                    'room_name': room_name,
                    'conversation_id': conversation_id,
                    'caller_id': usuario_id,
                    'caller_name': usuario_nombre,
                    'avatar': _avatar,
                    'tipo': tipo_llamada,
                    'participants': [{'id': usuario_id, 'name': usuario_nombre}]
                }, room=f"user_{p_id}")
                if p_id.isdigit():
                    _ids.append(int(p_id))
        # Canal único (app de escritorio): "el grupo te invita a una llamada" con opción de unirse
        try:
            if emitir and _ids:
                from urllib.parse import quote
                emitir(_ids, 'llamada', f"{room_name}: " + ('videollamada grupal' if tipo_llamada == 'video' else 'llamada grupal'),
                       f"{usuario_nombre} inició una llamada del grupo · toca para unirte",
                       f"{URL_BASE}/chat/conferencia?role=guest&room={quote(str(room_id))}&name={quote(str(room_name))}"
                       f"&conv={conversation_id or ''}{'&video=1' if tipo_llamada == 'video' else ''}",
                       {'origen': 'llamadas', 'avatar': _avatar,
                        'llamada': {'grupal': True, 'tipo': tipo_llamada, 'room_id': room_id, 'room_name': room_name, 'conversacion_id': conversation_id,
                                    'caller_id': usuario_id, 'caller_name': usuario_nombre}})
        except Exception as _e:
            print(f"[notificaciones] llamada grupal: {_e}")

    @socketio.on('conference_join')
    def manejar_conference_join(data):
        """
        Un participante acepta y se une a la conferencia.
        data: { room_id }
        """
        usuario_id = session.get('usuario_id')
        usuario_nombre = session.get('usuario_nombre', 'Usuario')
        if not usuario_id:
            return

        room_id = data.get('room_id')
        if not room_id or room_id not in active_conferences:
            emit('error', {'message': 'Conferencia no encontrada'})
            return

        conf = active_conferences[room_id]
        # [M-04] Solo quien fue invitado (o el creador) puede unirse a la sala.
        if str(usuario_id) not in conf.get('invitados', set()):
            logger.warning(f"[Conference] join denegado: usuario {usuario_id} no fue invitado a {room_id}")
            emit('error', {'message': 'No estas invitado a esta conferencia'})
            return
        # [A-5] Igual que el creador: queda registrado que estuvo en la sala.
        try:
            from interfaces.api.conferencia_miembros import registrar as _registrar_conf
            _registrar_conf(room_id, usuario_id)
        except Exception as _e:
            logger.warning(f"[Conference] no se pudo registrar al participante: {_e}")

        # Lista de participantes existentes ANTES de agregar al nuevo
        existing_participants = [
            {'id': int(uid), 'name': uname}
            for uid, uname in conf['participants'].items()
        ]

        # Agregar nuevo participante
        conf['participants'][str(usuario_id)] = usuario_nombre

        # Unirse a la sala Socket.IO
        join_room(f"conference_{room_id}")
        # T-48: en una llamada o reunion, el puntito pasa a OCUPADO solo
        _marcar_llamada(usuario_id, True)

        logger.info(f"[Conference] {usuario_nombre} ({usuario_id}) se unio a conferencia {room_id}. Total: {len(conf['participants'])}")

        # Notificar a todos los existentes que alguien se unio
        socketio.emit('conference_user_joined', {
            'room_id': room_id,
            'user_id': usuario_id,
            'user_name': usuario_nombre,
            'existing_participants': existing_participants,
            'all_participants': [
                {'id': int(uid), 'name': uname}
                for uid, uname in conf['participants'].items()
            ]
        }, room=f"conference_{room_id}")

    @socketio.on('conference_offer')
    def manejar_conference_offer(data):
        """Reenviar SDP offer a un peer especifico."""
        usuario_id = session.get('usuario_id')
        if not usuario_id:
            return
        target_user_id = data.get('target_user_id')
        if not target_user_id:
            return
        socketio.emit('conference_offer', {
            'from_user_id': usuario_id,
            'from_user_name': session.get('usuario_nombre', 'Usuario'),
            'room_id': data.get('room_id'),
            'sdp': data.get('sdp')
        }, room=f"user_{target_user_id}")

    @socketio.on('conference_answer')
    def manejar_conference_answer(data):
        """Reenviar SDP answer a un peer especifico."""
        usuario_id = session.get('usuario_id')
        if not usuario_id:
            return
        target_user_id = data.get('target_user_id')
        if not target_user_id:
            return
        socketio.emit('conference_answer', {
            'from_user_id': usuario_id,
            'room_id': data.get('room_id'),
            'sdp': data.get('sdp')
        }, room=f"user_{target_user_id}")

    @socketio.on('conference_ice_candidate')
    def manejar_conference_ice_candidate(data):
        """Reenviar ICE candidate a un peer especifico."""
        usuario_id = session.get('usuario_id')
        if not usuario_id:
            return
        target_user_id = data.get('target_user_id')
        if not target_user_id:
            return
        socketio.emit('conference_ice_candidate', {
            'from_user_id': usuario_id,
            'room_id': data.get('room_id'),
            'candidate': data.get('candidate')
        }, room=f"user_{target_user_id}")

    @socketio.on('conference_leave')
    def manejar_conference_leave(data):
        """Un participante abandona la conferencia."""
        usuario_id = session.get('usuario_id')
        usuario_nombre = session.get('usuario_nombre', 'Usuario')
        if not usuario_id:
            return

        room_id = data.get('room_id')
        if not room_id or room_id not in active_conferences:
            return

        conf = active_conferences[room_id]

        # Remover participante
        conf['participants'].pop(str(usuario_id), None)

        # Salir de la sala Socket.IO
        leave_room(f"conference_{room_id}")
        # T-48: al salir vuelve solo a su estado normal
        _marcar_llamada(usuario_id, False)

        logger.info(f"[Conference] {usuario_nombre} ({usuario_id}) abandono conferencia {room_id}. Quedan: {len(conf['participants'])}")

        if len(conf['participants']) <= 1:
            # Notificar al ultimo que la conferencia termino
            socketio.emit('conference_ended', {
                'room_id': room_id,
                'reason': 'last_participant'
            }, room=f"conference_{room_id}")
            # Limpiar
            del active_conferences[room_id]
            logger.info(f"[Conference] Conferencia {room_id} terminada (ultimo participante)")
        else:
            # Notificar a los demas
            socketio.emit('conference_user_left', {
                'room_id': room_id,
                'user_id': usuario_id,
                'user_name': usuario_nombre,
                'remaining_participants': [
                    {'id': int(uid), 'name': uname}
                    for uid, uname in conf['participants'].items()
                ]
            }, room=f"conference_{room_id}")

    @socketio.on('conference_reject')
    def manejar_conference_reject(data):
        """Un participante rechaza la invitacion."""
        usuario_id = session.get('usuario_id')
        usuario_nombre = session.get('usuario_nombre', 'Usuario')
        if not usuario_id:
            return

        room_id = data.get('room_id')
        if not room_id or room_id not in active_conferences:
            return

        conf = active_conferences[room_id]

        # Notificar al creador
        socketio.emit('conference_user_rejected', {
            'room_id': room_id,
            'user_id': usuario_id,
            'user_name': usuario_nombre
        }, room=f"user_{conf['creator']}")

        logger.info(f"[Conference] {usuario_nombre} ({usuario_id}) rechazo conferencia {room_id}")

