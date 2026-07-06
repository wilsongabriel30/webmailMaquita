# -*- coding: utf-8 -*-
"""
Cache de Presencia - Implementación Redis

Maneja el estado online/offline de usuarios en tiempo real.
Latencia objetivo: < 1ms

Autor: Wilson Arguello
Correo: gestiontecnologia@maquita.com.ec
Fecha: 2026-01-02
"""

import logging
from typing import Optional, List, Dict, Tuple
from datetime import datetime

from ...dominio.repositorios.repositorio_cache import CachePresencia
from .cliente_redis import ClienteRedis, obtener_cliente_redis

logger = logging.getLogger(__name__)


class CachePresenciaRedis(CachePresencia):
    """
    Implementación Redis de cache de presencia.

    Estructura de claves:
    - chat:presence:{usuario_id}     -> "online" con TTL
    - chat:last_seen:{usuario_id}    -> timestamp ISO
    - chat:online_users              -> SET de usuario_ids online
    """

    PREFIJO_PRESENCIA = "chat:presence:"
    PREFIJO_LAST_SEEN = "chat:last_seen:"
    SET_USUARIOS_ONLINE = "chat:online_users"
    TTL_DEFECTO = 300  # 5 minutos

    def __init__(self, cliente: Optional[ClienteRedis] = None):
        """
        Inicializa el cache de presencia.

        Args:
            cliente: Cliente Redis (usa singleton si no se proporciona)
        """
        self._redis = cliente or obtener_cliente_redis()

    def _clave_presencia(self, usuario_id: int) -> str:
        return f"{self.PREFIJO_PRESENCIA}{usuario_id}"

    def _clave_last_seen(self, usuario_id: int) -> str:
        return f"{self.PREFIJO_LAST_SEEN}{usuario_id}"

    def establecer_online(
        self,
        usuario_id: int,
        ttl_segundos: int = TTL_DEFECTO
    ) -> bool:
        """
        Marca usuario como online con TTL (heartbeat refresh).
        """
        if not self._redis.disponible:
            return False

        try:
            pipe = self._redis.pipeline()
            if pipe:
                # Marcar online con TTL
                pipe.setex(
                    self._clave_presencia(usuario_id),
                    ttl_segundos,
                    "online"
                )
                # Agregar al set de usuarios online
                pipe.sadd(self.SET_USUARIOS_ONLINE, str(usuario_id))
                pipe.execute()
                return True
            return False
        except Exception as e:
            logger.error(f"Error estableciendo online para {usuario_id}: {e}")
            return False

    def establecer_offline(self, usuario_id: int) -> bool:
        """
        Marca usuario como offline y guarda ultima_vez_visto.
        """
        if not self._redis.disponible:
            return False

        try:
            ahora = datetime.now().isoformat()
            pipe = self._redis.pipeline()
            if pipe:
                # Eliminar clave de presencia
                pipe.delete(self._clave_presencia(usuario_id))
                # Guardar última vez visto
                pipe.set(self._clave_last_seen(usuario_id), ahora)
                # Remover del set de usuarios online
                pipe.srem(self.SET_USUARIOS_ONLINE, str(usuario_id))
                pipe.execute()
                return True
            return False
        except Exception as e:
            logger.error(f"Error estableciendo offline para {usuario_id}: {e}")
            return False

    def esta_online(self, usuario_id: int) -> bool:
        """
        Verifica si un usuario está online.
        """
        if not self._redis.disponible:
            return False

        return self._redis.exists(self._clave_presencia(usuario_id))

    def obtener_estado(
        self,
        usuario_id: int
    ) -> Tuple[bool, Optional[datetime]]:
        """
        Obtiene estado completo: (esta_online, ultima_vez_visto).
        """
        if not self._redis.disponible:
            return (False, None)

        try:
            online = self._redis.exists(self._clave_presencia(usuario_id))

            if online:
                return (True, None)

            # Obtener última vez visto
            last_seen_str = self._redis.get(self._clave_last_seen(usuario_id))
            if last_seen_str:
                try:
                    last_seen = datetime.fromisoformat(last_seen_str)
                    return (False, last_seen)
                except ValueError:
                    pass

            return (False, None)

        except Exception as e:
            logger.error(f"Error obteniendo estado de {usuario_id}: {e}")
            return (False, None)

    def obtener_estados_multiple(
        self,
        usuario_ids: List[int]
    ) -> Dict[int, Tuple[bool, Optional[datetime]]]:
        """
        Obtiene estado de múltiples usuarios en una sola llamada.
        Optimizado para listas de participantes.
        """
        if not self._redis.disponible or not usuario_ids:
            return {}

        resultado = {}

        try:
            pipe = self._redis.pipeline()
            if not pipe:
                return {}

            # Verificar presencia de todos
            for uid in usuario_ids:
                pipe.exists(self._clave_presencia(uid))
                pipe.get(self._clave_last_seen(uid))

            respuestas = pipe.execute()

            # Procesar respuestas (2 por usuario: exists, last_seen)
            for i, uid in enumerate(usuario_ids):
                idx = i * 2
                online = bool(respuestas[idx])
                last_seen_str = respuestas[idx + 1]

                last_seen = None
                if not online and last_seen_str:
                    try:
                        last_seen = datetime.fromisoformat(last_seen_str)
                    except ValueError:
                        pass

                resultado[uid] = (online, last_seen)

            return resultado

        except Exception as e:
            logger.error(f"Error obteniendo estados múltiples: {e}")
            return {}

    def refrescar_heartbeat(self, usuario_id: int) -> bool:
        """
        Refresca el TTL del usuario (mantiene online).
        Llamar cada 60 segundos desde el cliente.
        """
        if not self._redis.disponible:
            return False

        return self._redis.expire(
            self._clave_presencia(usuario_id),
            self.TTL_DEFECTO
        )

    def obtener_usuarios_online(self) -> List[int]:
        """
        Obtiene lista de todos los usuarios online.
        """
        if not self._redis.disponible:
            return []

        try:
            miembros = self._redis.smembers(self.SET_USUARIOS_ONLINE)
            return [int(m) for m in miembros if m.isdigit()]
        except Exception as e:
            logger.error(f"Error obteniendo usuarios online: {e}")
            return []

    def limpiar_usuarios_expirados(self) -> int:
        """
        Limpia usuarios del set que ya no tienen clave de presencia.
        Ejecutar periódicamente (cada minuto).
        """
        if not self._redis.disponible:
            return 0

        try:
            usuarios_online = self._redis.smembers(self.SET_USUARIOS_ONLINE)
            eliminados = 0

            for uid_str in usuarios_online:
                if not uid_str.isdigit():
                    continue
                uid = int(uid_str)
                if not self._redis.exists(self._clave_presencia(uid)):
                    self._redis.srem(self.SET_USUARIOS_ONLINE, uid_str)
                    eliminados += 1

            if eliminados > 0:
                logger.info(f"Limpiados {eliminados} usuarios expirados del set online")

            return eliminados

        except Exception as e:
            logger.error(f"Error limpiando usuarios expirados: {e}")
            return 0
