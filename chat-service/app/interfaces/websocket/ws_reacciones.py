# -*- coding: utf-8 -*-
"""Reacciones. Extraído de manejador_websocket._registrar_eventos (líneas 713-818) el 28/08/2026 sin cambios.
Los manejadores se registran al llamar registrar(socketio) desde manejador_websocket._registrar_eventos()."""
from interfaces.websocket.manejador_websocket import *  # noqa: F401,F403
from interfaces.websocket.manejador_websocket import _autorizado_en_conversacion, _cerrar_servicio, _commit_servicio, _conversacion_de_mensaje, _es_participante, _obtener_servicio_chat  # noqa: F401


def registrar(socketio):
    # =========================================================================
    # REACCIONES
    # =========================================================================

    @socketio.on('add_reaction')
    def agregar_reaccion(data):
        """
        Agrega una reaccion a un mensaje.

        Args:
            data: {
                'message_id': int,
                'conversation_id': int,
                'emoji': str
            }

        Emite:
            'reaction_added' a todos los participantes
        """
        usuario_id = session.get('usuario_id')
        if not usuario_id:
            return

        mensaje_id = data.get('message_id')
        conversacion_id = data.get('conversation_id')
        emoji = data.get('emoji')

        if not mensaje_id or not emoji:
            emit('error', {'message': 'Datos incompletos'})
            return

        # La sala sale del mensaje en la base, no de lo que mande el cliente (M-01)
        conversacion_id = _conversacion_de_mensaje(mensaje_id)
        if not _autorizado_en_conversacion(usuario_id, conversacion_id, 'add_reaction'):
            return
        servicio = None
        try:
            servicio = _obtener_servicio_chat()
            resultado = servicio.agregar_reaccion(
                mensaje_id=mensaje_id,
                usuario_id=usuario_id,
                emoji=emoji
            )

            if resultado.exito:
                _commit_servicio(servicio)
                if conversacion_id:
                    room = f"conversation_{conversacion_id}"
                    socketio.emit('reaction_added', {
                        'message_id': mensaje_id,
                        'user_id': usuario_id,
                        'emoji': emoji,
                        'timestamp': datetime.now().isoformat()
                    }, room=room)

                    logger.debug(f"[WebSocket] Reaccion {emoji} agregada a msg {mensaje_id}")
        except Exception as e:
            logger.error(f"[WebSocket] Error en add_reaction: {e}")
            emit('error', {'message': 'Error interno'})
        finally:
            if servicio:
                _cerrar_servicio(servicio)

    @socketio.on('remove_reaction')
    def eliminar_reaccion(data):
        """
        Elimina una reaccion de un mensaje.

        Args:
            data: {
                'message_id': int,
                'conversation_id': int
            }

        Emite:
            'reaction_removed' a todos los participantes
        """
        usuario_id = session.get('usuario_id')
        if not usuario_id:
            return

        mensaje_id = data.get('message_id')
        conversacion_id = data.get('conversation_id')

        if not mensaje_id:
            return

        conversacion_id = _conversacion_de_mensaje(mensaje_id)
        if not _autorizado_en_conversacion(usuario_id, conversacion_id, 'remove_reaction'):
            return
        servicio = None
        try:
            servicio = _obtener_servicio_chat()
            resultado = servicio.eliminar_reaccion(
                mensaje_id=mensaje_id,
                usuario_id=usuario_id
            )

            if resultado.exito:
                _commit_servicio(servicio)
                if conversacion_id:
                    room = f"conversation_{conversacion_id}"
                    socketio.emit('reaction_removed', {
                        'message_id': mensaje_id,
                        'user_id': usuario_id,
                        'timestamp': datetime.now().isoformat()
                    }, room=room)
        except Exception as e:
            logger.error(f"[WebSocket] Error en remove_reaction: {e}")
        finally:
            if servicio:
                _cerrar_servicio(servicio)

