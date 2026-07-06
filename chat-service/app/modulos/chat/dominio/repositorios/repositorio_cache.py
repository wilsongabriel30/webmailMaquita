# -*- coding: utf-8 -*-
"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                    INTERFACES DE CACHE - DOMINIO                             ║
║              Puertos para Cache en Memoria (Redis, Memcached)                ║
╚══════════════════════════════════════════════════════════════════════════════╝

██████████████████████████████████████████████████████████████████████████████
██  REGLAS PARA ESTAS INTERFACES                                             ██
██████████████████████████████████████████████████████████████████████████████

1. Son INTERFACES (ABC), no implementaciones
2. Las implementaciones van en infraestructura/cache/
3. NO dependen de Redis, Memcached, ni ninguna tecnologia especifica
4. Definen QUE se necesita cachear, no COMO

IMPLEMENTACIONES ESPERADAS:
- CacheMensajesRedis      -> infraestructura/cache/cache_mensajes.py
- CachePresenciaRedis     -> infraestructura/cache/cache_presencia.py
- CacheConversacionRedis  -> infraestructura/cache/cache_conversacion.py

Autor: Wilson Arguello
Correo: gestiontecnologia@maquita.com.ec
Fecha: 2026-01-02
"""

from abc import ABC, abstractmethod
from typing import Optional, List, Dict, Any, Tuple
from datetime import datetime

from ..entidades.conversacion import Conversacion, Participante
from ..entidades.mensaje import Mensaje
from ..value_objects.tipos_chat import AccionUsuario


class CacheMensajes(ABC):
    """
    Interface para cache de mensajes recientes.

    Proposito:
    - Acceso ultra-rapido a mensajes recientes (< 5ms)
    - Evitar consultas a PostgreSQL para mensajes frecuentes
    - TTL sugerido: 1 hora para mensajes recientes
    """

    @abstractmethod
    def obtener_mensajes_recientes(
        self,
        conversacion_id: int,
        limite: int = 50
    ) -> Optional[List[Dict[str, Any]]]:
        """
        Obtiene mensajes recientes del cache.
        Retorna None si no hay cache (cache miss).
        """
        pass

    @abstractmethod
    def guardar_mensajes_recientes(
        self,
        conversacion_id: int,
        mensajes: List[Dict[str, Any]],
        ttl_segundos: int = 3600
    ) -> bool:
        """
        Guarda mensajes en cache.
        """
        pass

    @abstractmethod
    def agregar_mensaje(
        self,
        conversacion_id: int,
        mensaje: Dict[str, Any]
    ) -> bool:
        """
        Agrega un mensaje nuevo al cache existente (push al inicio).
        """
        pass

    @abstractmethod
    def actualizar_mensaje(
        self,
        conversacion_id: int,
        mensaje_id: int,
        datos: Dict[str, Any]
    ) -> bool:
        """
        Actualiza un mensaje en cache (edicion).
        """
        pass

    @abstractmethod
    def eliminar_mensaje(
        self,
        conversacion_id: int,
        mensaje_id: int
    ) -> bool:
        """
        Elimina un mensaje del cache.
        """
        pass

    @abstractmethod
    def invalidar(self, conversacion_id: int) -> bool:
        """
        Invalida todo el cache de una conversacion.
        """
        pass


class CachePresencia(ABC):
    """
    Interface para cache de presencia de usuarios.

    Proposito:
    - Estado online/offline en tiempo real (< 1ms)
    - Ultima vez visto
    - Heartbeat para detectar desconexiones
    - TTL sugerido: 5 minutos (con refresh automatico)
    """

    @abstractmethod
    def establecer_online(
        self,
        usuario_id: int,
        ttl_segundos: int = 300
    ) -> bool:
        """
        Marca usuario como online con TTL (heartbeat refresh).
        """
        pass

    @abstractmethod
    def establecer_offline(self, usuario_id: int) -> bool:
        """
        Marca usuario como offline y guarda ultima_vez_visto.
        """
        pass

    @abstractmethod
    def esta_online(self, usuario_id: int) -> bool:
        """
        Verifica si un usuario esta online.
        """
        pass

    @abstractmethod
    def obtener_estado(
        self,
        usuario_id: int
    ) -> Tuple[bool, Optional[datetime]]:
        """
        Obtiene estado completo: (esta_online, ultima_vez_visto).
        """
        pass

    @abstractmethod
    def obtener_estados_multiple(
        self,
        usuario_ids: List[int]
    ) -> Dict[int, Tuple[bool, Optional[datetime]]]:
        """
        Obtiene estado de multiples usuarios en una sola llamada.
        Optimizado para listas de participantes.
        """
        pass

    @abstractmethod
    def refrescar_heartbeat(self, usuario_id: int) -> bool:
        """
        Refresca el TTL del usuario (mantiene online).
        Llamar cada 60 segundos desde el cliente.
        """
        pass

    @abstractmethod
    def obtener_usuarios_online(self) -> List[int]:
        """
        Obtiene lista de todos los usuarios online.
        """
        pass


class CacheIndicadorAccion(ABC):
    """
    Interface para cache de indicadores de accion (typing, recording).

    Proposito:
    - "Escribiendo..." en tiempo real (< 1ms)
    - Auto-expira para limpiar indicadores huerfanos
    - TTL sugerido: 10 segundos (auto-limpieza)
    """

    @abstractmethod
    def establecer_accion(
        self,
        conversacion_id: int,
        usuario_id: int,
        accion: AccionUsuario,
        ttl_segundos: int = 10
    ) -> bool:
        """
        Establece que un usuario esta realizando una accion.
        La accion expira automaticamente (TTL).
        """
        pass

    @abstractmethod
    def limpiar_accion(
        self,
        conversacion_id: int,
        usuario_id: int
    ) -> bool:
        """
        Limpia la accion del usuario (dejo de escribir).
        """
        pass

    @abstractmethod
    def obtener_acciones(
        self,
        conversacion_id: int,
        excepto_usuario_id: Optional[int] = None
    ) -> List[Tuple[int, AccionUsuario]]:
        """
        Obtiene usuarios realizando acciones en una conversacion.
        Retorna: [(usuario_id, accion), ...]
        """
        pass


class CacheConversacion(ABC):
    """
    Interface para cache de conversaciones activas.

    Proposito:
    - Metadata de conversaciones frecuentes
    - Lista de participantes sin query a BD
    - Contadores de mensajes no leidos
    - TTL sugerido: 30 minutos
    """

    @abstractmethod
    def obtener_conversacion(
        self,
        conversacion_id: int
    ) -> Optional[Dict[str, Any]]:
        """
        Obtiene metadata de conversacion del cache.
        """
        pass

    @abstractmethod
    def guardar_conversacion(
        self,
        conversacion_id: int,
        datos: Dict[str, Any],
        ttl_segundos: int = 1800
    ) -> bool:
        """
        Guarda metadata de conversacion.
        """
        pass

    @abstractmethod
    def obtener_participantes(
        self,
        conversacion_id: int
    ) -> Optional[List[int]]:
        """
        Obtiene IDs de participantes activos (para broadcast).
        """
        pass

    @abstractmethod
    def guardar_participantes(
        self,
        conversacion_id: int,
        usuario_ids: List[int],
        ttl_segundos: int = 1800
    ) -> bool:
        """
        Guarda lista de participantes.
        """
        pass

    @abstractmethod
    def incrementar_no_leidos(
        self,
        conversacion_id: int,
        usuario_id: int
    ) -> int:
        """
        Incrementa contador de no leidos.
        Retorna nuevo valor.
        """
        pass

    @abstractmethod
    def resetear_no_leidos(
        self,
        conversacion_id: int,
        usuario_id: int
    ) -> bool:
        """
        Resetea contador de no leidos a 0.
        """
        pass

    @abstractmethod
    def obtener_no_leidos(
        self,
        usuario_id: int,
        conversacion_ids: Optional[List[int]] = None
    ) -> Dict[int, int]:
        """
        Obtiene contadores de no leidos por conversacion.
        """
        pass

    @abstractmethod
    def invalidar(self, conversacion_id: int) -> bool:
        """
        Invalida todo el cache de una conversacion.
        """
        pass


class CacheSesionWebSocket(ABC):
    """
    Interface para cache de sesiones WebSocket.

    Proposito:
    - Mapear usuario_id <-> socket_id para broadcasts
    - Soportar multiples conexiones por usuario (tabs, dispositivos)
    - TTL sugerido: igual a timeout de sesion
    """

    @abstractmethod
    def registrar_conexion(
        self,
        usuario_id: int,
        socket_id: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Registra una conexion WebSocket.
        """
        pass

    @abstractmethod
    def eliminar_conexion(
        self,
        usuario_id: int,
        socket_id: str
    ) -> bool:
        """
        Elimina una conexion WebSocket.
        """
        pass

    @abstractmethod
    def obtener_sockets_usuario(
        self,
        usuario_id: int
    ) -> List[str]:
        """
        Obtiene todos los socket_ids de un usuario.
        """
        pass

    @abstractmethod
    def obtener_sockets_usuarios(
        self,
        usuario_ids: List[int]
    ) -> Dict[int, List[str]]:
        """
        Obtiene sockets de multiples usuarios (para broadcast).
        """
        pass

    @abstractmethod
    def usuario_tiene_conexion(self, usuario_id: int) -> bool:
        """
        Verifica si el usuario tiene al menos una conexion activa.
        """
        pass

    @abstractmethod
    def contar_conexiones(self) -> int:
        """
        Cuenta total de conexiones activas.
        """
        pass
