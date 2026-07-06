# -*- coding: utf-8 -*-
"""
Manejador WebSocket: Chat en Tiempo Real

Implementa la comunicacion bidireccional en tiempo real usando Socket.IO.
Maneja eventos de mensajes, presencia, escritura y notificaciones.

Arquitectura:
- Flask-SocketIO con Eventlet como worker
- Redis como message queue para escalar a multiples workers
- Autenticacion basada en sesion Flask

Autor: Wilson Arguello
Correo: gestiontecnologia@maquita.com.ec
Fecha: 2026-01-02
"""

from flask import session, request
from flask_socketio import SocketIO, emit, join_room, leave_room, disconnect
from functools import wraps
from typing import Optional, Dict, Any, Set
from datetime import datetime, timedelta
from collections import defaultdict
import logging
import time
import threading

# Configurar logging
logger = logging.getLogger(__name__)

# ============================================================================
# RATE LIMITING
# ============================================================================

class RateLimiter:
    """Rate limiter distribuido con Redis, fallback in-memory."""

    def __init__(self):
        self._requests: Dict[str, list] = defaultdict(list)
        self._lock = threading.Lock()
        self._redis = None
        try:
            from modulos.chat.infraestructura.cache.cliente_redis import obtener_cliente_redis
            r = obtener_cliente_redis()
            if r.disponible:
                self._redis = r
                logger.info("[RateLimiter] Usando Redis distribuido")
        except Exception:
            pass

    def is_allowed(self, key: str, max_requests: int, window_seconds: int) -> bool:
        """Verifica si la accion esta permitida."""
        # Redis distribuido
        if self._redis:
            try:
                redis_key = f"chat:rate:{key}"
                count = self._redis.incr(redis_key)
                if count == 1:
                    self._redis.expire(redis_key, window_seconds)
                return count <= max_requests
            except Exception:
                pass

        # Fallback in-memory
        now = time.time()
        with self._lock:
            self._requests[key] = [t for t in self._requests[key] if now - t < window_seconds]
            if len(self._requests[key]) >= max_requests:
                return False
            self._requests[key].append(now)
            return True

    def cleanup(self):
        """Limpia entradas antiguas (solo para fallback in-memory)."""
        now = time.time()
        with self._lock:
            keys_to_delete = []
            for key, times in self._requests.items():
                self._requests[key] = [t for t in times if now - t < 60]
                if not self._requests[key]:
                    keys_to_delete.append(key)
            for key in keys_to_delete:
                del self._requests[key]


rate_limiter = RateLimiter()

# Rate limits por evento (max_requests, window_seconds)
RATE_LIMITS = {
    'send': (20, 10),           # 20 mensajes cada 10 segundos
    'typing': (10, 5),          # 10 typing cada 5 segundos
    'search': (5, 10),          # 5 busquedas cada 10 segundos
    'get_messages': (30, 10),   # 30 requests cada 10 segundos
}


def check_rate_limit(event: str, user_id: int) -> bool:
    """Verifica rate limit para un evento."""
    if event not in RATE_LIMITS:
        return True
    max_req, window = RATE_LIMITS[event]
    key = f"{event}:{user_id}"
    return rate_limiter.is_allowed(key, max_req, window)

# Instancia global de SocketIO (se inicializa en crear_socketio)
socketio: Optional[SocketIO] = None

# Redis para estado distribuido (conexiones, idempotencia)
_ws_redis = None
try:
    from modulos.chat.infraestructura.cache.cliente_redis import obtener_cliente_redis
    _r = obtener_cliente_redis()
    if _r.disponible:
        _ws_redis = _r
        logger.info("[WebSocket] Redis activo para estado distribuido")
except Exception:
    pass

# Fallback in-memory (siempre disponible para el worker local)
usuarios_conectados: Dict[int, Set[str]] = {}  # {usuario_id: {sid1, sid2, ...}}
sid_a_usuario: Dict[str, int] = {}  # {sid: usuario_id}

# Cache de client_ids procesados recientemente (para idempotencia)
_client_ids_recientes: Dict[str, Dict] = {}  # {client_id: {message_id, timestamp}}
_client_ids_lock = threading.Lock()
CLIENT_ID_TTL = 300  # 5 minutos

# Tracking de typing con expiracion automatica
_typing_timers: Dict[str, threading.Timer] = {}  # {conv_id:user_id: timer}
TYPING_EXPIRE_SECONDS = 10


def _limpiar_client_ids_antiguos():
    """Limpia client_ids mas antiguos que TTL."""
    now = time.time()
    with _client_ids_lock:
        to_delete = [
            cid for cid, data in _client_ids_recientes.items()
            if now - data.get('ts', 0) > CLIENT_ID_TTL
        ]
        for cid in to_delete:
            del _client_ids_recientes[cid]


def _registrar_client_id(client_id: str, message_id: int) -> bool:
    """
    Registra un client_id como procesado.
    Returns True si es nuevo, False si ya existia (duplicado).
    """
    if not client_id:
        return True  # Sin client_id, siempre procesar

    # Redis distribuido
    if _ws_redis:
        try:
            redis_key = f"chat:idempotent:{client_id}"
            # SETNX: solo setea si no existe
            was_set = _ws_redis.set(redis_key, str(message_id), ttl_segundos=CLIENT_ID_TTL)
            # Verificar si ya existia
            existing = _ws_redis.get(redis_key)
            if existing and int(existing) != message_id:
                return False  # Ya procesado con otro message_id
        except Exception:
            pass

    # Siempre registrar en local tambien
    with _client_ids_lock:
        if client_id in _client_ids_recientes:
            return False

        _client_ids_recientes[client_id] = {
            'message_id': message_id,
            'ts': time.time()
        }
        return True


