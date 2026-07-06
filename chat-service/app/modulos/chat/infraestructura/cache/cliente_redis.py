# -*- coding: utf-8 -*-
"""
Cliente Redis - Conexion y Utilidades Base

Maneja la conexion a Redis y proporciona utilidades comunes.

Autor: Wilson Arguello
Correo: gestiontecnologia@maquita.com.ec
Fecha: 2026-01-02
"""

import json
import logging
from typing import Optional, Any, Union
from datetime import datetime
from functools import wraps

try:
    import redis
    from redis import ConnectionPool, Redis
    REDIS_DISPONIBLE = True
except ImportError:
    REDIS_DISPONIBLE = False
    redis = None
    ConnectionPool = None
    Redis = None

logger = logging.getLogger(__name__)

# Pool de conexiones global (singleton)
_pool: Optional['ConnectionPool'] = None
_cliente: Optional['ClienteRedis'] = None


class ClienteRedis:
    """
    Cliente Redis con manejo de errores y serialización.

    Características:
    - Pool de conexiones para eficiencia
    - Serialización JSON automática
    - Fallback silencioso si Redis no está disponible
    - Prefijos de claves para namespace
    """

    PREFIJO_BASE = "chat:"

    def __init__(
        self,
        host: str = 'localhost',
        port: int = 6379,
        db: int = 0,
        password: Optional[str] = None,
        decode_responses: bool = True,
        socket_timeout: float = 5.0,
        socket_connect_timeout: float = 5.0,
        max_connections: int = 50
    ):
        """
        Inicializa el cliente Redis.

        Args:
            host: Host de Redis
            port: Puerto de Redis
            db: Número de base de datos
            password: Contraseña (opcional)
            decode_responses: Decodificar respuestas a string
            socket_timeout: Timeout de socket en segundos
            socket_connect_timeout: Timeout de conexión
            max_connections: Máximo de conexiones en el pool
        """
        self._disponible = REDIS_DISPONIBLE
        self._redis: Optional[Redis] = None

        if not REDIS_DISPONIBLE:
            logger.warning(
                "Redis no está instalado. Cache deshabilitado. "
                "Instalar con: pip install redis"
            )
            return

        try:
            global _pool
            if _pool is None:
                _pool = ConnectionPool(
                    host=host,
                    port=port,
                    db=db,
                    password=password,
                    decode_responses=decode_responses,
                    socket_timeout=socket_timeout,
                    socket_connect_timeout=socket_connect_timeout,
                    max_connections=max_connections
                )

            self._redis = Redis(connection_pool=_pool)
            # Verificar conexión
            self._redis.ping()
            logger.info(f"Conectado a Redis en {host}:{port}/{db}")

        except Exception as e:
            logger.error(f"Error conectando a Redis: {e}")
            self._disponible = False
            self._redis = None

    @property
    def disponible(self) -> bool:
        """Indica si Redis está disponible."""
        return self._disponible and self._redis is not None

    @property
    def cliente(self) -> Optional[Redis]:
        """Retorna el cliente Redis nativo."""
        return self._redis

    def _clave(self, *partes: Union[str, int]) -> str:
        """Genera una clave con el prefijo base."""
        return self.PREFIJO_BASE + ":".join(str(p) for p in partes)

    # ═══════════════════════════════════════════════════════════════════════
    # OPERACIONES BÁSICAS
    # ═══════════════════════════════════════════════════════════════════════

    def get(self, clave: str) -> Optional[str]:
        """Obtiene un valor."""
        if not self.disponible:
            return None
        try:
            return self._redis.get(clave)
        except Exception as e:
            logger.error(f"Error en GET {clave}: {e}")
            return None

    def set(
        self,
        clave: str,
        valor: str,
        ttl_segundos: Optional[int] = None
    ) -> bool:
        """Establece un valor con TTL opcional."""
        if not self.disponible:
            return False
        try:
            if ttl_segundos:
                self._redis.setex(clave, ttl_segundos, valor)
            else:
                self._redis.set(clave, valor)
            return True
        except Exception as e:
            logger.error(f"Error en SET {clave}: {e}")
            return False

    def delete(self, *claves: str) -> int:
        """Elimina una o más claves."""
        if not self.disponible:
            return 0
        try:
            return self._redis.delete(*claves)
        except Exception as e:
            logger.error(f"Error en DELETE: {e}")
            return 0

    def exists(self, clave: str) -> bool:
        """Verifica si una clave existe."""
        if not self.disponible:
            return False
        try:
            return bool(self._redis.exists(clave))
        except Exception as e:
            logger.error(f"Error en EXISTS {clave}: {e}")
            return False

    def expire(self, clave: str, segundos: int) -> bool:
        """Establece TTL en una clave existente."""
        if not self.disponible:
            return False
        try:
            return bool(self._redis.expire(clave, segundos))
        except Exception as e:
            logger.error(f"Error en EXPIRE {clave}: {e}")
            return False

    def ttl(self, clave: str) -> int:
        """Obtiene el TTL restante de una clave."""
        if not self.disponible:
            return -2
        try:
            return self._redis.ttl(clave)
        except Exception as e:
            logger.error(f"Error en TTL {clave}: {e}")
            return -2

    # ═══════════════════════════════════════════════════════════════════════
    # OPERACIONES JSON
    # ═══════════════════════════════════════════════════════════════════════

    def get_json(self, clave: str) -> Optional[Any]:
        """Obtiene y deserializa un valor JSON."""
        valor = self.get(clave)
        if valor is None:
            return None
        try:
            return json.loads(valor)
        except json.JSONDecodeError as e:
            logger.error(f"Error deserializando JSON de {clave}: {e}")
            return None

    def set_json(
        self,
        clave: str,
        valor: Any,
        ttl_segundos: Optional[int] = None
    ) -> bool:
        """Serializa y guarda un valor como JSON."""
        try:
            valor_json = json.dumps(valor, default=self._serializar_datetime)
            return self.set(clave, valor_json, ttl_segundos)
        except (TypeError, ValueError) as e:
            logger.error(f"Error serializando JSON para {clave}: {e}")
            return False

    def _serializar_datetime(self, obj: Any) -> str:
        """Serializa objetos datetime a ISO format."""
        if isinstance(obj, datetime):
            return obj.isoformat()
        raise TypeError(f"Objeto no serializable: {type(obj)}")

    # ═══════════════════════════════════════════════════════════════════════
    # OPERACIONES DE LISTA
    # ═══════════════════════════════════════════════════════════════════════

    def lpush(self, clave: str, *valores: str) -> int:
        """Agrega valores al inicio de una lista."""
        if not self.disponible:
            return 0
        try:
            return self._redis.lpush(clave, *valores)
        except Exception as e:
            logger.error(f"Error en LPUSH {clave}: {e}")
            return 0

    def rpush(self, clave: str, *valores: str) -> int:
        """Agrega valores al final de una lista."""
        if not self.disponible:
            return 0
        try:
            return self._redis.rpush(clave, *valores)
        except Exception as e:
            logger.error(f"Error en RPUSH {clave}: {e}")
            return 0

    def lrange(self, clave: str, inicio: int, fin: int) -> list:
        """Obtiene un rango de elementos de una lista."""
        if not self.disponible:
            return []
        try:
            return self._redis.lrange(clave, inicio, fin)
        except Exception as e:
            logger.error(f"Error en LRANGE {clave}: {e}")
            return []

    def ltrim(self, clave: str, inicio: int, fin: int) -> bool:
        """Recorta una lista al rango especificado."""
        if not self.disponible:
            return False
        try:
            self._redis.ltrim(clave, inicio, fin)
            return True
        except Exception as e:
            logger.error(f"Error en LTRIM {clave}: {e}")
            return False

    def llen(self, clave: str) -> int:
        """Obtiene la longitud de una lista."""
        if not self.disponible:
            return 0
        try:
            return self._redis.llen(clave)
        except Exception as e:
            logger.error(f"Error en LLEN {clave}: {e}")
            return 0

    # ═══════════════════════════════════════════════════════════════════════
    # OPERACIONES DE SET
    # ═══════════════════════════════════════════════════════════════════════

    def sadd(self, clave: str, *valores: str) -> int:
        """Agrega valores a un set."""
        if not self.disponible:
            return 0
        try:
            return self._redis.sadd(clave, *valores)
        except Exception as e:
            logger.error(f"Error en SADD {clave}: {e}")
            return 0

    def srem(self, clave: str, *valores: str) -> int:
        """Elimina valores de un set."""
        if not self.disponible:
            return 0
        try:
            return self._redis.srem(clave, *valores)
        except Exception as e:
            logger.error(f"Error en SREM {clave}: {e}")
            return 0

    def smembers(self, clave: str) -> set:
        """Obtiene todos los miembros de un set."""
        if not self.disponible:
            return set()
        try:
            return self._redis.smembers(clave)
        except Exception as e:
            logger.error(f"Error en SMEMBERS {clave}: {e}")
            return set()

    def sismember(self, clave: str, valor: str) -> bool:
        """Verifica si un valor es miembro del set."""
        if not self.disponible:
            return False
        try:
            return bool(self._redis.sismember(clave, valor))
        except Exception as e:
            logger.error(f"Error en SISMEMBER {clave}: {e}")
            return False

    def scard(self, clave: str) -> int:
        """Obtiene la cardinalidad de un set."""
        if not self.disponible:
            return 0
        try:
            return self._redis.scard(clave)
        except Exception as e:
            logger.error(f"Error en SCARD {clave}: {e}")
            return 0

    # ═══════════════════════════════════════════════════════════════════════
    # OPERACIONES DE HASH
    # ═══════════════════════════════════════════════════════════════════════

    def hset(self, clave: str, campo: str, valor: str) -> int:
        """Establece un campo en un hash."""
        if not self.disponible:
            return 0
        try:
            return self._redis.hset(clave, campo, valor)
        except Exception as e:
            logger.error(f"Error en HSET {clave}.{campo}: {e}")
            return 0

    def hget(self, clave: str, campo: str) -> Optional[str]:
        """Obtiene un campo de un hash."""
        if not self.disponible:
            return None
        try:
            return self._redis.hget(clave, campo)
        except Exception as e:
            logger.error(f"Error en HGET {clave}.{campo}: {e}")
            return None

    def hgetall(self, clave: str) -> dict:
        """Obtiene todos los campos de un hash."""
        if not self.disponible:
            return {}
        try:
            return self._redis.hgetall(clave)
        except Exception as e:
            logger.error(f"Error en HGETALL {clave}: {e}")
            return {}

    def hdel(self, clave: str, *campos: str) -> int:
        """Elimina campos de un hash."""
        if not self.disponible:
            return 0
        try:
            return self._redis.hdel(clave, *campos)
        except Exception as e:
            logger.error(f"Error en HDEL {clave}: {e}")
            return 0

    def hincrby(self, clave: str, campo: str, cantidad: int = 1) -> int:
        """Incrementa un campo numérico en un hash."""
        if not self.disponible:
            return 0
        try:
            return self._redis.hincrby(clave, campo, cantidad)
        except Exception as e:
            logger.error(f"Error en HINCRBY {clave}.{campo}: {e}")
            return 0

    # ═══════════════════════════════════════════════════════════════════════
    # OPERACIONES ATÓMICAS
    # ═══════════════════════════════════════════════════════════════════════

    def incr(self, clave: str) -> int:
        """Incrementa un contador."""
        if not self.disponible:
            return 0
        try:
            return self._redis.incr(clave)
        except Exception as e:
            logger.error(f"Error en INCR {clave}: {e}")
            return 0

    def decr(self, clave: str) -> int:
        """Decrementa un contador."""
        if not self.disponible:
            return 0
        try:
            return self._redis.decr(clave)
        except Exception as e:
            logger.error(f"Error en DECR {clave}: {e}")
            return 0

    # ═══════════════════════════════════════════════════════════════════════
    # PIPELINE (OPERACIONES BATCH)
    # ═══════════════════════════════════════════════════════════════════════

    def pipeline(self):
        """Crea un pipeline para operaciones batch."""
        if not self.disponible:
            return None
        return self._redis.pipeline()

    # ═══════════════════════════════════════════════════════════════════════
    # PUB/SUB
    # ═══════════════════════════════════════════════════════════════════════

    def publish(self, canal: str, mensaje: str) -> int:
        """Publica un mensaje en un canal."""
        if not self.disponible:
            return 0
        try:
            return self._redis.publish(canal, mensaje)
        except Exception as e:
            logger.error(f"Error en PUBLISH {canal}: {e}")
            return 0

    def pubsub(self):
        """Crea un objeto PubSub para suscripciones."""
        if not self.disponible:
            return None
        return self._redis.pubsub()

    # ═══════════════════════════════════════════════════════════════════════
    # UTILIDADES
    # ═══════════════════════════════════════════════════════════════════════

    def keys(self, patron: str) -> list:
        """Busca claves por patrón (usar con cuidado en producción)."""
        if not self.disponible:
            return []
        try:
            return self._redis.keys(patron)
        except Exception as e:
            logger.error(f"Error en KEYS {patron}: {e}")
            return []

    def scan_iter(self, match: str, count: int = 100):
        """Itera sobre claves de forma eficiente."""
        if not self.disponible:
            return iter([])
        try:
            return self._redis.scan_iter(match=match, count=count)
        except Exception as e:
            logger.error(f"Error en SCAN_ITER {match}: {e}")
            return iter([])

    def flushdb(self) -> bool:
        """Limpia toda la base de datos (PELIGROSO)."""
        if not self.disponible:
            return False
        try:
            self._redis.flushdb()
            return True
        except Exception as e:
            logger.error(f"Error en FLUSHDB: {e}")
            return False

    def info(self) -> dict:
        """Obtiene información del servidor Redis."""
        if not self.disponible:
            return {}
        try:
            return self._redis.info()
        except Exception as e:
            logger.error(f"Error en INFO: {e}")
            return {}


# ═══════════════════════════════════════════════════════════════════════════
# SINGLETON
# ═══════════════════════════════════════════════════════════════════════════

def obtener_cliente_redis(
    host: str = 'localhost',
    port: int = 6379,
    db: int = 0,
    password: Optional[str] = None
) -> ClienteRedis:
    """
    Obtiene el cliente Redis singleton.

    Uso:
        redis = obtener_cliente_redis()
        redis.set('clave', 'valor')
    """
    global _cliente
    if _cliente is None:
        _cliente = ClienteRedis(
            host=host,
            port=port,
            db=db,
            password=password
        )
    return _cliente


def fallback_si_redis_no_disponible(valor_defecto=None):
    """
    Decorador que retorna valor por defecto si Redis no está disponible.

    Uso:
        @fallback_si_redis_no_disponible(valor_defecto=[])
        def obtener_mensajes(self, conv_id):
            ...
    """
    def decorator(func):
        @wraps(func)
        def wrapper(self, *args, **kwargs):
            if not getattr(self, '_redis', None) or not self._redis.disponible:
                return valor_defecto
            return func(self, *args, **kwargs)
        return wrapper
    return decorator
