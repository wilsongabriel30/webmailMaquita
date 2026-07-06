# -*- coding: utf-8 -*-
"""
Chat - WebSocket

Comunicacion en tiempo real para el chat institucional.
"""

# Por ahora importamos desde la ubicacion legacy para compatibilidad
# TODO: Mover el manejador aqui
from interfaces.websocket import (
    crear_socketio as crear_socketio_chat,
    emitir_mensaje_nuevo,
    emitir_a_conversacion,
    emitir_notificacion,
    esta_usuario_conectado,
    obtener_usuarios_conectados,
)

__all__ = [
    'crear_socketio_chat',
    'emitir_mensaje_nuevo',
    'emitir_a_conversacion',
    'emitir_notificacion',
    'esta_usuario_conectado',
    'obtener_usuarios_conectados',
]