def _obtener_mensaje_por_client_id(client_id: str) -> Optional[int]:
    """Obtiene el message_id de un client_id ya procesado."""
    # Redis primero
    if _ws_redis and client_id:
        try:
            val = _ws_redis.get(f"chat:idempotent:{client_id}")
            if val:
                return int(val)
        except Exception:
            pass

    # Fallback local
    with _client_ids_lock:
        data = _client_ids_recientes.get(client_id)
        return data.get('message_id') if data else None


def crear_socketio(app, redis_url: Optional[str] = None) -> SocketIO:
    """
    Crea y configura la instancia de SocketIO.

    Args:
        app: Aplicacion Flask
        redis_url: URL de Redis para message queue (opcional)
                   Formato: redis://localhost:6379/0

    Returns:
        Instancia de SocketIO configurada
    """
    global socketio

    # Configuracion de message queue
    # En producción, desactivar loggers internos de engineio/socketio
    # para evitar ruido en stderr (ej: "socket shutdown error: Bad file descriptor")
    import os
    es_produccion = os.environ.get('FLASK_ENV') == 'production'
    sio_logger = not es_produccion
    eio_logger = not es_produccion

    if redis_url:
        # Usar Redis para escalar a multiples workers
        socketio = SocketIO(
            app,
            cors_allowed_origins="*",
            async_mode='eventlet',
            message_queue=redis_url,
            logger=sio_logger,
            engineio_logger=eio_logger
        )
        logger.info(f"[WebSocket] Configurado con Redis: {redis_url}")
    else:
        # Modo desarrollo sin Redis
        socketio = SocketIO(
            app,
            cors_allowed_origins="*",
            async_mode='eventlet',
            logger=sio_logger,
            engineio_logger=eio_logger
        )
        logger.info("[WebSocket] Configurado en modo desarrollo (sin Redis)")

    # Registrar manejadores de eventos
    _registrar_eventos()

    return socketio


