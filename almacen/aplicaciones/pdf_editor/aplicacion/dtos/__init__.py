# -*- coding: utf-8 -*-
"""
DTOs (Data Transfer Objects) - PDF Editor.

Objetos para transferir datos entre capas.
"""

from .documento_dto import DocumentoDTO, DocumentoResumenDTO
from .pagina_dto import PaginaDTO, ThumbnailDTO
from .anotacion_dto import AnotacionDTO, CrearAnotacionDTO
from .respuesta_dto import RespuestaAPI, PaginacionDTO

__all__ = [
    'DocumentoDTO',
    'DocumentoResumenDTO',
    'PaginaDTO',
    'ThumbnailDTO',
    'AnotacionDTO',
    'CrearAnotacionDTO',
    'RespuestaAPI',
    'PaginacionDTO'
]
