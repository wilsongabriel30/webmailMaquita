# -*- coding: utf-8 -*-
"""
Interface: Repositorio de Anotaciones PDF.
"""

from abc import ABC, abstractmethod
from typing import Optional, List

from ..entidades.anotacion import Anotacion


class IRepositorioAnotacion(ABC):
    """
    Interface para el repositorio de anotaciones.
    """

    @abstractmethod
    def guardar(self, anotacion: Anotacion) -> Anotacion:
        """
        Guarda una anotación (crear o actualizar).

        Args:
            anotacion: Anotación a guardar

        Returns:
            Anotación guardada con ID
        """
        pass

    @abstractmethod
    def obtener_por_id(self, id: int) -> Optional[Anotacion]:
        """
        Obtiene una anotación por ID.
        """
        pass

    @abstractmethod
    def obtener_por_documento(
        self,
        documento_id: int,
        incluir_eliminadas: bool = False
    ) -> List[Anotacion]:
        """
        Obtiene todas las anotaciones de un documento.
        """
        pass

    @abstractmethod
    def obtener_por_pagina(
        self,
        documento_id: int,
        pagina: int
    ) -> List[Anotacion]:
        """
        Obtiene las anotaciones de una página específica.
        """
        pass

    @abstractmethod
    def obtener_por_usuario(
        self,
        documento_id: int,
        usuario_id: int
    ) -> List[Anotacion]:
        """
        Obtiene las anotaciones de un usuario en un documento.
        """
        pass

    @abstractmethod
    def eliminar(self, id: int) -> bool:
        """
        Elimina una anotación (soft delete).
        """
        pass

    @abstractmethod
    def eliminar_por_documento(self, documento_id: int) -> int:
        """
        Elimina todas las anotaciones de un documento.

        Returns:
            Número de anotaciones eliminadas
        """
        pass

    @abstractmethod
    def contar_por_documento(self, documento_id: int) -> int:
        """
        Cuenta las anotaciones de un documento.
        """
        pass

    @abstractmethod
    def contar_por_pagina(self, documento_id: int, pagina: int) -> int:
        """
        Cuenta las anotaciones de una página.
        """
        pass

    @abstractmethod
    def resolver(self, id: int) -> bool:
        """
        Marca una anotación como resuelta.
        """
        pass

    @abstractmethod
    def reabrir(self, id: int) -> bool:
        """
        Reabre una anotación resuelta.
        """
        pass