def _registrar_eventos():
    """Registra todos los manejadores de eventos WebSocket."""

    # =========================================================================
    # CONEXION Y DESCONEXION
    # =========================================================================

    @socketio.on('connect')
    def manejar_conexion():
        """
        Maneja una nueva conexion WebSocket.

        El cliente debe estar autenticado via sesion Flask.
        Automaticamente une al usuario a sus rooms de conversaciones.
        """
        usuario_id = session.get('usuario_id')

        if not usuario_id:
            logger.warning(f"[WebSocket] Conexion rechazada: no autenticado (sid={request.sid})")
            disconnect()
            return False

        sid = request.sid

        # Registrar conexion (local)
        if usuario_id not in usuarios_conectados:
            usuarios_conectados[usuario_id] = set()
        usuarios_conectados[usuario_id].add(sid)
        sid_a_usuario[sid] = usuario_id

        # Registrar en Redis (distribuido)
        if _ws_redis:
            try:
                _ws_redis.sadd(f"chat:ws:user:{usuario_id}", sid)
                _ws_redis.expire(f"chat:ws:user:{usuario_id}", 3600)
                _ws_redis.hset("chat:ws:sid_map", sid, str(usuario_id))
                _ws_redis.set(f"chat:presence:{usuario_id}", "online", ttl_segundos=300)
            except Exception as e:
                logger.warning(f"[WebSocket] Redis registro conexion error: {e}")

        # Unir a room personal (para mensajes directos al usuario)
        join_room(f"user_{usuario_id}")

        # Actualizar presencia en BD
        _actualizar_presencia_bd(usuario_id, True)

        # Notificar a contactos que el usuario esta online
        _emitir_presencia(usuario_id, True)

        logger.info(f"[WebSocket] Usuario {usuario_id} conectado (sid={sid})")

        # Confirmar conexion al cliente
        emit('connected', {
            'usuario_id': usuario_id,
            'timestamp': datetime.now().isoformat()
        })

        return True

    @socketio.on('disconnect')
    def manejar_desconexion():
        """
        Maneja la desconexion de un cliente WebSocket.

        Limpia el registro y notifica a contactos.
        """
        sid = request.sid
        usuario_id = sid_a_usuario.get(sid)

        if usuario_id:
            # Remover esta conexion (local)
            if usuario_id in usuarios_conectados:
                usuarios_conectados[usuario_id].discard(sid)

                # Si no tiene mas conexiones en este worker, marcar como offline
                if not usuarios_conectados[usuario_id]:
                    del usuarios_conectados[usuario_id]

                    # Verificar en Redis si hay otras conexiones en otros workers
                    tiene_otras = False
                    if _ws_redis:
                        try:
                            _ws_redis.srem(f"chat:ws:user:{usuario_id}", sid)
                            _ws_redis.hdel("chat:ws:sid_map", sid)
                            remaining = _ws_redis.scard(f"chat:ws:user:{usuario_id}")
                            tiene_otras = remaining > 0
                        except Exception:
                            pass

                    if not tiene_otras:
                        _actualizar_presencia_bd(usuario_id, False)
                        _emitir_presencia(usuario_id, False)
                        if _ws_redis:
                            try:
                                _ws_redis.delete(f"chat:presence:{usuario_id}")
                            except Exception:
                                pass
            elif _ws_redis:
                # Limpiar Redis aunque no estaba en local
                try:
                    _ws_redis.srem(f"chat:ws:user:{usuario_id}", sid)
                    _ws_redis.hdel("chat:ws:sid_map", sid)
                except Exception:
                    pass

            if sid in sid_a_usuario:
                del sid_a_usuario[sid]

            logger.info(f"[WebSocket] Usuario {usuario_id} desconectado (sid={sid})")

    # =========================================================================
    # ROOMS DE CONVERSACIONES
    # =========================================================================

    @socketio.on('join_conversation')
    def unirse_a_conversacion(data):
        """
        Une al usuario a un room de conversacion.

        Args:
            data: {'conversation_id': int}
        """
        usuario_id = session.get('usuario_id')
        if not usuario_id:
            logger.warning(f"[WebSocket] join_conversation sin usuario_id")
            return

        conversacion_id = data.get('conversation_id')
        if not conversacion_id:
            logger.warning(f"[WebSocket] join_conversation sin conversation_id, data={data}")
            return

        # Unir al room (verificacion permisiva para debugging)
        room = f"conversation_{conversacion_id}"
        join_room(room)
        print(f"[WebSocket] ✅ Usuario {usuario_id} (SID: {request.sid}) unido a sala {room}")
        logger.info(f"[WebSocket] Usuario {usuario_id} (SID: {request.sid}) unido a {room}")

        emit('joined_conversation', {
            'conversation_id': conversacion_id,
            'timestamp': datetime.now().isoformat()
        })

    @socketio.on('leave_conversation')
    def salir_de_conversacion(data):
        """
        Remueve al usuario de un room de conversacion.

        Args:
            data: {'conversation_id': int}
        """
        usuario_id = session.get('usuario_id')
        if not usuario_id:
            return

        conversacion_id = data.get('conversation_id')
        if conversacion_id:
            room = f"conversation_{conversacion_id}"
            leave_room(room)
            logger.debug(f"[WebSocket] Usuario {usuario_id} salio de {room}")

    # =========================================================================
    # MENSAJES EN TIEMPO REAL
    # =========================================================================

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
        except Exception as e:
            logger.error(f"[WebSocket] Error en mark_read: {e}")
        finally:
            if servicio:
                _cerrar_servicio(servicio)

    # =========================================================================
    # INDICADORES DE ESCRITURA (TYPING)
    # =========================================================================

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

    # =========================================================================
    # PRESENCIA
    # =========================================================================

    @socketio.on('heartbeat')
    def heartbeat():
        """
        Heartbeat para mantener la conexion y actualizar presencia.

        El cliente debe enviar esto cada 30 segundos.
        """
        usuario_id = session.get('usuario_id')
        if usuario_id:
            _actualizar_presencia_bd(usuario_id, True)
            # Refresh Redis presence + connection TTLs
            if _ws_redis:
                try:
                    _ws_redis.set(f"chat:presence:{usuario_id}", "online", ttl_segundos=300)
                    _ws_redis.expire(f"chat:ws:user:{usuario_id}", 3600)
                except Exception:
                    pass
            emit('heartbeat_ack', {'timestamp': datetime.now().isoformat()})

    @socketio.on('get_presence')
    def obtener_presencia(data):
        """
        Obtiene la presencia de uno o varios usuarios.

        Args:
            data: {'user_ids': [int, int, ...]}

        Emite:
            'presence_info' con el estado de cada usuario
        """
        usuario_ids = data.get('user_ids', [])
        if not usuario_ids:
            return

        servicio = None
        try:
            servicio = _obtener_servicio_chat()
            presencias = servicio.obtener_presencia(usuario_ids)

            resultado = {}
            for uid in usuario_ids:
                # Check local + Redis
                en_linea = (uid in usuarios_conectados and usuarios_conectados[uid])
                if not en_linea and _ws_redis:
                    try:
                        en_linea = _ws_redis.exists(f"chat:presence:{uid}")
                    except Exception:
                        pass
                if en_linea:
                    resultado[uid] = {'online': True, 'last_seen': None}
                elif uid in presencias:
                    p = presencias[uid]
                    resultado[uid] = {
                        'online': p.get('online', False),
                        'last_seen': p.get('last_seen').isoformat() if p.get('last_seen') else None
                    }
                else:
                    resultado[uid] = {'online': False, 'last_seen': None}

            emit('presence_info', resultado)
        except Exception as e:
            logger.error(f"[WebSocket] Error en get_presence: {e}")
            emit('presence_info', {})
        finally:
            if servicio:
                _cerrar_servicio(servicio)

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

    # =========================================================================
    # ENVIO ULTRA-RAPIDO (formato compacto)
    # =========================================================================

    @socketio.on('send')
    def enviar_mensaje_rapido(data):
        """
        Envio de mensaje ultra-rapido con ACK instantaneo e idempotencia.

        Formato compacto para minima latencia:
        - c: conversation_id
        - m: message content
        - t: temp_id/client_id (ID temporal del cliente para idempotencia)
        - type: tipo de mensaje

        Flujo:
        1. Valida autenticacion, permisos y rate limit
        2. Verifica idempotencia (si client_id ya fue procesado)
        3. Emite 'ack' inmediatamente (antes de guardar en BD)
        4. Guarda en BD con client_id
        5. Emite 'msg_saved' con ID real o 'msg_failed' si falla
        6. Emite 'msg' a otros participantes
        """
        usuario_id = session.get('usuario_id')
        if not usuario_id:
            emit('error', {'message': 'No autenticado'})
            return

        conversacion_id = data.get('c') or data.get('conversation_id')
        contenido = (data.get('m') or data.get('content', '')).strip()
        client_id = data.get('t') or data.get('temp_id') or data.get('client_id')
        tipo = data.get('type', 'text')
        respuesta_a = data.get('reply_to')

        # Un GIF/media puede ir sin texto: basta con gif_url/url
        _tiene_media = bool(data.get('gif_url') or data.get('url'))

        # Validaciones basicas (texto requerido SOLO si no hay media)
        if not conversacion_id or (not contenido and not _tiene_media):
            emit('msg_failed', {
                't': client_id,
                'reason': 'c y m requeridos',
                'code': 'INVALID_DATA'
            })
            return

        # Rate limiting
        if not check_rate_limit('send', usuario_id):
            emit('msg_failed', {
                't': client_id,
                'reason': 'Demasiados mensajes. Espera un momento.',
                'code': 'RATE_LIMITED'
            })
            return

        # Verificar permisos (es participante de la conversacion)
        if not _es_participante(usuario_id, conversacion_id):
            emit('msg_failed', {
                't': client_id,
                'reason': 'No tienes acceso a esta conversacion',
                'code': 'FORBIDDEN'
            })
            return

        # ========== IDEMPOTENCIA ==========
        # Verificar si este client_id ya fue procesado
        mensaje_existente = _obtener_mensaje_por_client_id(client_id)
        if mensaje_existente:
            # Ya fue procesado - retornar el mensaje existente sin duplicar
            logger.info(f"[WebSocket] Mensaje duplicado detectado: {client_id} -> {mensaje_existente}")
            emit('ack', {
                't': client_id,
                'ts': datetime.now().timestamp() * 1000
            })
            emit('msg_saved', {
                't': client_id,
                'id': mensaje_existente,
                's': 'saved',
                'duplicate': True
            })
            return

        # 1. ACK INSTANTANEO (antes de cualquier operacion de BD)
        emit('ack', {
            't': client_id,
            'ts': datetime.now().timestamp() * 1000
        })

        servicio = None
        gif_url = data.get('gif_url') or data.get('url')  # URL del GIF si es tipo gif

        try:
            # 2. Guardar en BD con client_id para idempotencia
            print(f"[WS-DEBUG] Enviando mensaje: conv={conversacion_id}, user={usuario_id}, client_id={client_id}, tipo={tipo}")
            servicio = _obtener_servicio_chat()

            # Si es un GIF, usar el servicio de GIF
            if tipo == 'gif' and gif_url:
                resultado = servicio.enviar_gif(
                    conversacion_id=conversacion_id,
                    remitente_id=usuario_id,
                    url_gif=gif_url,
                    contenido=contenido or 'GIF'
                )
            else:
                resultado = servicio.enviar_mensaje(
                    conversacion_id=conversacion_id,
                    remitente_id=usuario_id,
                    contenido=contenido,
                    tipo=tipo,
                    respuesta_a_id=respuesta_a,
                    client_id=client_id  # Para constraint UNIQUE en BD
                )
            print(f"[WS-DEBUG] Resultado enviar_mensaje: exito={resultado.exito}, mensaje={resultado.mensaje}")

            if resultado.exito:
                # IMPORTANTE: Commit para persistir el mensaje
                print(f"[WS-DEBUG] Haciendo commit...")
                _commit_servicio(servicio)
                print(f"[WS-DEBUG] Commit exitoso")

                mensaje_data = resultado.datos.get('mensaje', {})
                mensaje_id = mensaje_data.get('id')

                # Registrar client_id como procesado (cache local)
                _registrar_client_id(client_id, mensaje_id)

                # 3. Confirmar guardado al remitente
                emit('msg_saved', {
                    't': client_id,
                    'id': mensaje_id,
                    's': 'saved'
                })

                # 4. Emitir a otros en la conversacion (formato compacto)
                room = f"conversation_{conversacion_id}"
                print(f"[WebSocket] ⚡⚡⚡ Emitiendo 'msg' a sala {room} (mensaje {mensaje_id} de usuario {usuario_id})")
                print(f"[WebSocket] Usuarios conectados: {list(usuarios_conectados.keys())}")
                print(f"[WebSocket] SID actual (skip): {request.sid}")

                # Debug: Listar SIDs y ver clientes en la sala destino
                try:
                    # Mostrar qué SIDs están en qué usuarios
                    for uid, sids in usuarios_conectados.items():
                        for sid in sids:
                            print(f"[WebSocket] 🔍 Usuario {uid} tiene SID {sid}")

                    # Intentar ver cuántos clientes hay en la sala
                    if socketio.server and hasattr(socketio.server, 'manager'):
                        try:
                            rooms_info = socketio.server.manager.get_participants('/', room)
                            sids_en_sala = list(rooms_info) if rooms_info else []
                            print(f"[WebSocket] 📊 Clientes en sala {room}: {sids_en_sala}")
                            print(f"[WebSocket] 📊 Total clientes en sala: {len(sids_en_sala)}")
                        except Exception as inner_e:
                            print(f"[WebSocket] No se pudo obtener participantes: {inner_e}")
                except Exception as e:
                    print(f"[WebSocket] Error listando rooms: {e}")

                # Preparar datos del mensaje
                msg_data = {
                    'id': mensaje_id,
                    't': client_id,
                    'c': conversacion_id,
                    'm': contenido,
                    'from': usuario_id,
                    'nombre': session.get('usuario_nombre', 'Usuario'),
                    'ts': datetime.now().timestamp() * 1000,
                    'type': tipo
                }

                # Si es un GIF, incluir la URL
                if tipo == 'gif' and gif_url:
                    msg_data['gif_url'] = gif_url
                    msg_data['media'] = [{
                        'file_path': gif_url,
                        'media_type': 'gif'
                    }]

                print(f"[WebSocket] 📤 Emitiendo msg_data: {msg_data}")
                socketio.emit('msg', msg_data, room=room, skip_sid=request.sid)
                print(f"[WebSocket] ✅ emit() ejecutado a sala {room}")

                # ⚡ SINCRONIZAR OTRAS VENTANAS DEL MISMO USUARIO
                # Emitir a todos los SIDs del remitente (excepto el actual) para sincronizar
                # sus otras ventanas/pestañas (ej: chat grande y mini-chat)
                current_sid = request.sid
                user_sids = usuarios_conectados.get(usuario_id, [])
                for other_sid in user_sids:
                    if other_sid != current_sid:
                        # Agregar flag para que el cliente sepa que es un mensaje propio
                        sync_data = {**msg_data, 'is_own_sync': True}
                        socketio.emit('msg', sync_data, to=other_sid)
                        print(f"[WebSocket] 🔄 Sincronizado a otra ventana del usuario: {other_sid}")

                # Limpiar indicador de escritura
                _limpiar_indicador(conversacion_id, usuario_id)

                print(f"[WebSocket] Mensaje {mensaje_id} emitido exitosamente a {room}")
                logger.info(f"[WebSocket] Mensaje {mensaje_id} enviado por {usuario_id} a {room}")
            else:
                # Error al guardar - emitir msg_failed
                logger.warning(f"[WebSocket] Error guardando mensaje: {resultado.mensaje}")
                emit('msg_failed', {
                    't': client_id,
                    'reason': resultado.mensaje,
                    'code': 'DB_ERROR',
                    'retry': True  # El cliente puede reintentar
                })

        except Exception as e:
            import traceback
            print(f"[WS-DEBUG] ERROR en send: {e}")
            traceback.print_exc()
            logger.error(f"[WebSocket] Error en send: {e}")
            emit('msg_failed', {
                't': client_id,
                'reason': 'Error interno del servidor',
                'code': 'INTERNAL_ERROR',
                'retry': True
            })
        finally:
            # Siempre cerrar la sesion
            if servicio:
                _cerrar_servicio(servicio)

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

    # =========================================================================
    # LLAMADAS WebRTC P2P (senalizacion)
    # =========================================================================

    @socketio.on('call_invite')
    def manejar_call_invite(data):
        """Reenvia invitacion de llamada al usuario destino."""
        print(f"[WebRTC] ========== call_invite recibido: {data}")
        usuario_id = session.get('usuario_id')
        if not usuario_id:
            print(f"[WebRTC] call_invite rechazado: no autenticado")
            return
        target_user_id = data.get('target_user_id')
        if not target_user_id:
            print(f"[WebRTC] call_invite rechazado: sin target_user_id")
            return
        print(f"[WebRTC] Emitiendo call_incoming de {usuario_id} a user_{target_user_id}")
        socketio.emit('call_incoming', {
            'caller_id': usuario_id,
            'caller_name': data.get('caller_name', session.get('usuario_nombre', 'Usuario')),
            'tipo': data.get('tipo', 'audio'),
            'chat_id': data.get('chat_id')
        }, room=f"user_{target_user_id}")
        logger.info(f"[WebRTC] call_invite de {usuario_id} a {target_user_id}")

    @socketio.on('call_accepted')
    def manejar_call_accepted(data):
        """Notifica al llamante que la llamada fue aceptada."""
        usuario_id = session.get('usuario_id')
        print(f"[WebRTC] call_accepted de user {usuario_id}, data: {data}")
        if not usuario_id:
            return
        target_user_id = data.get('target_user_id')
        if not target_user_id:
            return
        print(f"[WebRTC] Emitiendo call_accepted a user_{target_user_id}")
        socketio.emit('call_accepted', {
            'accepted_by': usuario_id
        }, room=f"user_{target_user_id}")

    @socketio.on('call_offer')
    def manejar_call_offer(data):
        """Reenvia SDP offer al usuario destino."""
        usuario_id = session.get('usuario_id')
        print(f"[WebRTC] call_offer de user {usuario_id} a user_{data.get('target_user_id')}")
        if not usuario_id:
            return
        target_user_id = data.get('target_user_id')
        if not target_user_id:
            return
        socketio.emit('call_offer', {
            'from': usuario_id,
            'sdp': data.get('sdp')
        }, room=f"user_{target_user_id}")

    @socketio.on('call_answer')
    def manejar_call_answer(data):
        """Reenvia SDP answer al usuario destino."""
        usuario_id = session.get('usuario_id')
        print(f"[WebRTC] call_answer de user {usuario_id} a user_{data.get('target_user_id')}")
        if not usuario_id:
            return
        target_user_id = data.get('target_user_id')
        if not target_user_id:
            return
        socketio.emit('call_answer', {
            'from': usuario_id,
            'sdp': data.get('sdp')
        }, room=f"user_{target_user_id}")

    @socketio.on('ice_candidate')
    def manejar_ice_candidate(data):
        """Reenvia ICE candidate al usuario destino."""
        usuario_id = session.get('usuario_id')
        if not usuario_id:
            return
        target_user_id = data.get('target_user_id')
        if not target_user_id:
            return
        print(f"[WebRTC] ice_candidate de user {usuario_id} a user_{target_user_id}")
        socketio.emit('ice_candidate', {
            'from': usuario_id,
            'candidate': data.get('candidate')
        }, room=f"user_{target_user_id}")

    @socketio.on('call_hangup')
    def manejar_call_hangup(data):
        """Notifica al otro usuario que la llamada fue colgada."""
        usuario_id = session.get('usuario_id')
        if not usuario_id:
            return
        target_user_id = data.get('target_user_id')
        if not target_user_id:
            return
        socketio.emit('call_hangup', {
            'from': usuario_id
        }, room=f"user_{target_user_id}")
        logger.info(f"[WebRTC] call_hangup de {usuario_id} a {target_user_id}")

    @socketio.on('call_reject')
    def manejar_call_reject(data):
        """Notifica al llamante que la llamada fue rechazada."""
        usuario_id = session.get('usuario_id')
        if not usuario_id:
            return
        target_user_id = data.get('target_user_id')
        if not target_user_id:
            return
        socketio.emit('call_rejected', {
            'rejected_by': usuario_id
        }, room=f"user_{target_user_id}")
        logger.info(f"[WebRTC] call_reject de {usuario_id} a {target_user_id}")

    # =========================================================================
    # AUDIOCONFERENCIA GRUPAL WebRTC (Full Mesh)
    # =========================================================================

    # Tracking en memoria de conferencias activas
    # { room_id: { 'creator': user_id, 'participants': {user_id: user_name, ...}, 'conversation_id': int|None, 'created_at': timestamp } }
    active_conferences = {}

    @socketio.on('conference_invite')
    def manejar_conference_invite(data):
        """
        Inicia una conferencia e invita participantes.
        data: { room_id, room_name, conversation_id (opt), participants: [{id, name}, ...] }
        """
        usuario_id = session.get('usuario_id')
        usuario_nombre = session.get('usuario_nombre', 'Usuario')
        if not usuario_id:
            return

        room_id = data.get('room_id')
        room_name = data.get('room_name', 'Conferencia')
        conversation_id = data.get('conversation_id')
        participants = data.get('participants', [])

        if not room_id or not participants:
            emit('error', {'message': 'room_id y participants requeridos'})
            return

        # Crear sala de conferencia
        active_conferences[room_id] = {
            'creator': usuario_id,
            'participants': {str(usuario_id): usuario_nombre},
            'conversation_id': conversation_id,
            'created_at': time.time(),
            'room_name': room_name
        }

        # El creador se une a la sala Socket.IO
        join_room(f"conference_{room_id}")

        logger.info(f"[Conference] {usuario_nombre} ({usuario_id}) creo conferencia {room_id} con {len(participants)} invitados")

        # Notificar a cada participante invitado
        for p in participants:
            p_id = str(p.get('id', ''))
            if p_id and p_id != str(usuario_id):
                socketio.emit('conference_incoming', {
                    'room_id': room_id,
                    'room_name': room_name,
                    'conversation_id': conversation_id,
                    'caller_id': usuario_id,
                    'caller_name': usuario_nombre,
                    'participants': [{'id': usuario_id, 'name': usuario_nombre}]
                }, room=f"user_{p_id}")

    @socketio.on('conference_join')
    def manejar_conference_join(data):
        """
        Un participante acepta y se une a la conferencia.
        data: { room_id }
        """
        usuario_id = session.get('usuario_id')
        usuario_nombre = session.get('usuario_nombre', 'Usuario')
        if not usuario_id:
            return

        room_id = data.get('room_id')
        if not room_id or room_id not in active_conferences:
            emit('error', {'message': 'Conferencia no encontrada'})
            return

        conf = active_conferences[room_id]

        # Lista de participantes existentes ANTES de agregar al nuevo
        existing_participants = [
            {'id': int(uid), 'name': uname}
            for uid, uname in conf['participants'].items()
        ]

        # Agregar nuevo participante
        conf['participants'][str(usuario_id)] = usuario_nombre

        # Unirse a la sala Socket.IO
        join_room(f"conference_{room_id}")

        logger.info(f"[Conference] {usuario_nombre} ({usuario_id}) se unio a conferencia {room_id}. Total: {len(conf['participants'])}")

        # Notificar a todos los existentes que alguien se unio
        socketio.emit('conference_user_joined', {
            'room_id': room_id,
            'user_id': usuario_id,
            'user_name': usuario_nombre,
            'existing_participants': existing_participants,
            'all_participants': [
                {'id': int(uid), 'name': uname}
                for uid, uname in conf['participants'].items()
            ]
        }, room=f"conference_{room_id}")

    @socketio.on('conference_offer')
    def manejar_conference_offer(data):
        """Reenviar SDP offer a un peer especifico."""
        usuario_id = session.get('usuario_id')
        if not usuario_id:
            return
        target_user_id = data.get('target_user_id')
        if not target_user_id:
            return
        socketio.emit('conference_offer', {
            'from_user_id': usuario_id,
            'from_user_name': session.get('usuario_nombre', 'Usuario'),
            'room_id': data.get('room_id'),
            'sdp': data.get('sdp')
        }, room=f"user_{target_user_id}")

    @socketio.on('conference_answer')
    def manejar_conference_answer(data):
        """Reenviar SDP answer a un peer especifico."""
        usuario_id = session.get('usuario_id')
        if not usuario_id:
            return
        target_user_id = data.get('target_user_id')
        if not target_user_id:
            return
        socketio.emit('conference_answer', {
            'from_user_id': usuario_id,
            'room_id': data.get('room_id'),
            'sdp': data.get('sdp')
        }, room=f"user_{target_user_id}")

    @socketio.on('conference_ice_candidate')
    def manejar_conference_ice_candidate(data):
        """Reenviar ICE candidate a un peer especifico."""
        usuario_id = session.get('usuario_id')
        if not usuario_id:
            return
        target_user_id = data.get('target_user_id')
        if not target_user_id:
            return
        socketio.emit('conference_ice_candidate', {
            'from_user_id': usuario_id,
            'room_id': data.get('room_id'),
            'candidate': data.get('candidate')
        }, room=f"user_{target_user_id}")

    @socketio.on('conference_leave')
    def manejar_conference_leave(data):
        """Un participante abandona la conferencia."""
        usuario_id = session.get('usuario_id')
        usuario_nombre = session.get('usuario_nombre', 'Usuario')
        if not usuario_id:
            return

        room_id = data.get('room_id')
        if not room_id or room_id not in active_conferences:
            return

        conf = active_conferences[room_id]

        # Remover participante
        conf['participants'].pop(str(usuario_id), None)

        # Salir de la sala Socket.IO
        leave_room(f"conference_{room_id}")

        logger.info(f"[Conference] {usuario_nombre} ({usuario_id}) abandono conferencia {room_id}. Quedan: {len(conf['participants'])}")

        if len(conf['participants']) <= 1:
            # Notificar al ultimo que la conferencia termino
            socketio.emit('conference_ended', {
                'room_id': room_id,
                'reason': 'last_participant'
            }, room=f"conference_{room_id}")
            # Limpiar
            del active_conferences[room_id]
            logger.info(f"[Conference] Conferencia {room_id} terminada (ultimo participante)")
        else:
            # Notificar a los demas
            socketio.emit('conference_user_left', {
                'room_id': room_id,
                'user_id': usuario_id,
                'user_name': usuario_nombre,
                'remaining_participants': [
                    {'id': int(uid), 'name': uname}
                    for uid, uname in conf['participants'].items()
                ]
            }, room=f"conference_{room_id}")

    @socketio.on('conference_reject')
    def manejar_conference_reject(data):
        """Un participante rechaza la invitacion."""
        usuario_id = session.get('usuario_id')
        usuario_nombre = session.get('usuario_nombre', 'Usuario')
        if not usuario_id:
            return

        room_id = data.get('room_id')
        if not room_id or room_id not in active_conferences:
            return

        conf = active_conferences[room_id]

        # Notificar al creador
        socketio.emit('conference_user_rejected', {
            'room_id': room_id,
            'user_id': usuario_id,
            'user_name': usuario_nombre
        }, room=f"user_{conf['creator']}")

        logger.info(f"[Conference] {usuario_nombre} ({usuario_id}) rechazo conferencia {room_id}")

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
            servicio = _obtener_servicio_chat()
            resultado = servicio.marcar_entregado(
                mensaje_id=mensaje_id,
                usuario_id=usuario_id
            )

            if resultado.exito:
                _commit_servicio(servicio)
                remitente_id = resultado.datos.get('remitente_id')
                if remitente_id and remitente_id != usuario_id:
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


