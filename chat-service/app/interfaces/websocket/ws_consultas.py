# -*- coding: utf-8 -*-
"""Consultas por socket: conversaciones, mensajes, directo, búsqueda. Extraído de manejador_websocket._registrar_eventos (líneas 890-1098) el 28/08/2026 sin cambios.
Los manejadores se registran al llamar registrar(socketio) desde manejador_websocket._registrar_eventos()."""
from interfaces.websocket.manejador_websocket import *  # noqa: F401,F403
from interfaces.websocket.manejador_websocket import _cerrar_servicio, _commit_servicio, _obtener_servicio_chat  # noqa: F401


def registrar(socketio):
    # =========================================================================
    # CARGA DE DATOS VIA WEBSOCKET (100% tiempo real, NO HTTP)
    # =========================================================================

    @socketio.on('get_conversations')
    def obtener_conversaciones(data):
        """
        Obtiene lista de conversaciones del usuario via WebSocket.

        IMPORTANTE: Esto reemplaza la llamada HTTP para tiempo real puro.

        Emite:
            'conversations_list' con la lista de conversaciones
        """
        usuario_id = session.get('usuario_id')
        if not usuario_id:
            emit('error', {'message': 'No autenticado'})
            return

        servicio = None
        try:
            servicio = _obtener_servicio_chat()
            resultado = servicio.listar_conversaciones(usuario_id)

            if resultado.exito:
                conversaciones = resultado.datos.get('conversaciones', [])
                emit('conversations_list', {
                    'conversaciones': conversaciones,
                    'total': len(conversaciones),
                    'timestamp': datetime.now().isoformat()
                })
                logger.debug(f"[WebSocket] Conversaciones enviadas a {usuario_id}: {len(conversaciones)}")
            else:
                emit('error', {'message': resultado.mensaje})
        except Exception as e:
            logger.error(f"[WebSocket] Error obteniendo conversaciones: {e}")
            emit('error', {'message': str(e)})
        finally:
            if servicio:
                _cerrar_servicio(servicio)

    @socketio.on('get_messages')
    def obtener_mensajes(data):
        """
        Obtiene mensajes de una conversacion via WebSocket.

        IMPORTANTE: Esto reemplaza la llamada HTTP para tiempo real puro.

        Args:
            data: {
                'conversation_id' o 'c': int,
                'limit': int (default 50),
                'before': int (mensaje_id para paginar hacia atras),
                'after': int (mensaje_id para paginar hacia adelante)
            }

        Emite:
            'messages_list' con los mensajes
        """
        usuario_id = session.get('usuario_id')
        if not usuario_id:
            emit('error', {'message': 'No autenticado'})
            return

        conversacion_id = data.get('conversation_id') or data.get('c')
        limite = data.get('limit', 50)
        antes_de = data.get('before')
        despues_de = data.get('after')

        if not conversacion_id:
            emit('error', {'message': 'conversation_id requerido'})
            return

        servicio = None
        try:
            servicio = _obtener_servicio_chat()
            resultado = servicio.listar_mensajes(
                conversacion_id=conversacion_id,
                usuario_id=usuario_id,
                limite=limite,
                antes_de_id=antes_de,
                despues_de_id=despues_de
            )

            if resultado.exito:
                mensajes = resultado.datos.get('mensajes', [])
                emit('messages_list', {
                    'conversation_id': conversacion_id,
                    'c': conversacion_id,
                    'mensajes': mensajes,
                    'total': resultado.datos.get('total', len(mensajes)),
                    'has_more': resultado.datos.get('has_more', False),
                    'timestamp': datetime.now().isoformat()
                })
                logger.debug(f"[WebSocket] Mensajes enviados de conv {conversacion_id}: {len(mensajes)}")
            else:
                emit('error', {'message': resultado.mensaje})
        except Exception as e:
            logger.error(f"[WebSocket] Error obteniendo mensajes: {e}")
            emit('error', {'message': str(e)})
        finally:
            if servicio:
                _cerrar_servicio(servicio)

    @socketio.on('get_or_create_direct')
    def obtener_o_crear_directo(data):
        """
        Obtiene o crea una conversacion directa con un usuario.

        Args:
            data: {'user_id' o 'usuario_id': int}

        Emite:
            'conversation_data' o 'conversation_created'
        """
        usuario_id = session.get('usuario_id')
        if not usuario_id:
            emit('error', {'message': 'No autenticado'})
            return

        otro_usuario_id = data.get('user_id') or data.get('usuario_id')
        if not otro_usuario_id:
            emit('error', {'message': 'user_id requerido'})
            return

        servicio = None
        try:
            servicio = _obtener_servicio_chat()
            resultado = servicio.crear_conversacion_directa(
                usuario1_id=usuario_id,
                usuario2_id=otro_usuario_id
            )

            if resultado.exito:
                _commit_servicio(servicio)
                conversacion = resultado.datos.get('conversacion', {})
                fue_creada = 'creada' in resultado.mensaje.lower() and 'existente' not in resultado.mensaje.lower()

                evento = 'conversation_created' if fue_creada else 'conversation_data'
                emit(evento, {
                    'conversacion': conversacion,
                    'id': conversacion.get('id'),
                    'creada': fue_creada,
                    'timestamp': datetime.now().isoformat()
                })
                logger.debug(f"[WebSocket] Conversacion directa {conversacion.get('id')} {'creada' if fue_creada else 'obtenida'}")
            else:
                emit('error', {'message': resultado.mensaje})
        except Exception as e:
            logger.error(f"[WebSocket] Error en get_or_create_direct: {e}")
            emit('error', {'message': str(e)})
        finally:
            if servicio:
                _cerrar_servicio(servicio)

    @socketio.on('search_messages')
    def buscar_mensajes(data):
        """
        Busca mensajes via WebSocket.

        Args:
            data: {
                'q' o 'query': str,
                'conversation_id': int (opcional),
                'limit': int (default 20)
            }

        Emite:
            'search_results' con los resultados
        """
        usuario_id = session.get('usuario_id')
        if not usuario_id:
            emit('error', {'message': 'No autenticado'})
            return

        query = data.get('q') or data.get('query', '')
        conversacion_id = data.get('conversation_id')
        limite = data.get('limit', 20)

        if not query:
            emit('search_results', {'resultados': [], 'total': 0})
            return

        servicio = None
        try:
            servicio = _obtener_servicio_chat()
            resultado = servicio.buscar_mensajes(
                usuario_id=usuario_id,
                query=query,
                conversacion_id=conversacion_id,
                limite=limite
            )

            if resultado.exito:
                emit('search_results', {
                    'resultados': resultado.datos.get('resultados', []),
                    'total': resultado.datos.get('total', 0),
                    'query': query,
                    'timestamp': datetime.now().isoformat()
                })
            else:
                emit('error', {'message': resultado.mensaje})
        except Exception as e:
            logger.error(f"[WebSocket] Error en busqueda: {e}")
            emit('search_results', {'resultados': [], 'total': 0, 'error': str(e)})
        finally:
            if servicio:
                _cerrar_servicio(servicio)

