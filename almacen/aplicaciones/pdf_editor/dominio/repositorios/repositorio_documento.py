# -*- coding: utf-8 -*-
"""
Interface: Repositorio de Documentos PDF.

Define el contrato para la persistencia de documentos.
"""

from abc import ABC, abstractmethod
from typing import Optional, List, Dict, Any

from ..entidades.documento_pdf import DocumentoPDF


class IRepositorioDocumento(ABC):
    """
    Interface para el repositorio de documentos PDF.

    Esta es la definición del puerto (hexagonal) que debe ser
    implementado por un adaptador en la capa de infraestructura.
    """

    @abstractmethod
    def guardar(self, documento: DocumentoPDF) -> DocumentoPDF:
        """
        Guarda un documento (crear o actualizar).

        Args:
            documento: Documento a guardar

        Returns:
            Documento guardado con ID asignado
        """
        pass

    @abstractmethod
    def obtener_por_id(self, id: int) -> Optional[DocumentoPDF]:
        """
        Obtiene un documento por su ID.

        Args:
            id: ID del documento

        Returns:
            Documento o None si no existe
        """
        pass

    @abstractmethod
    def obtener_por_usuario(
        self,
        usuario_id: int,
        incluir_eliminados: bool = False,
        limite: int = 100,
        offset: int = 0
    ) -> List[DocumentoPDF]:
        """
        Obtiene todos los documentos de un usuario.

        Args:
            usuario_id: ID del usuario
            incluir_eliminados: Si incluir documentos eliminados
            limite: Máximo de resultados
            offset: Desplazamiento para paginación

        Returns:
            Lista de documentos
        """
        pass

    @abstractmethod
    def buscar(
        self,
        usuario_id: int,
        termino: str,
        limite: int = 50
    ) -> List[DocumentoPDF]:
        """
        Busca documentos por texto.

        Args:
            usuario_id: ID del usuario
            termino: Término de búsqueda
            limite: Máximo de resultados

        Returns:
            Lista de documentos que coinciden
        """
        pass

    @abstractmethod
    def eliminar(self, id: int) -> bool:
        """
        Elimina un documento (soft delete).

        Args:
            id: ID del documento

        Returns:
            True si se eliminó correctamente
        """
        pass

    @abstractmethod
    def eliminar_permanente(self, id: int) -> bool:
        """
        Elimina un documento permanentemente.

        Args:
            id: ID del documento

        Returns:
            True si se eliminó
        """
        pass

    @abstractmethod
    def contar_por_usuario(self, usuario_id: int) -> int:
        """
        Cuenta los documentos de un usuario.

        Args:
            usuario_id: ID del usuario

        Returns:
            Número de documentos
        """
        pass

    @abstractmethod
    def obtener_estadisticas(self, usuario_id: int) -> Dict[str, Any]:
        """
        Obtiene estadísticas de documentos del usuario.

        Args:
            usuario_id: ID del usuario

        Returns:
            Diccionario con estadísticas
        """
        pass

    @abstractmethod
    def actualizar_metadata(self, id: int, metadata: Dict[str, Any]) -> bool:
        """
        Actualiza los metadatos de un documento.

        Args:
            id: ID del documento
            metadata: Nuevos metadatos

        Returns:
            True si se actualizó
        """
        pass

    @abstractmethod
    def marcar_ocr(self, id: int, texto: str = None) -> bool:
        """
        Marca un documento como procesado con OCR.

        Args:
            id: ID del documento
            texto: Texto extraído

        Returns:
            True si se actualizó
        """
        pass