# =============================================================================
# FUNCIONES AUXILIARES
# =============================================================================

def _obtener_servicio_chat(auto_commit: bool = True):
    """
    Obtiene una instancia del servicio de chat con sesion gestionada.

    Args:
        auto_commit: Si True, hace commit automatico al finalizar operaciones.
                     Necesario para WebSocket ya que no hay ciclo request/response.

    Returns:
        Tupla (ServicioChat, db_session) para permitir commit/rollback manual si es necesario.
    """
    from infraestructura.base_datos.base import obtener_gestor
    from aplicacion.servicios.servicio_chat import ServicioChat
    from infraestructura.persistencia.repositorio_chat_postgresql import (
        RepositorioConversacionPostgreSQL,
        RepositorioParticipantePostgreSQL,
        RepositorioMensajePostgreSQL,
        RepositorioArchivoMensajePostgreSQL,
        RepositorioReaccionPostgreSQL,
        RepositorioPresenciaPostgreSQL,
        RepositorioBloqueoPostgreSQL,
        RepositorioIndicadorAccionPostgreSQL
    )

    gestor = obtener_gestor()
    db_session = gestor.session()

    servicio = ServicioChat(
        repo_conversacion=RepositorioConversacionPostgreSQL(db_session),
        repo_participante=RepositorioParticipantePostgreSQL(db_session),
        repo_mensaje=RepositorioMensajePostgreSQL(db_session),
        repo_archivo=RepositorioArchivoMensajePostgreSQL(db_session),
        repo_reaccion=RepositorioReaccionPostgreSQL(db_session),
        repo_presencia=RepositorioPresenciaPostgreSQL(db_session),
        repo_bloqueo=RepositorioBloqueoPostgreSQL(db_session),
        repo_indicador=RepositorioIndicadorAccionPostgreSQL(db_session)
    )

    # Adjuntar sesion al servicio para poder hacer commit despues
    servicio._db_session = db_session

    return servicio


