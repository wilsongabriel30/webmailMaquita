# -*- coding: utf-8 -*-
"""Canal rápido: alias compactos join/leave/typing/stop_typing/read y ping_chat, que reutilizan los manejadores base.
Extraído de ws_canal_rapido.py el 28/08/2026 sin cambios."""
from interfaces.websocket.manejador_websocket import *  # noqa: F401,F403
from interfaces.websocket.manejador_websocket import _cerrar_servicio, _commit_servicio, _es_participante, _limpiar_indicador, _obtener_mensaje_por_client_id, _obtener_servicio_chat, _registrar_client_id, _typing_timers  # noqa: F401


def registrar(socketio, base):
    unirse_a_conversacion = base['unirse_a_conversacion']
    salir_de_conversacion = base['salir_de_conversacion']
    iniciar_escribiendo = base['iniciar_escribiendo']
    detener_escribiendo = base['detener_escribiendo']
    marcar_leido = base['marcar_leido']

    @socketio.on('join')
    def join_rapido(data):
        """Alias compacto para join_conversation."""
        print(f"[WebSocket] 📥 'join' event recibido: {data}, SID: {request.sid}")
        data['conversation_id'] = data.get('c') or data.get('conversation_id')
        unirse_a_conversacion(data)

    @socketio.on('leave')
    def leave_rapido(data):
        """Alias compacto para leave_conversation."""
        data['conversation_id'] = data.get('c') or data.get('conversation_id')
        salir_de_conversacion(data)

    @socketio.on('typing')
    def typing_rapido(data):
        """Alias compacto para typing_start."""
        data['conversation_id'] = data.get('c') or data.get('conversation_id')
        iniciar_escribiendo(data)

    @socketio.on('stop_typing')
    def stop_typing_rapido(data):
        """Alias compacto para typing_stop."""
        data['conversation_id'] = data.get('c') or data.get('conversation_id')
        detener_escribiendo(data)

    @socketio.on('read')
    def read_rapido(data):
        """Alias compacto para mark_read."""
        data['conversation_id'] = data.get('c') or data.get('conversation_id')
        marcar_leido(data)

    @socketio.on('ping_chat')
    def ping_chat():
        """Ping para medir latencia."""
        emit('pong_chat', {'ts': datetime.now().timestamp() * 1000})
