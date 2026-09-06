# -*- coding: utf-8 -*-
"""sync_chat. Extraído de manejador_websocket._registrar_eventos (líneas 1736-1808) el 28/08/2026 sin cambios.
Los manejadores se registran al llamar registrar(socketio) desde manejador_websocket._registrar_eventos()."""
from interfaces.websocket.manejador_websocket import *  # noqa: F401,F403
from interfaces.websocket.manejador_websocket import _cerrar_servicio, _es_participante, _obtener_servicio_chat  # noqa: F401


def registrar(socketio):
    # =========================================================================
    # SYNC / RECONEXION (anti "se perdio")
    # =========================================================================

    @socketio.on('sync_chat')
    def sincronizar_chat(data):
        """
        Sincroniza mensajes perdidos tras reconexion.

        Cuando el cliente se reconecta, envia el ultimo mensaje que vio
        y el servidor le devuelve todos los mensajes posteriores.

        Args:
            data: {
                'conversation_id' o 'c': int,
                'last_message_id': int (ultimo mensaje visto),
                'last_timestamp': int (timestamp en ms, alternativo)
            }

        Emite:
            'sync_messages' con mensajes faltantes + estados actualizados
        """
        usuario_id = session.get('usuario_id')
        if not usuario_id:
            emit('error', {'message': 'No autenticado'})
            return

        conversacion_id = data.get('conversation_id') or data.get('c')
        ultimo_mensaje_id = data.get('last_message_id')
        ultimo_timestamp = data.get('last_timestamp')

        if not conversacion_id:
            emit('error', {'message': 'conversation_id requerido'})
            return

        # Verificar permisos
        if not _es_participante(usuario_id, conversacion_id):
            emit('error', {'message': 'Sin acceso'})
            return

        servicio = None
        try:
            servicio = _obtener_servicio_chat()
            resultado = servicio.sincronizar_mensajes(
                conversacion_id=conversacion_id,
                usuario_id=usuario_id,
                despues_de_id=ultimo_mensaje_id,
                despues_de_timestamp=ultimo_timestamp
            )

            if resultado.exito:
                mensajes = resultado.datos.get('mensajes', [])
                emit('sync_messages', {
                    'c': conversacion_id,
                    'mensajes': mensajes,
                    'total': len(mensajes),
                    'synced_at': datetime.now().timestamp() * 1000
                })
                logger.debug(f"[WebSocket] Sync: {len(mensajes)} mensajes para user {usuario_id}")
            else:
                emit('sync_messages', {
                    'c': conversacion_id,
                    'mensajes': [],
                    'error': resultado.mensaje
                })

        except Exception as e:
            logger.error(f"[WebSocket] Error en sync_chat: {e}")
            emit('sync_messages', {'c': conversacion_id, 'mensajes': [], 'error': str(e)})
        finally:
            if servicio:
                _cerrar_servicio(servicio)

