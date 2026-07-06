# -*- coding: utf-8 -*-
"""
Modulo WebSocket: Chat en Tiempo Real

Exporta las funciones y clases principales para la comunicacion
en tiempo real del chat institucional.

Uso:
    from interfaces.websocket import crear_socketio, emitir_mensaje_nuevo

Autor: Wilson Arguello
Correo: gestiontecnologia@maquita.com.ec
Fecha: 2026-01-02
"""

from .manejador_websocket import (
    # Inicializacion
    crear_socketio,
    socketio,

    # Emision de eventos
    emitir_mensaje_nuevo,
    emitir_notificacion,
    emitir_a_conversacion,

    # Utilidades
    esta_usuario_conectado,
    obtener_usuarios_conectados,
)

__all__ = [
    'crear_socketio',
    'socketio',
    'emitir_mensaje_nuevo',
    'emitir_notificacion',
    'emitir_a_conversacion',
    'esta_usuario_conectado',
    'obtener_usuarios_conectados',
]
