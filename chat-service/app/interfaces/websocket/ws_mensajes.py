# -*- coding: utf-8 -*-
"""Mensajes por WebSocket: send_message, edit_message, delete_message, mark_read.
Extraído de ws_mensajeria.py (líneas 64-297) el 28/08/2026 sin cambios. registrar(socketio) registra los eventos y devuelve
los manejadores para que ws_canal_rapido los reutilice."""
from interfaces.websocket.manejador_websocket import *  # noqa: F401,F403
from interfaces.websocket.manejador_websocket import _autorizado_en_conversacion, _cerrar_servicio, _commit_servicio, _conversacion_de_mensaje, _es_participante, _limpiar_indicador, _obtener_mensaje_por_client_id, _obtener_servicio_chat, _registrar_client_id, _typing_timers  # noqa: F401


def registrar(socketio):
    @socketio.on('send_message')
    def enviar_mensaje(data):
        """
        Envia un mensaje via WebSocket.

        Args:
            data: {
                'conversation_id': int,
                'content': str,
                'type': str (opcional, default 'text'),
                'reply_to': int (opcional)
            }

        Emite:
            'new_message' a todos los participantes de la conversacion
        """
        usuario_id = session.get('usuario_id')
        if not usuario_id:
            emit('error', {'message': 'No autenticado'})
            return

        conversacion_id = data.get('conversation_id')
        contenido = data.get('content', '').strip()
        tipo = data.get('type', 'text')
        respuesta_a = data.get('reply_to')

        if not conversacion_id or not contenido:
            emit('error', {'message': 'Datos incompletos'})
            return

        if not _autorizado_en_conversacion(usuario_id, conversacion_id, 'send_message'):
            return
        servicio = None
        try:
            # Enviar mensaje usando el servicio
            servicio = _obtener_servicio_chat()
            resultado = servicio.enviar_mensaje(
                conversacion_id=conversacion_id,
                remitente_id=usuario_id,
                contenido=contenido,
                tipo=tipo,
                respuesta_a_id=respuesta_a
            )

            if resultado.exito:
                # IMPORTANTE: Commit para persistir el mensaje
                _commit_servicio(servicio)

                mensaje_data = resultado.datos.get('mensaje', {})

                # Agregar info del remitente
                mensaje_data['remitente'] = {
                    'id': usuario_id,
                    'nombre': session.get('usuario_nombre', 'Usuario')
                }

                # Emitir a todos en la conversacion
                room = f"conversation_{conversacion_id}"
                socketio.emit('new_message', mensaje_data, room=room)

                # Limpiar indicador de escritura
                _limpiar_indicador(conversacion_id, usuario_id)

                logger.debug(f"[WebSocket] Mensaje enviado en conv {conversacion_id} por {usuario_id}")
            else:
                emit('error', {'message': resultado.mensaje})
        except Exception as e:
            logger.error(f"[WebSocket] Error en send_message: {e}")
            emit('error', {'message': 'Error interno del servidor'})
        finally:
            if servicio:
                _cerrar_servicio(servicio)

    @socketio.on('edit_message')
    def editar_mensaje(data):
        """
        Edita un mensaje existente.

        Args:
            data: {
                'message_id': int,
                'content': str
            }

        Emite:
            'message_edited' a todos los participantes
        """
        usuario_id = session.get('usuario_id')
        if not usuario_id:
            return

        mensaje_id = data.get('message_id')
        contenido = data.get('content', '').strip()

        if not mensaje_id or not contenido:
            emit('error', {'message': 'Datos incompletos'})
            return

        conversacion_id = _conversacion_de_mensaje(mensaje_id)
        if not _autorizado_en_conversacion(usuario_id, conversacion_id, 'edit_message'):
            return
        servicio = None
        try:
            servicio = _obtener_servicio_chat()
            resultado = servicio.editar_mensaje(
                mensaje_id=mensaje_id,
                usuario_id=usuario_id,
                nuevo_contenido=contenido
            )

            if resultado.exito:
                _commit_servicio(servicio)
                mensaje_data = resultado.datos.get('mensaje', {})
                conversacion_id = mensaje_data.get('conversacion_id')

                if conversacion_id:
                    room = f"conversation_{conversacion_id}"
                    socketio.emit('message_edited', mensaje_data, room=room)

                    logger.debug(f"[WebSocket] Mensaje {mensaje_id} editado por {usuario_id}")
            else:
                emit('error', {'message': resultado.mensaje})
        except Exception as e:
            logger.error(f"[WebSocket] Error en edit_message: {e}")
            emit('error', {'message': 'Error interno'})
        finally:
            if servicio:
                _cerrar_servicio(servicio)

    @socketio.on('delete_message')
    def eliminar_mensaje(data):
        """
        Elimina un mensaje.

        Args:
            data: {
                'message_id': int,
                'conversation_id': int,
                'for_all': bool (opcional)
            }

        Emite:
            'message_deleted' a todos los participantes
        """
        usuario_id = session.get('usuario_id')
        if not usuario_id:
            return

        mensaje_id = data.get('message_id')
        conversacion_id = data.get('conversation_id')
        para_todos = data.get('for_all', False)

        if not mensaje_id:
            emit('error', {'message': 'message_id requerido'})
            return

        conversacion_id = _conversacion_de_mensaje(mensaje_id)
        if not _autorizado_en_conversacion(usuario_id, conversacion_id, 'delete_message'):
            return
        servicio = None
        try:
            servicio = _obtener_servicio_chat()
            resultado = servicio.eliminar_mensaje(
                mensaje_id=mensaje_id,
                usuario_id=usuario_id,
                para_todos=para_todos
            )

            if resultado.exito:
                _commit_servicio(servicio)
                if conversacion_id:
                    room = f"conversation_{conversacion_id}"
                    socketio.emit('message_deleted', {
                        'message_id': mensaje_id,
                        'deleted_by': usuario_id,
                        'for_all': para_todos,
                        'timestamp': datetime.now().isoformat()
                    }, room=room)

                    logger.debug(f"[WebSocket] Mensaje {mensaje_id} eliminado por {usuario_id}")
            else:
                emit('error', {'message': resultado.mensaje})
        except Exception as e:
            logger.error(f"[WebSocket] Error en delete_message: {e}")
            emit('error', {'message': 'Error interno'})
        finally:
            if servicio:
                _cerrar_servicio(servicio)

    @socketio.on('mark_read')
    def marcar_leido(data):
        """
        Marca mensajes como leidos.

        Args:
            data: {
                'conversation_id': int,
                'until_message_id': int (opcional)
            }

        Emite:
            'messages_read' al remitente del mensaje
        """
        usuario_id = session.get('usuario_id')
        if not usuario_id:
            return

        conversacion_id = data.get('conversation_id')
        hasta_mensaje_id = data.get('until_message_id')

        if not conversacion_id:
            return
        if not _autorizado_en_conversacion(usuario_id, conversacion_id, 'mark_read'):
            return

        servicio = None
        try:
            servicio = _obtener_servicio_chat()
            resultado = servicio.marcar_leido(
                conversacion_id=conversacion_id,
                usuario_id=usuario_id,
                hasta_mensaje_id=hasta_mensaje_id
            )

            if resultado.exito:
                _commit_servicio(servicio)
                # Notificar en la conversacion que alguien leyo
                room = f"conversation_{conversacion_id}"
                socketio.emit('messages_read', {
                    'conversation_id': conversacion_id,
                    'read_by': usuario_id,
                    'until_message_id': hasta_mensaje_id,
                    'timestamp': datetime.now().isoformat()
                }, room=room)
                # y al room personal de cada remitente, para que el visto se
                # encienda aunque no tenga la conversacion abierta (T-45 p.10)
                from interfaces.websocket.avisos_lectura import avisar_lectura
                avisar_lectura(socketio, conversacion_id, usuario_id, hasta_mensaje_id)
        except Exception as e:
            logger.error(f"[WebSocket] Error en mark_read: {e}")
        finally:
            if servicio:
                _cerrar_servicio(servicio)

    # =========================================================================
    # INDICADORES DE ESCRITURA (TYPING)
    # =========================================================================

    return {'enviar_mensaje': enviar_mensaje, 'editar_mensaje': editar_mensaje, 'eliminar_mensaje': eliminar_mensaje, 'marcar_leido': marcar_leido}
