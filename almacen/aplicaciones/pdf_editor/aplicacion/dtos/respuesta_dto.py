# -*- coding: utf-8 -*-
"""
DTOs para respuestas de API.
"""

from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List, Generic, TypeVar

T = TypeVar('T')


@dataclass
class RespuestaAPI:
    """
    DTO estándar para respuestas de API.
    """

    exito: bool
    mensaje: Optional[str] = None
    datos: Optional[Any] = None
    errores: List[str] = field(default_factory=list)
    codigo: str = 'OK'

    @classmethod
    def ok(cls, datos: Any = None, mensaje: str = None) -> 'RespuestaAPI':
        """Crea respuesta exitosa."""
        return cls(
            exito=True,
            mensaje=mensaje,
            datos=datos,
            codigo='OK'
        )

    @classmethod
    def error(
        cls,
        mensaje: str,
        codigo: str = 'ERROR',
        errores: List[str] = None
    ) -> 'RespuestaAPI':
        """Crea respuesta de error."""
        return cls(
            exito=False,
            mensaje=mensaje,
            codigo=codigo,
            errores=errores or []
        )

    @classmethod
    def desde_excepcion(cls, exc: Exception) -> 'RespuestaAPI':
        """Crea respuesta desde excepción."""
        from ...dominio.excepciones import PDFEditorError

        if isinstance(exc, PDFEditorError):
            return cls(
                exito=False,
                mensaje=exc.mensaje,
                codigo=exc.codigo,
                errores=[str(exc)]
            )

        return cls(
            exito=False,
            mensaje=str(exc),
            codigo='ERROR_INTERNO',
            errores=[str(exc)]
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convierte a diccionario para JSON."""
        resultado = {
            'exito': self.exito,
            'codigo': self.codigo
        }

        if self.mensaje:
            resultado['mensaje'] = self.mensaje

        if self.datos is not None:
            if hasattr(self.datos, 'to_dict'):
                resultado['datos'] = self.datos.to_dict()
            elif isinstance(self.datos, list):
                resultado['datos'] = [
                    d.to_dict() if hasattr(d, 'to_dict') else d
                    for d in self.datos
                ]
            else:
                resultado['datos'] = self.datos

        if self.errores:
            resultado['errores'] = self.errores

        return resultado


@dataclass
class PaginacionDTO:
    """
    DTO para información de paginación.
    """

    total: int
    pagina: int
    por_pagina: int
    total_paginas: int

    @classmethod
    def calcular(cls, total: int, pagina: int, por_pagina: int) -> 'PaginacionDTO':
        """Calcula paginación."""
        import math
        total_paginas = math.ceil(total / por_pagina) if por_pagina > 0 else 0

        return cls(
            total=total,
            pagina=pagina,
            por_pagina=por_pagina,
            total_paginas=total_paginas
        )

    @property
    def tiene_siguiente(self) -> bool:
        """Indica si hay página siguiente."""
        return self.pagina < self.total_paginas

    @property
    def tiene_anterior(self) -> bool:
        """Indica si hay página anterior."""
        return self.pagina > 1

    @property
    def offset(self) -> int:
        """Calcula el offset para consultas."""
        return (self.pagina - 1) * self.por_pagina

    def to_dict(self) -> Dict[str, Any]:
        """Convierte a diccionario."""
        return {
            'total': self.total,
            'pagina': self.pagina,
            'por_pagina': self.por_pagina,
            'total_paginas': self.total_paginas,
            'tiene_siguiente': self.tiene_siguiente,
            'tiene_anterior': self.tiene_anterior
        }


@dataclass
class RespuestaPaginada:
    """
    DTO para respuestas paginadas.
    """

    items: List[Any]
    paginacion: PaginacionDTO

    def to_dict(self) -> Dict[str, Any]:
        """Convierte a diccionario."""
        return {
            'items': [
                i.to_dict() if hasattr(i, 'to_dict') else i
                for i in self.items
            ],
            'paginacion': self.paginacion.to_dict()
        }


@dataclass
class EstadisticasDTO:
    """
    DTO para estadísticas del usuario.
    """

    total_documentos: int
    total_paginas: int
    espacio_usado_bytes: int
    documentos_con_ocr: int
    total_anotaciones: int
    total_formularios: int

    @property
    def espacio_formateado(self) -> str:
        """Espacio usado en formato legible."""
        bytes = self.espacio_usado_bytes
        for unidad in ['B', 'KB', 'MB', 'GB']:
            if bytes < 1024:
                return f"{bytes:.1f} {unidad}"
            bytes /= 1024
        return f"{bytes:.1f} TB"

    def to_dict(self) -> Dict[str, Any]:
        """Convierte a diccionario."""
        return {
            'total_documentos': self.total_documentos,
            'total_paginas': self.total_paginas,
            'espacio_usado_bytes': self.espacio_usado_bytes,
            'espacio_formateado': self.espacio_formateado,
            'documentos_con_ocr': self.documentos_con_ocr,
            'total_anotaciones': self.total_anotaciones,
            'total_formularios': self.total_formularios
        }
