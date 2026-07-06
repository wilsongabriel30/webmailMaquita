# -*- coding: utf-8 -*-
"""
Interfaces de Repositorio: Chat Institucional

Define los puertos (interfaces) para persistencia del chat.
Las implementaciones concretas estan en infraestructura/persistencia/.

CAPA: modulos/chat/dominio/repositorios
ARQUITECTURA: Hexagonal - 100%

Autor: Wilson Arguello
Correo: gestiontecnologia@maquita.com.ec
Fecha: 2026-01-02
Migrado: 2026-01-05
"""

from abc import ABC, abstractmethod
from typing import Optional, List, Tuple
from datetime import datetime

from modulos.chat.dominio.entidades.conversacion import Conversacion, Participante
from modulos.chat.dominio.entidades.mensaje import Mensaje, ArchivoMensaje, ReaccionMensaje
from modulos.chat.dominio.value_objects.tipos_chat import TipoConversacion, RolParticipante


class RepositorioConversacion(ABC):
    """
    Interface para el repositorio de conversaciones.
    """

    @abstractmethod
    def buscar_por_id(self, conversacion_id: int) -> Optional[Conversacion]:
        """Busca una conversacion por su ID."""
        pass

    @abstractmethod
    def buscar_por_public_id(self, public_id: str) -> Optional[Conversacion]:
        """Busca una conversacion por su ID publico (UUID)."""
        pass

    @abstractmethod
    def obtener_conversaciones_usuario(
        self,
        usuario_id: int,
        limite: int = 20,
        offset: int = 0
    ) -> List[Conversacion]:
        """Obtiene las conversaciones de un usuario ordenadas por ultimo mensaje."""
        pass

    @abstractmethod
    def buscar_directa(
        self,
        usuario1_id: int,
        usuario2_id: int
    ) -> Optional[Conversacion]:
        """Busca una conversacion directa entre dos usuarios."""
        pass

    @abstractmethod
    def crear(self, conversacion: Conversacion) -> Conversacion:
        """Crea una nueva conversacion."""
        pass

    @abstractmethod
    def actualizar(self, conversacion: Conversacion) -> Conversacion:
        """Actualiza una conversacion existente."""
        pass

    @abstractmethod
    def actualizar_ultimo_mensaje(
        self,
        conversacion_id: int,
        contenido: str,
        fecha: datetime
    ) -> None:
        """Actualiza la informacion del ultimo mensaje."""
        pass


class RepositorioParticipante(ABC):
    """
    Interface para el repositorio de participantes.
    """

    @abstractmethod
    def buscar_por_id(self, participante_id: int) -> Optional[Participante]:
        """Busca un participante por su ID."""
        pass

    @abstractmethod
    def buscar_en_conversacion(
        self,
        conversacion_id: int,
        usuario_id: int
    ) -> Optional[Participante]:
        """Busca un participante en una conversacion especifica."""
        pass

    @abstractmethod
    def obtener_participantes(
        self,
        conversacion_id: int,
        solo_activos: bool = True
    ) -> List[Participante]:
        """Obtiene todos los participantes de una conversacion."""
        pass

    @abstractmethod
    def agregar(self, participante: Participante) -> Participante:
        """Agrega un participante a una conversacion."""
        pass

    @abstractmethod
    def agregar_varios(
        self,
        conversacion_id: int,
        usuario_ids: List[int],
        rol: RolParticipante = RolParticipante.MIEMBRO
    ) -> List[Participante]:
        """Agrega varios participantes a una conversacion."""
        pass

    @abstractmethod
    def actualizar(self, participante: Participante) -> Participante:
        """Actualiza un participante."""
        pass

    @abstractmethod
    def desactivar(self, conversacion_id: int, usuario_id: int) -> bool:
        """Desactiva (elimina logicamente) un participante."""
        pass

    @abstractmethod
    def marcar_leido(
        self,
        conversacion_id: int,
        usuario_id: int,
        hasta_mensaje_id: int
    ) -> None:
        """Marca mensajes como leidos hasta cierto ID."""
        pass

    @abstractmethod
    def obtener_no_leidos(self, usuario_id: int) -> int:
        """Obtiene el total de mensajes no leidos del usuario."""
        pass


