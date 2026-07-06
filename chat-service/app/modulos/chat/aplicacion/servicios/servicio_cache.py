# -*- coding: utf-8 -*-
"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                     SERVICIO DE CACHE - CHAT                                 ║
║                Facade para Operaciones de Cache Redis                        ║
╚══════════════════════════════════════════════════════════════════════════════╝

Proporciona una interfaz unificada para todas las operaciones de cache
del modulo de chat. Actua como Facade sobre los diferentes caches.

USO:
    from modulos.chat.aplicacion.servicios import ServicioCache

    cache = ServicioCache()

    # Presencia
    cache.marcar_online(usuario_id)
    cache.marcar_offline(usuario_id)

    # Mensajes
    cache.obtener_mensajes_cache(conversacion_id)
    cache.agregar_mensaje_cache(conversacion_id, mensaje)

    # Typing
    cache.establecer_escribiendo(conversacion_id, usuario_id)
    cache.obtener_escribiendo(conversacion_id)

Autor: Wilson Arguello
Correo: gestiontecnologia@maquita.com.ec
Fecha: 2026-01-02
"""

import logging
from typing import Optional, List, Dict, Any, Tuple
from datetime import datetime

from ...dominio.value_objects.tipos_chat import AccionUsuario
from ...infraestructura.cache import (
    ClienteRedis,
    obtener_cliente_redis,
    CacheMensajesRedis,
    CachePresenciaRedis,
    CacheIndicadorAccionRedis,
    CacheConversacionRedis,
    CacheSesionWebSocketRedis,
)

logger = logging.getLogger(__name__)


class ServicioCache:
    """
    Servicio unificado de cache para el modulo de chat.

    Beneficios:
    - Una sola interfaz para todos los caches
    - Manejo de errores centralizado
    - Facil de mockear en tests
    - Fallback silencioso si Redis no esta disponible
    """

    def __init__(self, cliente_redis: Optional[ClienteRedis] = None):
        """
        Inicializa el servicio de cache.

        Args:
            cliente_redis: Cliente Redis personalizado (opcional)
        """
        self._redis = cliente_redis or obtener_cliente_redis()

        # Inicializar caches especializados
        self._cache_mensajes = CacheMensajesRedis(self._redis)
        self._cache_presencia = CachePresenciaRedis(self._redis)
        self._cache_indicador = CacheIndicadorAccionRedis(self._redis)
        self._cache_conversacion = CacheConversacionRedis(self._redis)
        self._cache_sesion = CacheSesionWebSocketRedis(self._redis)

    @property
    def disponible(self) -> bool:
        """Indica si el cache esta disponible."""
        return self._redis.disponible

    # ═══════════════════════════════════════════════════════════════════════
    # PRESENCIA DE USUARIOS
    # ═══════════════════════════════════════════════════════════════════════

    def marcar_online(self, usuario_id: int) -> bool:
        """Marca un usuario como online."""
        return self._cache_presencia.establecer_online(usuario_id)

    def marcar_offline(self, usuario_id: int) -> bool:
        """Marca un usuario como offline."""
        return self._cache_presencia.establecer_offline(usuario_id)

    def esta_online(self, usuario_id: int) -> bool:
        """Verifica si un usuario esta online."""
        return self._cache_presencia.esta_online(usuario_id)

    def obtener_presencia(
        self,
        usuario_id: int
    ) -> Tuple[bool, Optional[datetime]]:
        """Obtiene estado de presencia y ultima vez visto."""
        return self._cache_presencia.obtener_estado(usuario_id)

    def obtener_presencia_multiple(
        self,
        usuario_ids: List[int]
    ) -> Dict[int, Tuple[bool, Optional[datetime]]]:
        """Obtiene presencia de multiples usuarios."""
        return self._cache_presencia.obtener_estados_multiple(usuario_ids)

    def refrescar_heartbeat(self, usuario_id: int) -> bool:
        """Refresca el heartbeat del usuario (mantiene online)."""
        return self._cache_presencia.refrescar_heartbeat(usuario_id)

    def obtener_usuarios_online(self) -> List[int]:
        """Obtiene lista de usuarios online."""
        return self._cache_presencia.obtener_usuarios_online()

    # ═══════════════════════════════════════════════════════════════════════
    # INDICADORES DE ACCION (TYPING)
    # ═══════════════════════════════════════════════════════════════════════

    def establecer_escribiendo(
        self,
        conversacion_id: int,
        usuario_id: int
    ) -> bool:
        """Indica que un usuario esta escribiendo."""
        return self._cache_indicador.establecer_accion(
            conversacion_id,
            usuario_id,
            AccionUsuario.ESCRIBIENDO
        )

    def establecer_grabando_audio(
        self,
        conversacion_id: int,
        usuario_id: int
    ) -> bool:
        """Indica que un usuario esta grabando audio."""
        return self._cache_indicador.establecer_accion(
            conversacion_id,
            usuario_id,
            AccionUsuario.GRABANDO_AUDIO
        )

    def limpiar_accion(
        self,
        conversacion_id: int,
        usuario_id: int
    ) -> bool:
        """Limpia la accion del usuario."""
        return self._cache_indicador.limpiar_accion(conversacion_id, usuario_id)

    def obtener_escribiendo(
        self,
        conversacion_id: int,
        excepto_usuario_id: Optional[int] = None
    ) -> List[Tuple[int, AccionUsuario]]:
        """Obtiene usuarios realizando acciones en una conversacion."""
        return self._cache_indicador.obtener_acciones(
            conversacion_id,
            excepto_usuario_id
        )

    def limpiar_acciones_usuario(self, usuario_id: int) -> int:
        """Limpia todas las acciones de un usuario (al desconectarse)."""
        return self._cache_indicador.limpiar_acciones_usuario(usuario_id)

    # ═══════════════════════════════════════════════════════════════════════
    # MENSAJES
    # ═══════════════════════════════════════════════════════════════════════

    def obtener_mensajes_cache(
        self,
        conversacion_id: int,
        limite: int = 50
    ) -> Optional[List[Dict[str, Any]]]:
        """Obtiene mensajes del cache (None si cache miss)."""
        return self._cache_mensajes.obtener_mensajes_recientes(
            conversacion_id,
            limite
        )

    def guardar_mensajes_cache(
        self,
        conversacion_id: int,
        mensajes: List[Dict[str, Any]]
    ) -> bool:
        """Guarda mensajes en cache."""
        return self._cache_mensajes.guardar_mensajes_recientes(
            conversacion_id,
            mensajes
        )

    def agregar_mensaje_cache(
        self,
        conversacion_id: int,
        mensaje: Dict[str, Any]
    ) -> bool:
        """Agrega un mensaje nuevo al cache."""
        return self._cache_mensajes.agregar_mensaje(conversacion_id, mensaje)

    def actualizar_mensaje_cache(
        self,
        conversacion_id: int,
        mensaje_id: int,
        datos: Dict[str, Any]
    ) -> bool:
        """Actualiza un mensaje en cache."""
        return self._cache_mensajes.actualizar_mensaje(
            conversacion_id,
            mensaje_id,
            datos
        )

    def eliminar_mensaje_cache(
        self,
        conversacion_id: int,
        mensaje_id: int
    ) -> bool:
        """Elimina un mensaje del cache."""
        return self._cache_mensajes.eliminar_mensaje(conversacion_id, mensaje_id)

    def invalidar_mensajes_cache(self, conversacion_id: int) -> bool:
        """Invalida el cache de mensajes de una conversacion."""
        return self._cache_mensajes.invalidar(conversacion_id)

    # ═══════════════════════════════════════════════════════════════════════
    # CONVERSACIONES
    # ═══════════════════════════════════════════════════════════════════════

    def obtener_conversacion_cache(
        self,
        conversacion_id: int
    ) -> Optional[Dict[str, Any]]:
        """Obtiene metadata de conversacion del cache."""
        return self._cache_conversacion.obtener_conversacion(conversacion_id)

    def guardar_conversacion_cache(
        self,
        conversacion_id: int,
        datos: Dict[str, Any]
    ) -> bool:
        """Guarda metadata de conversacion en cache."""
        return self._cache_conversacion.guardar_conversacion(
            conversacion_id,
            datos
        )

    def obtener_participantes_cache(
        self,
        conversacion_id: int
    ) -> Optional[List[int]]:
        """Obtiene IDs de participantes del cache."""
        return self._cache_conversacion.obtener_participantes(conversacion_id)

    def guardar_participantes_cache(
        self,
        conversacion_id: int,
        usuario_ids: List[int]
    ) -> bool:
        """Guarda participantes en cache."""
        return self._cache_conversacion.guardar_participantes(
            conversacion_id,
            usuario_ids
        )

    def incrementar_no_leidos(
        self,
        conversacion_id: int,
        usuario_id: int
    ) -> int:
        """Incrementa contador de no leidos."""
        return self._cache_conversacion.incrementar_no_leidos(
            conversacion_id,
            usuario_id
        )

    def resetear_no_leidos(
        self,
        conversacion_id: int,
        usuario_id: int
    ) -> bool:
        """Resetea contador de no leidos."""
        return self._cache_conversacion.resetear_no_leidos(
            conversacion_id,
            usuario_id
        )

    def obtener_no_leidos(
        self,
        usuario_id: int,
        conversacion_ids: Optional[List[int]] = None
    ) -> Dict[int, int]:
        """Obtiene contadores de no leidos."""
        return self._cache_conversacion.obtener_no_leidos(
            usuario_id,
            conversacion_ids
        )

    def obtener_total_no_leidos(self, usuario_id: int) -> int:
        """Obtiene total de mensajes no leidos."""
        return self._cache_conversacion.obtener_total_no_leidos(usuario_id)

    def invalidar_conversacion_cache(self, conversacion_id: int) -> bool:
        """Invalida todo el cache de una conversacion."""
        resultado_conv = self._cache_conversacion.invalidar(conversacion_id)
        resultado_msg = self._cache_mensajes.invalidar(conversacion_id)
        return resultado_conv and resultado_msg

    # ═══════════════════════════════════════════════════════════════════════
    # SESIONES WEBSOCKET
    # ═══════════════════════════════════════════════════════════════════════

    def registrar_conexion_ws(
        self,
        usuario_id: int,
        socket_id: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Registra una conexion WebSocket."""
        return self._cache_sesion.registrar_conexion(
            usuario_id,
            socket_id,
            metadata
        )

    def eliminar_conexion_ws(
        self,
        usuario_id: int,
        socket_id: str
    ) -> bool:
        """Elimina una conexion WebSocket."""
        return self._cache_sesion.eliminar_conexion(usuario_id, socket_id)

    def obtener_sockets_usuario(self, usuario_id: int) -> List[str]:
        """Obtiene todos los sockets de un usuario."""
        return self._cache_sesion.obtener_sockets_usuario(usuario_id)

    def obtener_sockets_usuarios(
        self,
        usuario_ids: List[int]
    ) -> Dict[int, List[str]]:
        """Obtiene sockets de multiples usuarios (para broadcast)."""
        return self._cache_sesion.obtener_sockets_usuarios(usuario_ids)

    def usuario_conectado(self, usuario_id: int) -> bool:
        """Verifica si un usuario tiene conexion activa."""
        return self._cache_sesion.usuario_tiene_conexion(usuario_id)

    def contar_conexiones_totales(self) -> int:
        """Cuenta total de conexiones WebSocket."""
        return self._cache_sesion.contar_conexiones()

    def limpiar_sesiones_usuario(self, usuario_id: int) -> int:
        """Limpia todas las sesiones de un usuario."""
        return self._cache_sesion.limpiar_sesiones_usuario(usuario_id)

    # ═══════════════════════════════════════════════════════════════════════
    # OPERACIONES COMPUESTAS
    # ═══════════════════════════════════════════════════════════════════════

    def al_conectar_usuario(
        self,
        usuario_id: int,
        socket_id: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Operaciones al conectar un usuario.
        - Registra conexion WebSocket
        - Marca online
        """
        resultado_ws = self.registrar_conexion_ws(usuario_id, socket_id, metadata)
        resultado_presencia = self.marcar_online(usuario_id)

        logger.info(f"Usuario {usuario_id} conectado (socket: {socket_id})")
        return resultado_ws and resultado_presencia

    def al_desconectar_usuario(
        self,
        usuario_id: int,
        socket_id: str
    ) -> bool:
        """
        Operaciones al desconectar un usuario.
        - Elimina conexion WebSocket
        - Si no tiene mas conexiones, marca offline
        - Limpia indicadores de accion
        """
        # Eliminar conexion
        self.eliminar_conexion_ws(usuario_id, socket_id)

        # Verificar si tiene mas conexiones
        if not self.usuario_conectado(usuario_id):
            self.marcar_offline(usuario_id)
            self.limpiar_acciones_usuario(usuario_id)
            logger.info(f"Usuario {usuario_id} desconectado completamente")
        else:
            logger.debug(
                f"Usuario {usuario_id} cerro socket {socket_id} "
                f"pero tiene otras conexiones activas"
            )

        return True

    def al_enviar_mensaje(
        self,
        conversacion_id: int,
        mensaje: Dict[str, Any],
        remitente_id: int,
        participantes_ids: List[int]
    ) -> None:
        """
        Operaciones al enviar un mensaje.
        - Agrega mensaje al cache
        - Incrementa no leidos para otros participantes
        - Limpia indicador de escribiendo
        """
        # Agregar al cache
        self.agregar_mensaje_cache(conversacion_id, mensaje)

        # Incrementar no leidos para otros
        for uid in participantes_ids:
            if uid != remitente_id:
                self.incrementar_no_leidos(conversacion_id, uid)

        # Limpiar indicador de escribiendo
        self.limpiar_accion(conversacion_id, remitente_id)

    def al_leer_mensajes(
        self,
        conversacion_id: int,
        usuario_id: int
    ) -> None:
        """
        Operaciones al marcar mensajes como leidos.
        - Resetea contador de no leidos
        """
        self.resetear_no_leidos(conversacion_id, usuario_id)

    # ═══════════════════════════════════════════════════════════════════════
    # ESTADISTICAS
    # ═══════════════════════════════════════════════════════════════════════

    def obtener_estadisticas(self) -> Dict[str, Any]:
        """Obtiene estadisticas generales del cache."""
        if not self.disponible:
            return {"disponible": False}

        return {
            "disponible": True,
            "usuarios_online": len(self.obtener_usuarios_online()),
            "conexiones_ws": self.contar_conexiones_totales(),
            "mensajes": self._cache_mensajes.obtener_estadisticas(),
            "sesiones": self._cache_sesion.obtener_estadisticas(),
        }