def _commit_servicio(servicio):
    """Hace commit de la sesion del servicio de chat."""
    if hasattr(servicio, '_db_session') and servicio._db_session:
        try:
            servicio._db_session.commit()
        except Exception as e:
            logger.error(f"[WebSocket] Error en commit: {e}")
            servicio._db_session.rollback()
            raise


def _cerrar_servicio(servicio):
    """Cierra la sesion del servicio de chat."""
    if hasattr(servicio, '_db_session') and servicio._db_session:
        try:
            servicio._db_session.close()
        except Exception as e:
            logger.error(f"[WebSocket] Error cerrando sesion: {e}")


def _es_participante(usuario_id: int, conversacion_id: int) -> bool:
    """Verifica si el usuario es participante de una conversacion."""
    servicio = None
    try:
        servicio = _obtener_servicio_chat()
        conv = servicio.obtener_conversacion(conversacion_id, usuario_id)
        return conv is not None
    except Exception:
        return False
    finally:
        if servicio:
            _cerrar_servicio(servicio)


def _actualizar_presencia_bd(usuario_id: int, en_linea: bool):
    """Actualiza la presencia del usuario en la base de datos."""
    servicio = None
    try:
        servicio = _obtener_servicio_chat()
        servicio.actualizar_presencia(usuario_id, en_linea)
        _commit_servicio(servicio)
    except Exception as e:
        logger.error(f"[WebSocket] Error actualizando presencia: {e}")
    finally:
        if servicio:
            _cerrar_servicio(servicio)


