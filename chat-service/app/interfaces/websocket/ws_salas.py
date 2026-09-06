# -*- coding: utf-8 -*-
"""Salas de conversación: join_conversation / leave_conversation.
Extraído de ws_mensajeria.py (líneas 9-63) el 28/08/2026 sin cambios. registrar(socketio) registra los eventos y devuelve
los manejadores para que ws_canal_rapido los reutilice."""
from interfaces.websocket.manejador_websocket import *  # noqa: F401,F403
from interfaces.websocket.manejador_websocket import _cerrar_servicio, _commit_servicio, _es_participante, _limpiar_indicador, _obtener_mensaje_por_client_id, _obtener_servicio_chat, _registrar_client_id, _typing_timers  # noqa: F401


def registrar(socketio):
    # =========================================================================
    # ROOMS DE CONVERSACIONES
    # =========================================================================

    @socketio.on('join_conversation')
    def unirse_a_conversacion(data):
        """
        Une al usuario a un room de conversacion.

        Args:
            data: {'conversation_id': int}
        """
        usuario_id = session.get('usuario_id')
        if not usuario_id:
            logger.warning(f"[WebSocket] join_conversation sin usuario_id")
            return

        conversacion_id = data.get('conversation_id')
        if not conversacion_id:
            logger.warning("[WebSocket] join_conversation sin conversation_id")
            return

        # [A-3] Exigir ser participante. Antes la comprobacion era "permisiva para
        # debugging": cualquiera con sesion podia unirse a la sala de cualquier
        # conversacion y recibir en vivo TODO lo que se hablara dentro.
        if not _es_participante(usuario_id, conversacion_id):
            logger.warning(
                f"[WebSocket] join_conversation denegado: usuario {usuario_id} "
                f"no es participante de {conversacion_id}")
            emit('error', {'mensaje': 'No autorizado'})
            return

        room = f"conversation_{conversacion_id}"
        join_room(room)
        print(f"[WebSocket] ✅ Usuario {usuario_id} (SID: {request.sid}) unido a sala {room}")
        logger.info(f"[WebSocket] Usuario {usuario_id} (SID: {request.sid}) unido a {room}")

        emit('joined_conversation', {
            'conversation_id': conversacion_id,
            'timestamp': datetime.now().isoformat()
        })

    @socketio.on('leave_conversation')
    def salir_de_conversacion(data):
        """
        Remueve al usuario de un room de conversacion.

        Args:
            data: {'conversation_id': int}
        """
        usuario_id = session.get('usuario_id')
        if not usuario_id:
            return

        conversacion_id = data.get('conversation_id')
        if conversacion_id:
            room = f"conversation_{conversacion_id}"
            leave_room(room)
            logger.debug(f"[WebSocket] Usuario {usuario_id} salio de {room}")

    # =========================================================================
    # MENSAJES EN TIEMPO REAL
    # =========================================================================

    return {'unirse_a_conversacion': unirse_a_conversacion, 'salir_de_conversacion': salir_de_conversacion}
