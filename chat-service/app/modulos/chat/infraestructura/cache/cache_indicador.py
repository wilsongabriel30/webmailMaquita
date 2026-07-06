# -*- coding: utf-8 -*-
"""
Cache de Indicadores de Acción - Implementación Redis

Maneja indicadores como "escribiendo...", "grabando audio...", etc.
Auto-expira para limpiar indicadores huérfanos.
Latencia objetivo: < 1ms

Autor: Wilson Arguello
Correo: gestiontecnologia@maquita.com.ec
Fecha: 2026-01-02
"""

import logging
from typing import Optional, List, Tuple

from ...dominio.repositorios.repositorio_cache import CacheIndicadorAccion
from ...dominio.value_objects.tipos_chat import AccionUsuario
from .cliente_redis import ClienteRedis, obtener_cliente_redis

logger = logging.getLogger(__name__)


class CacheIndicadorAccionRedis(CacheIndicadorAccion):
    """
    Implementación Redis de cache de indicadores de acción.

    Estructura de claves:
    - chat:typing:{conversacion_id}:{usuario_id} -> accion con TTL
    """

    PREFIJO = "chat:typing:"
    TTL_DEFECTO = 10  # 10 segundos

    def __init__(self, cliente: Optional[ClienteRedis] = None):
        """
        Inicializa el cache de indicadores.

        Args:
            cliente: Cliente Redis (usa singleton si no se proporciona)
        """
        self._redis = cliente or obtener_cliente_redis()

    def _clave(self, conversacion_id: int, usuario_id: int) -> str:
        return f"{self.PREFIJO}{conversacion_id}:{usuario_id}"

    def _patron_conversacion(self, conversacion_id: int) -> str:
        return f"{self.PREFIJO}{conversacion_id}:*"

    def establecer_accion(
        self,
        conversacion_id: int,
        usuario_id: int,
        accion: AccionUsuario,
        ttl_segundos: int = TTL_DEFECTO
    ) -> bool:
        """
        Establece que un usuario está realizando una acción.
        La acción expira automáticamente (TTL).
        """
        if not self._redis.disponible:
            return False

        try:
            clave = self._clave(conversacion_id, usuario_id)
            return self._redis.set(clave, accion.value, ttl_segundos)
        except Exception as e:
            logger.error(
                f"Error estableciendo acción para {usuario_id} "
                f"en conv {conversacion_id}: {e}"
            )
            return False

    def limpiar_accion(
        self,
        conversacion_id: int,
        usuario_id: int
    ) -> bool:
        """
        Limpia la acción del usuario (dejó de escribir).
        """
        if not self._redis.disponible:
            return False

        try:
            clave = self._clave(conversacion_id, usuario_id)
            self._redis.delete(clave)
            return True
        except Exception as e:
            logger.error(
                f"Error limpiando acción para {usuario_id} "
                f"en conv {conversacion_id}: {e}"
            )
            return False

    def obtener_acciones(
        self,
        conversacion_id: int,
        excepto_usuario_id: Optional[int] = None
    ) -> List[Tuple[int, AccionUsuario]]:
        """
        Obtiene usuarios realizando acciones en una conversación.
        Retorna: [(usuario_id, accion), ...]
        """
        if not self._redis.disponible:
            return []

        try:
            resultado = []
            patron = self._patron_conversacion(conversacion_id)

            # Usar scan para encontrar claves (más eficiente que keys)
            for clave in self._redis.scan_iter(patron):
                # Extraer usuario_id de la clave
                # Formato: chat:typing:{conv_id}:{user_id}
                partes = clave.split(":")
                if len(partes) >= 4:
                    try:
                        uid = int(partes[3])

                        # Filtrar usuario actual
                        if excepto_usuario_id and uid == excepto_usuario_id:
                            continue

                        # Obtener acción
                        accion_str = self._redis.get(clave)
                        if accion_str:
                            try:
                                accion = AccionUsuario(accion_str)
                                resultado.append((uid, accion))
                            except ValueError:
                                # Acción desconocida, ignorar
                                pass

                    except ValueError:
                        # usuario_id no es número, ignorar
                        pass

            return resultado

        except Exception as e:
            logger.error(
                f"Error obteniendo acciones en conv {conversacion_id}: {e}"
            )
            return []

    def limpiar_todas_acciones(self, conversacion_id: int) -> int:
        """
        Limpia todas las acciones de una conversación.
        Útil cuando se cierra una conversación.
        """
        if not self._redis.disponible:
            return 0

        try:
            patron = self._patron_conversacion(conversacion_id)
            eliminados = 0

            for clave in self._redis.scan_iter(patron):
                self._redis.delete(clave)
                eliminados += 1

            return eliminados

        except Exception as e:
            logger.error(
                f"Error limpiando acciones en conv {conversacion_id}: {e}"
            )
            return 0

    def limpiar_acciones_usuario(self, usuario_id: int) -> int:
        """
        Limpia todas las acciones de un usuario en todas las conversaciones.
        Útil cuando un usuario se desconecta.
        """
        if not self._redis.disponible:
            return 0

        try:
            patron = f"{self.PREFIJO}*:{usuario_id}"
            eliminados = 0

            for clave in self._redis.scan_iter(patron):
                self._redis.delete(clave)
                eliminados += 1

            return eliminados

        except Exception as e:
            logger.error(
                f"Error limpiando acciones del usuario {usuario_id}: {e}"
            )
            return 0
