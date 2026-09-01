# -*- coding: utf-8 -*-
"""
Interface: Repositorio de Versiones de Documento.
"""

from abc import ABC, abstractmethod
from typing import Optional, List

from ..entidades.version import VersionDocumento


class IRepositorioVersion(ABC):
    """
    Interface para el repositorio de versiones.
    """

    @abstractmethod
    def guardar(self, version: VersionDocumento) -> VersionDocumento:
        """
        Guarda una versión.

        Args:
            version: Versión a guardar

        Returns:
            Versión guardada con ID
        """
        pass

    @abstractmethod
    def obtener_por_id(self, id: int) -> Optional[VersionDocumento]:
        """
        Obtiene una versión por ID.
        """
        pass

    @abstractmethod
    def obtener_por_documento(
        self,
        documento_id: int
    ) -> List[VersionDocumento]:
        """
        Obtiene todas las versiones de un documento.

        Returns:
            Lista ordenada por número de versión
        """
        pass

    @abstractmethod
    def obtener_version_especifica(
        self,
        documento_id: int,
        numero_version: int
    ) -> Optional[VersionDocumento]:
        """
        Obtiene una versión específica de un documento.
        """
        pass

    @abstractmethod
    def obtener_ultima_version(
        self,
        documento_id: int
    ) -> Optional[VersionDocumento]:
        """
        Obtiene la última versión de un documento.
        """
        pass

    @abstractmethod
    def obtener_numero_siguiente(self, documento_id: int) -> int:
        """
        Obtiene el siguiente número de versión disponible.
        """
        pass

    @abstractmethod
    def eliminar(self, id: int) -> bool:
        """
        Elimina una versión.
        """
        pass

    @abstractmethod
    def eliminar_por_documento(self, documento_id: int) -> int:
        """
        Elimina todas las versiones de un documento.

        Returns:
            Número de versiones eliminadas
        """
        pass

    @abstractmethod
    def contar_por_documento(self, documento_id: int) -> int:
        """
        Cuenta las versiones de un documento.
        """
        pass
