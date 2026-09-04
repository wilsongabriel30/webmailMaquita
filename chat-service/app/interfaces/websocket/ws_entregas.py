# -*- coding: utf-8 -*-
"""Confirmaciones de entrega y lectura por lote. Extraído de manejador_websocket._registrar_eventos (líneas 1809-1913) el 28/08/2026 sin cambios.
Los manejadores se registran al llamar registrar(socketio) desde manejador_websocket._registrar_eventos()."""
from interfaces.websocket.manejador_websocket import *  # noqa: F401,F403
from interfaces.websocket.manejador_websocket import _cerrar_servicio, _commit_servicio, _obtener_servicio_chat  # noqa: F401


def registrar(socketio):
    # =========================================================================
    # ESTADOS DE MENSAJE (delivered / read)
    # =========================================================================

    @socketio.on('delivered')
    def confirmar_entregado(data):
        """
        Confirma que el cliente recibio un mensaje.

        El cliente llama esto cuando recibe 'msg' para confirmar delivery.

        Args:
            data: {
                'message_id' o 'id': int,
                'conversation_id' o 'c': int
            }

        Emite:
            'msg_status' al remitente original con estado 'delivered'
        """
        usuario_id = session.get('usuario_id')
        if not usuario_id:
            return

        mensaje_id = data.get('message_id') or data.get('id')
        conversacion_id = data.get('conversation_id') or data.get('c')

        if not mensaje_id:
            return

        servicio = None
        try:
            # El servicio cargado no implementa marcar_entregado: se usa estado_entrega (SQL directo)
            from interfaces.api.estado_entrega import marcar_entregado_directo
            remitente_id = marcar_entregado_directo(int(mensaje_id), int(usuario_id))
            if remitente_id:
                if remitente_id != usuario_id:
                    # Notificar al remitente que el mensaje fue entregado
                    socketio.emit('msg_status', {
                        'id': mensaje_id,
                        'c': conversacion_id,
                        'status': 'delivered',
                        'by': usuario_id,
                        'ts': datetime.now().timestamp() * 1000
                    }, room=f"user_{remitente_id}")

        except Exception as e:
            logger.error(f"[WebSocket] Error en delivered: {e}")
        finally:
            if servicio:
                _cerrar_servicio(servicio)

    @socketio.on('mark_read_batch')
    def marcar_leido_batch(data):
        """
        Marca multiples mensajes como leidos (hasta un ID).

        Mas eficiente que marcar uno por uno.

        Args:
            data: {
                'conversation_id' o 'c': int,
                'up_to_id': int (todos los mensajes hasta este ID, inclusive)
            }

        Emite:
            'msg_status_batch' a los remitentes
        """
        usuario_id = session.get('usuario_id')
        if not usuario_id:
            return

        conversacion_id = data.get('conversation_id') or data.get('c')
        hasta_id = data.get('up_to_id')

        if not conversacion_id or not hasta_id:
            return

        servicio = None
        try:
            servicio = _obtener_servicio_chat()
            resultado = servicio.marcar_leido_hasta(
                conversacion_id=conversacion_id,
                usuario_id=usuario_id,
                hasta_mensaje_id=hasta_id
            )

            if resultado.exito:
                _commit_servicio(servicio)
                # Notificar a la conversacion
                room = f"conversation_{conversacion_id}"
                socketio.emit('msg_status_batch', {
                    'c': conversacion_id,
                    'up_to_id': hasta_id,
                    'status': 'read',
                    'by': usuario_id,
                    'ts': datetime.now().timestamp() * 1000
                }, room=room, skip_sid=request.sid)

        except Exception as e:
            logger.error(f"[WebSocket] Error en mark_read_batch: {e}")
        finally:
            if servicio:
                _cerrar_servicio(servicio)

