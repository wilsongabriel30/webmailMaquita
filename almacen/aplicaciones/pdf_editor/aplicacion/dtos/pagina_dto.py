# -*- coding: utf-8 -*-
"""
DTOs para Páginas PDF.
"""

from dataclasses import dataclass
from typing import Optional, Dict, Any


@dataclass
class PaginaDTO:
    """
    DTO de página PDF.
    """

    numero: int
    documento_id: int
    ancho: float
    alto: float
    rotacion: int
    tiene_imagenes: bool
    tiene_formularios: bool
    anotaciones_count: int
    orientacion: str

    @classmethod
    def desde_entidad(cls, entidad) -> 'PaginaDTO':
        """Crea DTO desde entidad."""
        return cls(
            numero=entidad.numero,
            documento_id=entidad.documento_id,
            ancho=entidad.ancho,
            alto=entidad.alto,
            rotacion=entidad.rotacion,
            tiene_imagenes=entidad.tiene_imagenes,
            tiene_formularios=entidad.tiene_formularios,
            anotaciones_count=entidad.anotaciones_count,
            orientacion=entidad.orientacion
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convierte a diccionario."""
        return {
            'numero': self.numero,
            'documento_id': self.documento_id,
            'ancho': self.ancho,
            'alto': self.alto,
            'rotacion': self.rotacion,
            'tiene_imagenes': self.tiene_imagenes,
            'tiene_formularios': self.tiene_formularios,
            'anotaciones_count': self.anotaciones_count,
            'orientacion': self.orientacion
        }


@dataclass
class ThumbnailDTO:
    """
    DTO para miniatura de página.
    """

    documento_id: int
    pagina: int
    ancho: int
    alto: int
    formato: str
    datos_base64: Optional[str] = None
    url: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convierte a diccionario."""
        return {
            'documento_id': self.documento_id,
            'pagina': self.pagina,
            'ancho': self.ancho,
            'alto': self.alto,
            'formato': self.formato,
            'datos_base64': self.datos_base64,
            'url': self.url
        }


@dataclass
class RenderPaginaDTO:
    """
    DTO para solicitud de renderizado.
    """

    documento_id: int
    pagina: int
    zoom: float = 1.0
    formato: str = 'png'
    calidad: str = 'media'  # baja, media, alta, maxima


@dataclass
class RotarPaginaDTO:
    """
    DTO para rotación de página.
    """

    documento_id: int
    pagina: int
    grados: int  # 90, 180, 270, -90


@dataclass
class ReordenarPaginasDTO:
    """
    DTO para reordenamiento de páginas.
    """

    documento_id: int
    orden_nuevo: list  # Lista de números de página en nuevo orden


@dataclass
class ExtraerPaginasDTO:
    """
    DTO para extracción de páginas.
    """

    documento_id: int
    paginas: list  # Lista de números de página a extraer
    nombre_nuevo: Optional[str] = None