class RepositorioMensaje(ABC):
    """
    Interface para el repositorio de mensajes.
    """

    @abstractmethod
    def buscar_por_id(self, mensaje_id: int) -> Optional[Mensaje]:
        """Busca un mensaje por su ID."""
        pass

    @abstractmethod
    def buscar_por_public_id(self, public_id: str) -> Optional[Mensaje]:
        """Busca un mensaje por su ID publico (UUID)."""
        pass

    @abstractmethod
    def obtener_mensajes(
        self,
        conversacion_id: int,
        limite: int = 50,
        antes_de_id: Optional[int] = None
    ) -> List[Mensaje]:
        """
        Obtiene mensajes de una conversacion con paginacion.

        Args:
            conversacion_id: ID de la conversacion
            limite: Cantidad maxima de mensajes
            antes_de_id: Obtener mensajes anteriores a este ID

        Returns:
            Lista de mensajes ordenados por fecha descendente
        """
        pass

    @abstractmethod
    def crear(self, mensaje: Mensaje) -> Mensaje:
        """Crea un nuevo mensaje."""
        pass

    @abstractmethod
    def actualizar(self, mensaje: Mensaje) -> Mensaje:
        """Actualiza un mensaje existente."""
        pass

    @abstractmethod
    def eliminar(
        self,
        mensaje_id: int,
        para_todos: bool = False
    ) -> bool:
        """Elimina (soft delete) un mensaje."""
        pass

    @abstractmethod
    def buscar(
        self,
        usuario_id: int,
        consulta: str,
        conversacion_id: Optional[int] = None,
        limite: int = 50
    ) -> List[Mensaje]:
        """
        Busca mensajes por contenido.

        Args:
            usuario_id: ID del usuario que busca
            consulta: Texto a buscar
            conversacion_id: Opcional, limitar a una conversacion
            limite: Cantidad maxima de resultados

        Returns:
            Lista de mensajes que coinciden
        """
        pass

    @abstractmethod
    def contar_no_leidos(
        self,
        conversacion_id: int,
        usuario_id: int,
        desde_mensaje_id: Optional[int] = None
    ) -> int:
        """Cuenta mensajes no leidos en una conversacion."""
        pass


class RepositorioArchivoMensaje(ABC):
    """
    Interface para el repositorio de archivos de mensajes.
    """

    @abstractmethod
    def buscar_por_id(self, archivo_id: int) -> Optional[ArchivoMensaje]:
        """Busca un archivo por su ID."""
        pass

    @abstractmethod
    def obtener_archivos_mensaje(self, mensaje_id: int) -> List[ArchivoMensaje]:
        """Obtiene todos los archivos de un mensaje."""
        pass

    @abstractmethod
    def crear(self, archivo: ArchivoMensaje) -> ArchivoMensaje:
        """Crea un nuevo registro de archivo."""
        pass

    @abstractmethod
    def crear_varios(self, archivos: List[ArchivoMensaje]) -> List[ArchivoMensaje]:
        """Crea varios registros de archivos."""
        pass

    @abstractmethod
    def eliminar(self, archivo_id: int) -> bool:
        """Elimina un archivo."""
        pass


class RepositorioReaccion(ABC):
    """
    Interface para el repositorio de reacciones.
    """

    @abstractmethod
    def buscar(
        self,
        mensaje_id: int,
        usuario_id: int
    ) -> Optional[ReaccionMensaje]:
        """Busca una reaccion de un usuario en un mensaje."""
        pass

    @abstractmethod
    def obtener_reacciones_mensaje(
        self,
        mensaje_id: int
    ) -> List[ReaccionMensaje]:
        """Obtiene todas las reacciones de un mensaje."""
        pass

    @abstractmethod
    def agregar(self, reaccion: ReaccionMensaje) -> ReaccionMensaje:
        """Agrega una reaccion (reemplaza si ya existe)."""
        pass

    @abstractmethod
    def eliminar(self, mensaje_id: int, usuario_id: int) -> bool:
        """Elimina una reaccion."""
        pass

    @abstractmethod
    def contar_por_emoji(self, mensaje_id: int) -> dict:
        """Cuenta reacciones agrupadas por emoji."""
        pass