def _emitir_presencia(usuario_id: int, en_linea: bool):
    """Emite el estado de presencia a los contactos del usuario."""
    if socketio:
        presencia_data = {
            'user_id': usuario_id,
            'online': en_linea,
            'timestamp': datetime.now().isoformat()
        }

        # Emitir a todos los usuarios conectados (broadcast)
        # En produccion con Redis, esto escala automaticamente
        socketio.emit('user_presence', presencia_data)

        # Tambien emitir al canal especifico del usuario (para actualizaciones dirigidas)
        socketio.emit('user_presence', presencia_data,
                      room=f"user_{usuario_id}",
                      skip_sid=request.sid if hasattr(request, 'sid') else None)


def _limpiar_indicador(conversacion_id: int, usuario_id: int):
    """Limpia el indicador de escritura y notifica."""
    servicio = None
    try:
        servicio = _obtener_servicio_chat()
        servicio.limpiar_accion(conversacion_id, usuario_id)
        _commit_servicio(servicio)

        if socketio:
            room = f"conversation_{conversacion_id}"
            socketio.emit('user_stopped_typing', {
                'conversation_id': conversacion_id,
                'user_id': usuario_id,
                'timestamp': datetime.now().isoformat()
            }, room=room)
    except Exception as e:
        logger.error(f"[WebSocket] Error limpiando indicador: {e}")
    finally:
        if servicio:
            _cerrar_servicio(servicio)


