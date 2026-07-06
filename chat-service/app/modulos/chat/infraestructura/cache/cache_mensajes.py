# -*- coding: utf-8 -*-
"""
Cache de Mensajes - Implementación Redis

Almacena mensajes recientes para acceso ultra-rápido.
Latencia objetivo: < 5ms

Autor: Wilson Arguello
Correo: gestiontecnologia@maquita.com.ec
Fecha: 2026-01-02
"""

import json
import logging
from typing import Optional, List, Dict, Any

from ...dominio.repositorios.repositorio_cache import CacheMensajes
from .cliente_redis import ClienteRedis, obtener_cliente_redis

logger = logging.getLogger(__name__)


class CacheMensajesRedis(CacheMensajes):
    """
    Implementación Redis de cache de mensajes.

    Estructura de claves:
    - chat:msg:{conversacion_id} -> Lista JSON de mensajes (más recientes primero)

    Estrategia:
    - Guarda últimos 100 mensajes por conversación
    - TTL de 1 hora (refresh al acceder)
    - Push al inicio para mensajes nuevos
    """

    PREFIJO = "chat:msg:"
    MAX_MENSAJES = 100
    TTL_DEFECTO = 3600  # 1 hora

    def __init__(self, cliente: Optional[ClienteRedis] = None):
        """
        Inicializa el cache de mensajes.

        Args:
            cliente: Cliente Redis (usa singleton si no se proporciona)
        """
        self._redis = cliente or obtener_cliente_redis()

    def _clave(self, conversacion_id: int) -> str:
        return f"{self.PREFIJO}{conversacion_id}"

    def obtener_mensajes_recientes(
        self,
        conversacion_id: int,
        limite: int = 50
    ) -> Optional[List[Dict[str, Any]]]:
        """
        Obtiene mensajes recientes del cache.
        Retorna None si no hay cache (cache miss).
        """
        if not self._redis.disponible:
            return None

        try:
            clave = self._clave(conversacion_id)

            # Verificar si existe
            if not self._redis.exists(clave):
                return None

            # Obtener mensajes (lista de JSON strings)
            mensajes_raw = self._redis.lrange(clave, 0, limite - 1)

            if not mensajes_raw:
                return None

            # Deserializar
            mensajes = []
            for msg_str in mensajes_raw:
                try:
                    mensajes.append(json.loads(msg_str))
                except json.JSONDecodeError:
                    logger.warning(f"Mensaje corrupto en cache: {msg_str[:50]}")

            # Refresh TTL
            self._redis.expire(clave, self.TTL_DEFECTO)

            logger.debug(
                f"Cache HIT: {len(mensajes)} mensajes de conv {conversacion_id}"
            )
            return mensajes

        except Exception as e:
            logger.error(
                f"Error obteniendo mensajes de cache para conv {conversacion_id}: {e}"
            )
            return None

    def guardar_mensajes_recientes(
        self,
        conversacion_id: int,
        mensajes: List[Dict[str, Any]],
        ttl_segundos: int = TTL_DEFECTO
    ) -> bool:
        """
        Guarda mensajes en cache (reemplaza existentes).
        """
        if not self._redis.disponible:
            return False

        if not mensajes:
            return True

        try:
            clave = self._clave(conversacion_id)

            # Serializar mensajes
            mensajes_json = []
            for msg in mensajes[:self.MAX_MENSAJES]:
                try:
                    mensajes_json.append(json.dumps(msg, default=str))
                except (TypeError, ValueError) as e:
                    logger.warning(f"Error serializando mensaje: {e}")

            if not mensajes_json:
                return False

            pipe = self._redis.pipeline()
            if not pipe:
                return False

            # Eliminar lista existente y crear nueva
            pipe.delete(clave)
            pipe.rpush(clave, *mensajes_json)
            pipe.expire(clave, ttl_segundos)
            pipe.execute()

            logger.debug(
                f"Cache SET: {len(mensajes_json)} mensajes para conv {conversacion_id}"
            )
            return True

        except Exception as e:
            logger.error(
                f"Error guardando mensajes en cache para conv {conversacion_id}: {e}"
            )
            return False

    def agregar_mensaje(
        self,
        conversacion_id: int,
        mensaje: Dict[str, Any]
    ) -> bool:
        """
        Agrega un mensaje nuevo al cache existente (push al inicio).
        """
        if not self._redis.disponible:
            return False

        try:
            clave = self._clave(conversacion_id)

            # Solo agregar si el cache existe
            if not self._redis.exists(clave):
                return False

            # Serializar mensaje
            try:
                mensaje_json = json.dumps(mensaje, default=str)
            except (TypeError, ValueError) as e:
                logger.warning(f"Error serializando mensaje nuevo: {e}")
                return False

            pipe = self._redis.pipeline()
            if not pipe:
                return False

            # Push al inicio (mensajes más recientes primero)
            pipe.lpush(clave, mensaje_json)
            # Mantener solo MAX_MENSAJES
            pipe.ltrim(clave, 0, self.MAX_MENSAJES - 1)
            # Refresh TTL
            pipe.expire(clave, self.TTL_DEFECTO)
            pipe.execute()

            logger.debug(
                f"Cache ADD: mensaje {mensaje.get('id')} a conv {conversacion_id}"
            )
            return True

        except Exception as e:
            logger.error(
                f"Error agregando mensaje a cache para conv {conversacion_id}: {e}"
            )
            return False

    def actualizar_mensaje(
        self,
        conversacion_id: int,
        mensaje_id: int,
        datos: Dict[str, Any]
    ) -> bool:
        """
        Actualiza un mensaje en cache (edición).
        """
        if not self._redis.disponible:
            return False

        try:
            clave = self._clave(conversacion_id)

            # Obtener todos los mensajes
            mensajes_raw = self._redis.lrange(clave, 0, -1)
            if not mensajes_raw:
                return False

            # Buscar y actualizar el mensaje
            actualizado = False
            nuevos_mensajes = []

            for msg_str in mensajes_raw:
                try:
                    msg = json.loads(msg_str)
                    if msg.get('id') == mensaje_id:
                        # Actualizar campos
                        msg.update(datos)
                        actualizado = True
                    nuevos_mensajes.append(json.dumps(msg, default=str))
                except json.JSONDecodeError:
                    nuevos_mensajes.append(msg_str)

            if not actualizado:
                return False

            # Reemplazar lista
            pipe = self._redis.pipeline()
            if not pipe:
                return False

            pipe.delete(clave)
            if nuevos_mensajes:
                pipe.rpush(clave, *nuevos_mensajes)
            pipe.expire(clave, self.TTL_DEFECTO)
            pipe.execute()

            logger.debug(
                f"Cache UPDATE: mensaje {mensaje_id} en conv {conversacion_id}"
            )
            return True

        except Exception as e:
            logger.error(
                f"Error actualizando mensaje en cache: {e}"
            )
            return False

    def eliminar_mensaje(
        self,
        conversacion_id: int,
        mensaje_id: int
    ) -> bool:
        """
        Elimina un mensaje del cache.
        """
        if not self._redis.disponible:
            return False

        try:
            clave = self._clave(conversacion_id)

            # Obtener todos los mensajes
            mensajes_raw = self._redis.lrange(clave, 0, -1)
            if not mensajes_raw:
                return False

            # Filtrar el mensaje a eliminar
            nuevos_mensajes = []
            eliminado = False

            for msg_str in mensajes_raw:
                try:
                    msg = json.loads(msg_str)
                    if msg.get('id') == mensaje_id:
                        eliminado = True
                        continue
                    nuevos_mensajes.append(msg_str)
                except json.JSONDecodeError:
                    nuevos_mensajes.append(msg_str)

            if not eliminado:
                return False

            # Reemplazar lista
            pipe = self._redis.pipeline()
            if not pipe:
                return False

            pipe.delete(clave)
            if nuevos_mensajes:
                pipe.rpush(clave, *nuevos_mensajes)
            pipe.expire(clave, self.TTL_DEFECTO)
            pipe.execute()

            logger.debug(
                f"Cache DELETE: mensaje {mensaje_id} de conv {conversacion_id}"
            )
            return True

        except Exception as e:
            logger.error(
                f"Error eliminando mensaje de cache: {e}"
            )
            return False

    def invalidar(self, conversacion_id: int) -> bool:
        """
        Invalida todo el cache de una conversación.
        """
        if not self._redis.disponible:
            return False

        try:
            clave = self._clave(conversacion_id)
            self._redis.delete(clave)
            logger.debug(f"Cache INVALIDATE: conv {conversacion_id}")
            return True
        except Exception as e:
            logger.error(
                f"Error invalidando cache de conv {conversacion_id}: {e}"
            )
            return False

    def obtener_estadisticas(self) -> Dict[str, Any]:
        """
        Obtiene estadísticas del cache de mensajes.
        """
        if not self._redis.disponible:
            return {"disponible": False}

        try:
            patron = f"{self.PREFIJO}*"
            total_conversaciones = 0
            total_mensajes = 0

            for clave in self._redis.scan_iter(patron):
                total_conversaciones += 1
                total_mensajes += self._redis.llen(clave)

            return {
                "disponible": True,
                "conversaciones_cacheadas": total_conversaciones,
                "mensajes_totales": total_mensajes,
                "max_mensajes_por_conv": self.MAX_MENSAJES,
                "ttl_segundos": self.TTL_DEFECTO
            }

        except Exception as e:
            logger.error(f"Error obteniendo estadísticas: {e}")
            return {"disponible": True, "error": str(e)}