class RepositorioPresencia(ABC):
    """
    Interface para el repositorio de presencia de usuarios.
    """

    @abstractmethod
    def actualizar_presencia(self, usuario_id: int, en_linea: bool = True) -> None:
        """Actualiza el estado de presencia de un usuario."""
        pass

    @abstractmethod
    def obtener_presencia(self, usuario_id: int) -> Tuple[bool, Optional[datetime]]:
        """
        Obtiene el estado de presencia de un usuario.

        Returns:
            Tupla (en_linea, ultima_vez)
        """
        pass

    @abstractmethod
    def obtener_presencia_multiple(
        self,
        usuario_ids: List[int]
    ) -> dict:
        """
        Obtiene el estado de presencia de multiples usuarios.

        Returns:
            Dict {usuario_id: {'online': bool, 'last_seen': datetime}}
        """
        pass

    @abstractmethod
    def marcar_offline(self, usuario_id: int) -> None:
        """Marca a un usuario como offline."""
        pass


class RepositorioBloqueo(ABC):
    """
    Interface para el repositorio de bloqueos entre usuarios.
    """

    @abstractmethod
    def esta_bloqueado(
        self,
        bloqueador_id: int,
        bloqueado_id: int
    ) -> bool:
        """Verifica si un usuario tiene bloqueado a otro."""
        pass

    @abstractmethod
    def hay_bloqueo_mutuo(
        self,
        usuario1_id: int,
        usuario2_id: int
    ) -> bool:
        """Verifica si hay bloqueo en alguna direccion entre dos usuarios."""
        pass

    @abstractmethod
    def bloquear(
        self,
        bloqueador_id: int,
        bloqueado_id: int,
        razon: Optional[str] = None
    ) -> bool:
        """Bloquea a un usuario."""
        pass

    @abstractmethod
    def desbloquear(
        self,
        bloqueador_id: int,
        bloqueado_id: int
    ) -> bool:
        """Desbloquea a un usuario."""
        pass

    @abstractmethod
    def obtener_bloqueados(self, usuario_id: int) -> List[int]:
        """Obtiene la lista de IDs de usuarios bloqueados."""
        pass


class RepositorioIndicadorAccion(ABC):
    """
    Interface para el repositorio de indicadores de accion.
    Maneja estados como: escribiendo, grabando audio/video, etc.
    """

    @abstractmethod
    def establecer_accion(
        self,
        conversacion_id: int,
        usuario_id: int,
        accion: str
    ) -> None:
        """
        Establece la accion actual del usuario.

        Args:
            conversacion_id: ID de la conversacion
            usuario_id: ID del usuario
            accion: Tipo de accion (typing, recording_audio, etc.)
        """
        pass

    @abstractmethod
    def limpiar_accion(
        self,
        conversacion_id: int,
        usuario_id: int
    ) -> None:
        """Limpia la accion del usuario."""
        pass

    @abstractmethod
    def obtener_acciones_conversacion(
        self,
        conversacion_id: int,
        excepto_usuario_id: Optional[int] = None
    ) -> List[Tuple[int, str, datetime]]:
        """
        Obtiene las acciones activas en una conversacion.

        Returns:
            Lista de tuplas (usuario_id, accion, inicio)
        """
        pass

    @abstractmethod
    def limpiar_acciones_expiradas(self, segundos: int = 10) -> int:
        """
        Limpia acciones que llevan mas de N segundos.

        Returns:
            Cantidad de acciones limpiadas
        """
        pass