# =============================================================================
# FUNCIONES PUBLICAS PARA EMITIR DESDE OTROS MODULOS
# =============================================================================

def emitir_mensaje_nuevo(conversacion_id: int, mensaje_data: Dict[str, Any]):
    """
    Emite un nuevo mensaje a una conversacion.

    Usar cuando se envia un mensaje via REST y se quiere notificar via WS.
    Emite tanto 'new_message' (legacy) como 'msg' (v3.0 UltraFast).
    """
    if socketio:
        room = f"conversation_{conversacion_id}"

        print(f"[WebSocket] 📤 emitir_mensaje_nuevo llamado")
        print(f"[WebSocket] 📤 mensaje_data keys: {list(mensaje_data.keys())}")
        print(f"[WebSocket] 📤 tipo: {mensaje_data.get('tipo')}, gif_url: {mensaje_data.get('gif_url')}")

        # Emitir en formato legacy para compatibilidad
        socketio.emit('new_message', mensaje_data, room=room)

        # Obtener nombre del remitente
        remitente = mensaje_data.get('remitente', {})
        nombre_remitente = remitente.get('nombre', '') if isinstance(remitente, dict) else ''

        # Obtener el remitente_id correctamente
        remitente_id = mensaje_data.get('remitente_id')
        if not remitente_id and isinstance(remitente, dict):
            remitente_id = remitente.get('id')

        # También emitir en formato compacto v3.0 para ChatUltraFast
        from datetime import datetime
        msg_compact = {
            'id': mensaje_data.get('id'),
            'c': conversacion_id,
            'm': mensaje_data.get('contenido') or mensaje_data.get('content', ''),
            'from': remitente_id or mensaje_data.get('sender_id'),
            'ts': int(datetime.now().timestamp() * 1000),
            'type': mensaje_data.get('tipo') or mensaje_data.get('type', 'text'),
            'gif_url': mensaje_data.get('gif_url'),
            'nombre': nombre_remitente
        }
        print(f"[WebSocket] 📤 Emitiendo 'msg' v3.0 a sala {room}: {msg_compact}")
        socketio.emit('msg', msg_compact, room=room)


