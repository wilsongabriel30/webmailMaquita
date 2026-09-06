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
import os
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
sesion_de_socket: Dict[str, str] = {}  # {sid de Socket.IO: sid de la sesión del correo} (F-03)

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

    # [A-6] Origenes permitidos para Socket.IO. Antes era "*" CON credenciales: desde
    # cualquier web se podia abrir un socket con la sesion de quien la visitara y leer
    # su chat en tiempo real. Ahora es una lista blanca explicita.
    # Se configura con CHAT_CORS_ORIGENES (separados por coma). Sin variable se usan
    # los origenes conocidos del despliegue; nunca se vuelve a "*".
    _origenes = [o.strip() for o in os.environ.get('CHAT_CORS_ORIGENES', '').split(',') if o.strip()]
    if not _origenes:
        # TODOS los sitios que embeben el chat. Omitir uno lo rompe para esos
        # usuarios: al aplicar la lista blanca faltaba Raices (datos.maquita.com.ec)
        # y sus conexiones quedaron rechazadas hasta que se anadio.
        _origenes = [
            'https://mensajeria.maquita.org',   # origen propio del chat
            'https://mail.maquita.org',         # correo (hasta la fase D)
            'https://datos.maquita.com.ec',     # Raices
            'https://faro.maquita.org',         # Raices (nombre alterno)
            'https://drive.maquita.com.ec',     # Drive de Raices
        ]
    logger.info(f"[WebSocket] Origenes permitidos: {_origenes}")

    if redis_url:
        # Usar Redis para escalar a multiples workers
        socketio = SocketIO(
            app,
            cors_allowed_origins=_origenes,
            async_mode=os.getenv('CHAT_SOCKETIO_ASYNC_MODE', 'eventlet'),
            message_queue=redis_url,
            logger=sio_logger,
            engineio_logger=eio_logger
        )
        logger.info(f"[WebSocket] Configurado con Redis: {redis_url}")
    else:
        # Modo desarrollo sin Redis
        socketio = SocketIO(
            app,
            cors_allowed_origins=_origenes,
            async_mode=os.getenv('CHAT_SOCKETIO_ASYNC_MODE', 'eventlet'),
            logger=sio_logger,
            engineio_logger=eio_logger
        )
        logger.info("[WebSocket] Configurado en modo desarrollo (sin Redis)")

    # Registrar manejadores de eventos
    _registrar_eventos()

    return socketio


def _registrar_eventos():
    """Registra todos los manejadores de eventos WebSocket (partidos por responsabilidad el 28/08/2026)."""
    from interfaces.websocket import ws_conexion   # Conexión y desconexión
    ws_conexion.registrar(socketio)
    from interfaces.websocket import ws_mensajeria   # Salas (join/leave), mensajes (enviar/editar/eliminar/leído), escribiendo (normal y con expiración) y el canal rápido que los reutiliza
    ws_mensajeria.registrar(socketio)
    from interfaces.websocket import ws_reacciones   # Reacciones
    ws_reacciones.registrar(socketio)
    from interfaces.websocket import ws_presencia   # Latido y presencia
    ws_presencia.registrar(socketio)
    from interfaces.websocket import ws_consultas   # Consultas por socket: conversaciones, mensajes, directo, búsqueda
    ws_consultas.registrar(socketio)
    from interfaces.websocket import ws_llamadas   # Señalización de llamadas 1a1 (invite/accept/offer/answer/ice/hangup/reject)
    ws_llamadas.registrar(socketio)
    from interfaces.websocket import ws_conferencias   # Conferencias grupales (invite/join/offer/answer/ice/leave/reject)
    ws_conferencias.registrar(socketio)
    from interfaces.websocket import ws_sincronizacion   # sync_chat
    ws_sincronizacion.registrar(socketio)
    from interfaces.websocket import ws_entregas   # Confirmaciones de entrega y lectura por lote
    ws_entregas.registrar(socketio)

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

        # Canal único de notificaciones (evento 'notificacion' a user_<id>)
        try:
            from interfaces.websocket.notificaciones_globales import notificar_mensaje
            notificar_mensaje(conversacion_id, msg_compact['from'], nombre_remitente, msg_compact['m'],
                              msg_compact['type'], msg_compact['id'], mensaje_data.get('menciones') or mensaje_data.get('mentions'))
        except Exception as _e:
            print(f"[notificaciones] {_e}")


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
