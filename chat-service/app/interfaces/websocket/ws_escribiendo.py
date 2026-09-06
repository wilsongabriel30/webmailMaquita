# -*- coding: utf-8 -*-
"""Indicador «escribiendo»: typing_start / typing_stop.
Extraído de ws_mensajeria.py (líneas 298-365) el 28/08/2026 sin cambios. registrar(socketio) registra los eventos y devuelve
los manejadores para que ws_canal_rapido los reutilice."""
from interfaces.websocket.manejador_websocket import *  # noqa: F401,F403
from interfaces.websocket.manejador_websocket import _autorizado_en_conversacion, _cerrar_servicio, _commit_servicio, _conversacion_de_mensaje, _es_participante, _limpiar_indicador, _obtener_mensaje_por_client_id, _obtener_servicio_chat, _registrar_client_id, _typing_timers  # noqa: F401


def registrar(socketio):
    @socketio.on('typing_start')
    def iniciar_escribiendo(data):
        """
        Indica que el usuario empezo a escribir.

        Args:
            data: {
                'conversation_id': int,
                'action': str (opcional, default 'typing')
            }

        Emite:
            'user_typing' a otros participantes
        """
        usuario_id = session.get('usuario_id')
        if not usuario_id:
            return

        conversacion_id = data.get('conversation_id')
        accion = data.get('action', 'typing')

        if not conversacion_id:
            return
        if not _autorizado_en_conversacion(usuario_id, conversacion_id, 'typing_start'):
            return

        # Actualizar en BD
        servicio = None
        try:
            servicio = _obtener_servicio_chat()
            servicio.establecer_accion(conversacion_id, usuario_id, accion)
            _commit_servicio(servicio)
        except Exception as e:
            logger.error(f"[WebSocket] Error en typing_start: {e}")
        finally:
            if servicio:
                _cerrar_servicio(servicio)

        # Emitir a otros en la conversacion
        room = f"conversation_{conversacion_id}"
        socketio.emit('user_typing', {
            'conversation_id': conversacion_id,
            'user_id': usuario_id,
            'user_name': session.get('usuario_nombre', 'Usuario'),
            'action': accion,
            'timestamp': datetime.now().isoformat()
        }, room=room, skip_sid=request.sid)

        logger.debug(f"[WebSocket] Usuario {usuario_id} escribiendo en conv {conversacion_id}")

    @socketio.on('typing_stop')
    def detener_escribiendo(data):
        """
        Indica que el usuario dejo de escribir.

        Args:
            data: {'conversation_id': int}

        Emite:
            'user_stopped_typing' a otros participantes
        """
        usuario_id = session.get('usuario_id')
        if not usuario_id:
            return

        conversacion_id = data.get('conversation_id')
        if not conversacion_id:
            return

        _limpiar_indicador(conversacion_id, usuario_id)

    return {'iniciar_escribiendo': iniciar_escribiendo, 'detener_escribiendo': detener_escribiendo}
