# -*- coding: utf-8 -*-
"""
Cache de Conversación - Implementación Redis

Almacena metadata de conversaciones y contadores de no leídos.
Latencia objetivo: < 2ms

Autor: Wilson Arguello
Correo: gestiontecnologia@maquita.com.ec
Fecha: 2026-01-02
"""

import json
import logging
from typing import Optional, List, Dict, Any

from ...dominio.repositorios.repositorio_cache import CacheConversacion
from .cliente_redis import ClienteRedis, obtener_cliente_redis

logger = logging.getLogger(__name__)


class CacheConversacionRedis(CacheConversacion):
    """
    Implementación Redis de cache de conversaciones.

    Estructura de claves:
    - chat:conv:{conversacion_id}          -> Hash con metadata
    - chat:conv:participants:{conv_id}     -> Set de usuario_ids
    - chat:unread:{usuario_id}:{conv_id}   -> Contador de no leídos
    """

    PREFIJO_CONV = "chat:conv:"
    PREFIJO_PARTICIPANTS = "chat:conv:participants:"
    PREFIJO_UNREAD = "chat:unread:"
    TTL_DEFECTO = 1800  # 30 minutos

    def __init__(self, cliente: Optional[ClienteRedis] = None):
        """
        Inicializa el cache de conversaciones.

        Args:
            cliente: Cliente Redis (usa singleton si no se proporciona)
        """
        self._redis = cliente or obtener_cliente_redis()

    def _clave_conv(self, conversacion_id: int) -> str:
        return f"{self.PREFIJO_CONV}{conversacion_id}"

    def _clave_participants(self, conversacion_id: int) -> str:
        return f"{self.PREFIJO_PARTICIPANTS}{conversacion_id}"

    def _clave_unread(self, usuario_id: int, conversacion_id: int) -> str:
        return f"{self.PREFIJO_UNREAD}{usuario_id}:{conversacion_id}"

    def obtener_conversacion(
        self,
        conversacion_id: int
    ) -> Optional[Dict[str, Any]]:
        """
        Obtiene metadata de conversación del cache.
        """
        if not self._redis.disponible:
            return None

        try:
            clave = self._clave_conv(conversacion_id)
            datos = self._redis.hgetall(clave)

            if not datos:
                return None

            # Deserializar campos JSON
            resultado = {}
            for k, v in datos.items():
                if k in ('configuracion', 'metadata'):
                    try:
                        resultado[k] = json.loads(v)
                    except json.JSONDecodeError:
                        resultado[k] = v
                else:
                    resultado[k] = v

            # Refresh TTL
            self._redis.expire(clave, self.TTL_DEFECTO)

            logger.debug(f"Cache HIT: conversacion {conversacion_id}")
            return resultado

        except Exception as e:
            logger.error(
                f"Error obteniendo conversacion {conversacion_id} de cache: {e}"
            )
            return None

    def guardar_conversacion(
        self,
        conversacion_id: int,
        datos: Dict[str, Any],
        ttl_segundos: int = TTL_DEFECTO
    ) -> bool:
        """
        Guarda metadata de conversación.
        """
        if not self._redis.disponible:
            return False

        try:
            clave = self._clave_conv(conversacion_id)

            # Serializar campos complejos
            datos_redis = {}
            for k, v in datos.items():
                if isinstance(v, (dict, list)):
                    datos_redis[k] = json.dumps(v, default=str)
                elif v is not None:
                    datos_redis[k] = str(v)

            if not datos_redis:
                return False

            pipe = self._redis.pipeline()
            if not pipe:
                return False

            # Guardar como hash
            for k, v in datos_redis.items():
                pipe.hset(clave, k, v)
            pipe.expire(clave, ttl_segundos)
            pipe.execute()

            logger.debug(f"Cache SET: conversacion {conversacion_id}")
            return True

        except Exception as e:
            logger.error(
                f"Error guardando conversacion {conversacion_id} en cache: {e}"
            )
            return False

    def obtener_participantes(
        self,
        conversacion_id: int
    ) -> Optional[List[int]]:
        """
        Obtiene IDs de participantes activos (para broadcast).
        """
        if not self._redis.disponible:
            return None

        try:
            clave = self._clave_participants(conversacion_id)

            if not self._redis.exists(clave):
                return None

            miembros = self._redis.smembers(clave)
            participantes = [int(m) for m in miembros if m.isdigit()]

            # Refresh TTL
            self._redis.expire(clave, self.TTL_DEFECTO)

            logger.debug(
                f"Cache HIT: {len(participantes)} participantes de conv {conversacion_id}"
            )
            return participantes

        except Exception as e:
            logger.error(
                f"Error obteniendo participantes de conv {conversacion_id}: {e}"
            )
            return None

    def guardar_participantes(
        self,
        conversacion_id: int,
        usuario_ids: List[int],
        ttl_segundos: int = TTL_DEFECTO
    ) -> bool:
        """
        Guarda lista de participantes.
        """
        if not self._redis.disponible:
            return False

        if not usuario_ids:
            return True

        try:
            clave = self._clave_participants(conversacion_id)

            pipe = self._redis.pipeline()
            if not pipe:
                return False

            # Eliminar set existente y crear nuevo
            pipe.delete(clave)
            pipe.sadd(clave, *[str(uid) for uid in usuario_ids])
            pipe.expire(clave, ttl_segundos)
            pipe.execute()

            logger.debug(
                f"Cache SET: {len(usuario_ids)} participantes para conv {conversacion_id}"
            )
            return True

        except Exception as e:
            logger.error(
                f"Error guardando participantes de conv {conversacion_id}: {e}"
            )
            return False

    def agregar_participante(
        self,
        conversacion_id: int,
        usuario_id: int
    ) -> bool:
        """
        Agrega un participante al set.
        """
        if not self._redis.disponible:
            return False

        try:
            clave = self._clave_participants(conversacion_id)

            if not self._redis.exists(clave):
                return False

            self._redis.sadd(clave, str(usuario_id))
            return True

        except Exception as e:
            logger.error(
                f"Error agregando participante {usuario_id} a conv {conversacion_id}: {e}"
            )
            return False

    def eliminar_participante(
        self,
        conversacion_id: int,
        usuario_id: int
    ) -> bool:
        """
        Elimina un participante del set.
        """
        if not self._redis.disponible:
            return False

        try:
            clave = self._clave_participants(conversacion_id)
            self._redis.srem(clave, str(usuario_id))
            return True

        except Exception as e:
            logger.error(
                f"Error eliminando participante {usuario_id} de conv {conversacion_id}: {e}"
            )
            return False

    def incrementar_no_leidos(
        self,
        conversacion_id: int,
        usuario_id: int
    ) -> int:
        """
        Incrementa contador de no leídos.
        Retorna nuevo valor.
        """
        if not self._redis.disponible:
            return 0

        try:
            clave = self._clave_unread(usuario_id, conversacion_id)
            nuevo_valor = self._redis.incr(clave)
            # TTL largo para contadores (1 día)
            self._redis.expire(clave, 86400)
            return nuevo_valor

        except Exception as e:
            logger.error(
                f"Error incrementando no leídos para user {usuario_id} conv {conversacion_id}: {e}"
            )
            return 0

    def resetear_no_leidos(
        self,
        conversacion_id: int,
        usuario_id: int
    ) -> bool:
        """
        Resetea contador de no leídos a 0.
        """
        if not self._redis.disponible:
            return False

        try:
            clave = self._clave_unread(usuario_id, conversacion_id)
            self._redis.delete(clave)
            return True

        except Exception as e:
            logger.error(
                f"Error reseteando no leídos para user {usuario_id} conv {conversacion_id}: {e}"
            )
            return False

    def obtener_no_leidos(
        self,
        usuario_id: int,
        conversacion_ids: Optional[List[int]] = None
    ) -> Dict[int, int]:
        """
        Obtiene contadores de no leídos por conversación.
        """
        if not self._redis.disponible:
            return {}

        try:
            resultado = {}

            if conversacion_ids:
                # Obtener para conversaciones específicas
                pipe = self._redis.pipeline()
                if not pipe:
                    return {}

                for conv_id in conversacion_ids:
                    clave = self._clave_unread(usuario_id, conv_id)
                    pipe.get(clave)

                valores = pipe.execute()

                for i, conv_id in enumerate(conversacion_ids):
                    valor = valores[i]
                    if valor:
                        try:
                            resultado[conv_id] = int(valor)
                        except ValueError:
                            resultado[conv_id] = 0
                    else:
                        resultado[conv_id] = 0

            else:
                # Obtener todas las conversaciones con no leídos
                patron = f"{self.PREFIJO_UNREAD}{usuario_id}:*"

                for clave in self._redis.scan_iter(patron):
                    # Extraer conversacion_id de la clave
                    partes = clave.split(":")
                    if len(partes) >= 4:
                        try:
                            conv_id = int(partes[3])
                            valor = self._redis.get(clave)
                            if valor:
                                resultado[conv_id] = int(valor)
                        except ValueError:
                            pass

            return resultado

        except Exception as e:
            logger.error(
                f"Error obteniendo no leídos para usuario {usuario_id}: {e}"
            )
            return {}

    def obtener_total_no_leidos(self, usuario_id: int) -> int:
        """
        Obtiene el total de mensajes no leídos del usuario.
        """
        no_leidos = self.obtener_no_leidos(usuario_id)
        return sum(no_leidos.values())

    def invalidar(self, conversacion_id: int) -> bool:
        """
        Invalida todo el cache de una conversación.
        """
        if not self._redis.disponible:
            return False

        try:
            claves = [
                self._clave_conv(conversacion_id),
                self._clave_participants(conversacion_id)
            ]
            self._redis.delete(*claves)

            logger.debug(f"Cache INVALIDATE: conversacion {conversacion_id}")
            return True

        except Exception as e:
            logger.error(
                f"Error invalidando cache de conv {conversacion_id}: {e}"
            )
            return False
