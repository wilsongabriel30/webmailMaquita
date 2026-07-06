# -*- coding: utf-8 -*-
"""
Cache de Sesiones WebSocket - Implementación Redis

Mapea usuarios a conexiones WebSocket para broadcasts eficientes.
Soporta múltiples conexiones por usuario (tabs, dispositivos).
Latencia objetivo: < 1ms

Autor: Wilson Arguello
Correo: gestiontecnologia@maquita.com.ec
Fecha: 2026-01-02
"""

import json
import logging
from typing import Optional, List, Dict, Any

from ...dominio.repositorios.repositorio_cache import CacheSesionWebSocket
from .cliente_redis import ClienteRedis, obtener_cliente_redis

logger = logging.getLogger(__name__)


class CacheSesionWebSocketRedis(CacheSesionWebSocket):
    """
    Implementación Redis de cache de sesiones WebSocket.

    Estructura de claves:
    - chat:ws:user:{usuario_id}         -> Set de socket_ids
    - chat:ws:socket:{socket_id}        -> Hash con metadata (usuario_id, dispositivo, etc)
    - chat:ws:total_connections         -> Contador global
    """

    PREFIJO_USER = "chat:ws:user:"
    PREFIJO_SOCKET = "chat:ws:socket:"
    CLAVE_TOTAL = "chat:ws:total_connections"
    TTL_SESION = 3600  # 1 hora

    def __init__(self, cliente: Optional[ClienteRedis] = None):
        """
        Inicializa el cache de sesiones.

        Args:
            cliente: Cliente Redis (usa singleton si no se proporciona)
        """
        self._redis = cliente or obtener_cliente_redis()

    def _clave_user(self, usuario_id: int) -> str:
        return f"{self.PREFIJO_USER}{usuario_id}"

    def _clave_socket(self, socket_id: str) -> str:
        return f"{self.PREFIJO_SOCKET}{socket_id}"

    def registrar_conexion(
        self,
        usuario_id: int,
        socket_id: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Registra una conexión WebSocket.
        """
        if not self._redis.disponible:
            return False

        try:
            clave_user = self._clave_user(usuario_id)
            clave_socket = self._clave_socket(socket_id)

            pipe = self._redis.pipeline()
            if not pipe:
                return False

            # Agregar socket al set del usuario
            pipe.sadd(clave_user, socket_id)
            pipe.expire(clave_user, self.TTL_SESION)

            # Guardar metadata del socket
            socket_data = {
                "usuario_id": str(usuario_id),
                "socket_id": socket_id,
                **(metadata or {})
            }
            for k, v in socket_data.items():
                if v is not None:
                    pipe.hset(clave_socket, k, str(v) if not isinstance(v, str) else v)
            pipe.expire(clave_socket, self.TTL_SESION)

            # Incrementar contador global
            pipe.incr(self.CLAVE_TOTAL)

            pipe.execute()

            logger.info(
                f"WebSocket registrado: usuario {usuario_id}, socket {socket_id}"
            )
            return True

        except Exception as e:
            logger.error(
                f"Error registrando conexión {socket_id} para usuario {usuario_id}: {e}"
            )
            return False

    def eliminar_conexion(
        self,
        usuario_id: int,
        socket_id: str
    ) -> bool:
        """
        Elimina una conexión WebSocket.
        """
        if not self._redis.disponible:
            return False

        try:
            clave_user = self._clave_user(usuario_id)
            clave_socket = self._clave_socket(socket_id)

            pipe = self._redis.pipeline()
            if not pipe:
                return False

            # Remover socket del set del usuario
            pipe.srem(clave_user, socket_id)

            # Eliminar metadata del socket
            pipe.delete(clave_socket)

            # Decrementar contador global
            pipe.decr(self.CLAVE_TOTAL)

            pipe.execute()

            logger.info(
                f"WebSocket eliminado: usuario {usuario_id}, socket {socket_id}"
            )
            return True

        except Exception as e:
            logger.error(
                f"Error eliminando conexión {socket_id} para usuario {usuario_id}: {e}"
            )
            return False

    def obtener_sockets_usuario(
        self,
        usuario_id: int
    ) -> List[str]:
        """
        Obtiene todos los socket_ids de un usuario.
        """
        if not self._redis.disponible:
            return []

        try:
            clave = self._clave_user(usuario_id)
            miembros = self._redis.smembers(clave)
            return list(miembros)

        except Exception as e:
            logger.error(
                f"Error obteniendo sockets de usuario {usuario_id}: {e}"
            )
            return []

    def obtener_sockets_usuarios(
        self,
        usuario_ids: List[int]
    ) -> Dict[int, List[str]]:
        """
        Obtiene sockets de múltiples usuarios (para broadcast).
        """
        if not self._redis.disponible or not usuario_ids:
            return {}

        try:
            resultado = {}
            pipe = self._redis.pipeline()
            if not pipe:
                return {}

            # Obtener sets de todos los usuarios
            for uid in usuario_ids:
                clave = self._clave_user(uid)
                pipe.smembers(clave)

            respuestas = pipe.execute()

            for i, uid in enumerate(usuario_ids):
                if respuestas[i]:
                    resultado[uid] = list(respuestas[i])
                else:
                    resultado[uid] = []

            return resultado

        except Exception as e:
            logger.error(f"Error obteniendo sockets múltiples: {e}")
            return {}

    def obtener_metadata_socket(self, socket_id: str) -> Optional[Dict[str, Any]]:
        """
        Obtiene metadata de un socket.
        """
        if not self._redis.disponible:
            return None

        try:
            clave = self._clave_socket(socket_id)
            datos = self._redis.hgetall(clave)
            return datos if datos else None

        except Exception as e:
            logger.error(f"Error obteniendo metadata de socket {socket_id}: {e}")
            return None

    def usuario_tiene_conexion(self, usuario_id: int) -> bool:
        """
        Verifica si el usuario tiene al menos una conexión activa.
        """
        if not self._redis.disponible:
            return False

        try:
            clave = self._clave_user(usuario_id)
            return self._redis.scard(clave) > 0

        except Exception as e:
            logger.error(
                f"Error verificando conexión de usuario {usuario_id}: {e}"
            )
            return False

    def contar_conexiones(self) -> int:
        """
        Cuenta total de conexiones activas.
        """
        if not self._redis.disponible:
            return 0

        try:
            valor = self._redis.get(self.CLAVE_TOTAL)
            return int(valor) if valor else 0

        except Exception as e:
            logger.error(f"Error contando conexiones: {e}")
            return 0

    def contar_conexiones_usuario(self, usuario_id: int) -> int:
        """
        Cuenta conexiones de un usuario específico.
        """
        if not self._redis.disponible:
            return 0

        try:
            clave = self._clave_user(usuario_id)
            return self._redis.scard(clave)

        except Exception as e:
            logger.error(
                f"Error contando conexiones de usuario {usuario_id}: {e}"
            )
            return 0

    def refrescar_sesion(
        self,
        usuario_id: int,
        socket_id: str
    ) -> bool:
        """
        Refresca el TTL de una sesión.
        """
        if not self._redis.disponible:
            return False

        try:
            clave_user = self._clave_user(usuario_id)
            clave_socket = self._clave_socket(socket_id)

            pipe = self._redis.pipeline()
            if not pipe:
                return False

            pipe.expire(clave_user, self.TTL_SESION)
            pipe.expire(clave_socket, self.TTL_SESION)
            pipe.execute()

            return True

        except Exception as e:
            logger.error(
                f"Error refrescando sesión {socket_id} de usuario {usuario_id}: {e}"
            )
            return False

    def limpiar_sesiones_usuario(self, usuario_id: int) -> int:
        """
        Elimina todas las sesiones de un usuario.
        Útil para logout forzado.
        """
        if not self._redis.disponible:
            return 0

        try:
            clave_user = self._clave_user(usuario_id)

            # Obtener todos los sockets
            sockets = self._redis.smembers(clave_user)
            if not sockets:
                return 0

            pipe = self._redis.pipeline()
            if not pipe:
                return 0

            # Eliminar metadata de cada socket
            for socket_id in sockets:
                pipe.delete(self._clave_socket(socket_id))
                pipe.decr(self.CLAVE_TOTAL)

            # Eliminar set del usuario
            pipe.delete(clave_user)

            pipe.execute()

            logger.info(
                f"Limpiadas {len(sockets)} sesiones del usuario {usuario_id}"
            )
            return len(sockets)

        except Exception as e:
            logger.error(
                f"Error limpiando sesiones de usuario {usuario_id}: {e}"
            )
            return 0

    def obtener_todos_usuarios_conectados(self) -> List[int]:
        """
        Obtiene lista de todos los usuarios con conexiones activas.
        """
        if not self._redis.disponible:
            return []

        try:
            patron = f"{self.PREFIJO_USER}*"
            usuarios = []

            for clave in self._redis.scan_iter(patron):
                # Extraer usuario_id de la clave
                partes = clave.split(":")
                if len(partes) >= 4:
                    try:
                        uid = int(partes[3])
                        usuarios.append(uid)
                    except ValueError:
                        pass

            return usuarios

        except Exception as e:
            logger.error(f"Error obteniendo usuarios conectados: {e}")
            return []

    def obtener_estadisticas(self) -> Dict[str, Any]:
        """
        Obtiene estadísticas de conexiones.
        """
        if not self._redis.disponible:
            return {"disponible": False}

        try:
            usuarios_conectados = self.obtener_todos_usuarios_conectados()
            total_conexiones = self.contar_conexiones()

            return {
                "disponible": True,
                "usuarios_unicos": len(usuarios_conectados),
                "conexiones_totales": total_conexiones,
                "promedio_conexiones_por_usuario": (
                    total_conexiones / len(usuarios_conectados)
                    if usuarios_conectados else 0
                )
            }

        except Exception as e:
            logger.error(f"Error obteniendo estadísticas: {e}")
            return {"disponible": True, "error": str(e)}
