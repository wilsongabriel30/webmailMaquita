# -*- coding: utf-8 -*-
"""Indicador «escribiendo» con expiración automática (typing_with_expire). Extraído de ws_canal_rapido.py el 28/08/2026 sin cambios."""
from interfaces.websocket.manejador_websocket import *  # noqa: F401,F403
from interfaces.websocket.manejador_websocket import _cerrar_servicio, _commit_servicio, _es_participante, _limpiar_indicador, _obtener_mensaje_por_client_id, _obtener_servicio_chat, _registrar_client_id, _typing_timers  # noqa: F401


def registrar(socketio):
    # =========================================================================
    # TYPING CON EXPIRACION AUTOMATICA
    # =========================================================================

    def _cancelar_typing_timer(key: str):
        """Cancela el timer de typing si existe."""
        if key in _typing_timers:
            _typing_timers[key].cancel()
            del _typing_timers[key]

    def _expirar_typing(conversacion_id: int, usuario_id: int):
        """Callback cuando el typing expira automaticamente."""
        key = f"{conversacion_id}:{usuario_id}"
        if key in _typing_timers:
            del _typing_timers[key]

        # Notificar que dejo de escribir
        if socketio:
            room = f"conversation_{conversacion_id}"
            socketio.emit('styp', {
                'c': conversacion_id,
                'u': usuario_id
            }, room=room)

    @socketio.on('typing_with_expire')
    def typing_con_expiracion(data):
        """
        Indica que el usuario esta escribiendo, con expiracion automatica.

        Si no se recibe 'stop_typing' en TYPING_EXPIRE_SECONDS,
        automaticamente se emite que dejo de escribir.

        Args:
            data: {'conversation_id' o 'c': int}
        """
        usuario_id = session.get('usuario_id')
        if not usuario_id:
            return

        conversacion_id = data.get('conversation_id') or data.get('c')
        if not conversacion_id:
            return

        # Rate limit para typing
        if not check_rate_limit('typing', usuario_id):
            return

        key = f"{conversacion_id}:{usuario_id}"

        # Cancelar timer anterior si existe
        _cancelar_typing_timer(key)

        # Emitir typing a otros
        room = f"conversation_{conversacion_id}"
        socketio.emit('typ', {
            'c': conversacion_id,
            'u': usuario_id
        }, room=room, skip_sid=request.sid)

        # Programar expiracion automatica
        timer = threading.Timer(
            TYPING_EXPIRE_SECONDS,
            _expirar_typing,
            args=[conversacion_id, usuario_id]
        )
        timer.daemon = True
        timer.start()
        _typing_timers[key] = timer
