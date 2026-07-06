# -*- coding: utf-8 -*-
"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                    INTERFACES DE BUSQUEDA - DOMINIO                          ║
║              Puertos para Motor de Busqueda (Elasticsearch)                  ║
╚══════════════════════════════════════════════════════════════════════════════╝

██████████████████████████████████████████████████████████████████████████████
██  REGLAS PARA ESTAS INTERFACES                                             ██
██████████████████████████████████████████████████████████████████████████████

1. Son INTERFACES (ABC), no implementaciones
2. Las implementaciones van en infraestructura/busqueda/
3. NO dependen de Elasticsearch ni ninguna tecnologia especifica
4. Definen QUE se necesita buscar, no COMO

IMPLEMENTACIONES ESPERADAS:
- BuscadorMensajesElasticsearch -> infraestructura/busqueda/buscador_mensajes.py
- IndexadorMensajesElasticsearch -> infraestructura/busqueda/indexador_mensajes.py

Autor: Wilson Arguello
Correo: gestiontecnologia@maquita.com.ec
Fecha: 2026-01-02
"""

from abc import ABC, abstractmethod
from typing import Optional, List, Dict, Any
from datetime import datetime
from dataclasses import dataclass

from ..entidades.mensaje import Mensaje
from ..value_objects.tipos_chat import TipoMensaje


@dataclass
class ResultadoBusqueda:
    """
    Resultado de una busqueda de mensajes.

    Incluye metadata para paginacion y highlighting.
    """
    mensajes: List[Dict[str, Any]]
    total: int
    pagina: int
    paginas_totales: int
    tiempo_ms: float
    query_original: str

    @property
    def tiene_mas(self) -> bool:
        """Indica si hay mas paginas."""
        return self.pagina < self.paginas_totales


@dataclass
class FiltrosBusqueda:
    """
    Filtros para busqueda de mensajes.
    """
    query: str
    usuario_id: int  # Para verificar permisos
    conversacion_id: Optional[int] = None
    remitente_id: Optional[int] = None
    tipo_mensaje: Optional[TipoMensaje] = None
    fecha_desde: Optional[datetime] = None
    fecha_hasta: Optional[datetime] = None
    solo_con_archivos: bool = False
    pagina: int = 1
    por_pagina: int = 20


class BuscadorMensajes(ABC):
    """
    Interface para busqueda de mensajes.

    Proposito:
    - Busqueda full-text en contenido de mensajes
    - Filtrado por conversacion, fecha, tipo
    - Highlighting de resultados
    - Latencia objetivo: < 50ms
    """

    @abstractmethod
    def buscar(self, filtros: FiltrosBusqueda) -> ResultadoBusqueda:
        """
        Busca mensajes segun los filtros.

        Args:
            filtros: Criterios de busqueda

        Returns:
            ResultadoBusqueda con mensajes y metadata
        """
        pass

    @abstractmethod
    def buscar_en_conversacion(
        self,
        conversacion_id: int,
        query: str,
        usuario_id: int,
        limite: int = 50
    ) -> List[Dict[str, Any]]:
        """
        Busqueda rapida dentro de una conversacion.

        Args:
            conversacion_id: ID de la conversacion
            query: Texto a buscar
            usuario_id: ID del usuario (para permisos)
            limite: Maximo de resultados

        Returns:
            Lista de mensajes encontrados
        """
        pass

    @abstractmethod
    def buscar_global(
        self,
        usuario_id: int,
        query: str,
        limite: int = 50
    ) -> List[Dict[str, Any]]:
        """
        Busqueda en todas las conversaciones del usuario.

        Args:
            usuario_id: ID del usuario
            query: Texto a buscar
            limite: Maximo de resultados

        Returns:
            Lista de mensajes encontrados (de todas sus conversaciones)
        """
        pass

    @abstractmethod
    def sugerir(
        self,
        usuario_id: int,
        prefijo: str,
        limite: int = 10
    ) -> List[str]:
        """
        Sugiere terminos de busqueda basado en un prefijo.

        Args:
            usuario_id: ID del usuario
            prefijo: Inicio del termino a buscar
            limite: Maximo de sugerencias

        Returns:
            Lista de sugerencias
        """
        pass


class IndexadorMensajes(ABC):
    """
    Interface para indexacion de mensajes.

    Proposito:
    - Indexar mensajes nuevos para busqueda
    - Actualizar mensajes editados
    - Eliminar mensajes del indice
    - Reindexar conversaciones completas
    """

    @abstractmethod
    def indexar(self, mensaje: Dict[str, Any]) -> bool:
        """
        Indexa un mensaje nuevo.

        Args:
            mensaje: Datos del mensaje a indexar

        Returns:
            True si se indexo correctamente
        """
        pass

    @abstractmethod
    def indexar_lote(self, mensajes: List[Dict[str, Any]]) -> int:
        """
        Indexa multiples mensajes en batch.

        Args:
            mensajes: Lista de mensajes a indexar

        Returns:
            Numero de mensajes indexados exitosamente
        """
        pass

    @abstractmethod
    def actualizar(
        self,
        mensaje_id: int,
        campos: Dict[str, Any]
    ) -> bool:
        """
        Actualiza un mensaje en el indice.

        Args:
            mensaje_id: ID del mensaje
            campos: Campos a actualizar

        Returns:
            True si se actualizo correctamente
        """
        pass

    @abstractmethod
    def eliminar(self, mensaje_id: int) -> bool:
        """
        Elimina un mensaje del indice.

        Args:
            mensaje_id: ID del mensaje a eliminar

        Returns:
            True si se elimino correctamente
        """
        pass

    @abstractmethod
    def eliminar_conversacion(self, conversacion_id: int) -> int:
        """
        Elimina todos los mensajes de una conversacion del indice.

        Args:
            conversacion_id: ID de la conversacion

        Returns:
            Numero de mensajes eliminados
        """
        pass

    @abstractmethod
    def reindexar_conversacion(
        self,
        conversacion_id: int,
        mensajes: List[Dict[str, Any]]
    ) -> int:
        """
        Reindexa todos los mensajes de una conversacion.

        Args:
            conversacion_id: ID de la conversacion
            mensajes: Mensajes a indexar

        Returns:
            Numero de mensajes indexados
        """
        pass


class AdministradorIndice(ABC):
    """
    Interface para administracion del indice.

    Proposito:
    - Crear/eliminar indices
    - Configurar mappings
    - Obtener estadisticas
    - Optimizar indices
    """

    @abstractmethod
    def crear_indice(self, nombre: str, configuracion: Dict[str, Any]) -> bool:
        """
        Crea un nuevo indice.

        Args:
            nombre: Nombre del indice
            configuracion: Mapping y settings

        Returns:
            True si se creo correctamente
        """
        pass

    @abstractmethod
    def existe_indice(self, nombre: str) -> bool:
        """
        Verifica si un indice existe.

        Args:
            nombre: Nombre del indice

        Returns:
            True si existe
        """
        pass

    @abstractmethod
    def eliminar_indice(self, nombre: str) -> bool:
        """
        Elimina un indice.

        Args:
            nombre: Nombre del indice

        Returns:
            True si se elimino correctamente
        """
        pass

    @abstractmethod
    def obtener_estadisticas(self, nombre: str) -> Dict[str, Any]:
        """
        Obtiene estadisticas del indice.

        Args:
            nombre: Nombre del indice

        Returns:
            Estadisticas (docs, size, etc.)
        """
        pass

    @abstractmethod
    def refrescar(self, nombre: str) -> bool:
        """
        Refresca el indice (hace documentos buscables).

        Args:
            nombre: Nombre del indice

        Returns:
            True si se refresco correctamente
        """
        pass

    @abstractmethod
    def optimizar(self, nombre: str) -> bool:
        """
        Optimiza el indice (merge segments).

        Args:
            nombre: Nombre del indice

        Returns:
            True si se optimizo correctamente
        """
        pass