def emitir_notificacion(usuario_id: int, notificacion: Dict[str, Any]):
    """
    Emite una notificacion a un usuario especifico.

    Args:
        usuario_id: ID del usuario destino
        notificacion: Datos de la notificacion
    """
    if socketio:
        room = f"user_{usuario_id}"
        socketio.emit('notification', notificacion, room=room)


def emitir_a_conversacion(conversacion_id: int, evento: str, data: Dict[str, Any]):
    """
    Emite un evento a todos los participantes de una conversacion.

    Args:
        conversacion_id: ID de la conversacion
        evento: Nombre del evento
        data: Datos a enviar
    """
    if socketio:
        room = f"conversation_{conversacion_id}"
        socketio.emit(evento, data, room=room)


def esta_usuario_conectado(usuario_id: int) -> bool:
    """
    Verifica si un usuario tiene conexiones activas.

    Args:
        usuario_id: ID del usuario

    Returns:
        True si tiene al menos una conexion activa
    """
    # Local primero (rápido)
    if usuario_id in usuarios_conectados and usuarios_conectados[usuario_id]:
        return True
    # Redis distribuido
    if _ws_redis:
        try:
            return _ws_redis.scard(f"chat:ws:user:{usuario_id}") > 0
        except Exception:
            pass
    return False


def obtener_usuarios_conectados() -> Set[int]:
    """
    Obtiene el conjunto de usuarios conectados.

    Returns:
        Set de IDs de usuarios conectados
    """
    return set(usuarios_conectados.keys())
