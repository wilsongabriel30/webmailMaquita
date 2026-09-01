# -*- coding: utf-8 -*-
"""
DTOs para Anotaciones PDF.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Dict, Any, List


@dataclass
class AnotacionDTO:
    """
    DTO de anotación.
    """

    id: int
    documento_id: int
    usuario_id: int
    pagina: int
    tipo: str
    contenido: Optional[str]
    coordenadas: Dict[str, float]
    estilo: Dict[str, Any]
    estado: str
    created_at: datetime
    updated_at: datetime
    usuario_nombre: Optional[str] = None

    @classmethod
    def desde_entidad(cls, entidad, usuario_nombre: str = None) -> 'AnotacionDTO':
        """Crea DTO desde entidad."""
        return cls(
            id=entidad.id,
            documento_id=entidad.documento_id,
            usuario_id=entidad.usuario_id,
            pagina=entidad.pagina,
            tipo=entidad.tipo.value if hasattr(entidad.tipo, 'value') else entidad.tipo,
            contenido=entidad.contenido,
            coordenadas=entidad.coordenadas,
            estilo=entidad.estilo,
            estado=entidad.estado.value if hasattr(entidad.estado, 'value') else entidad.estado,
            created_at=entidad.created_at,
            updated_at=entidad.updated_at,
            usuario_nombre=usuario_nombre
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convierte a diccionario."""
        return {
            'id': self.id,
            'documento_id': self.documento_id,
            'usuario_id': self.usuario_id,
            'usuario_nombre': self.usuario_nombre,
            'pagina': self.pagina,
            'tipo': self.tipo,
            'contenido': self.contenido,
            'coordenadas': self.coordenadas,
            'estilo': self.estilo,
            'estado': self.estado,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }


@dataclass
class CrearAnotacionDTO:
    """
    DTO para crear anotación.
    """

    documento_id: int
    usuario_id: int
    pagina: int
    tipo: str
    coordenadas: Dict[str, float]
    contenido: Optional[str] = None
    estilo: Dict[str, Any] = field(default_factory=lambda: {
        'color': '#FFFF00',
        'opacidad': 0.5,
        'grosor': 1
    })


@dataclass
class ActualizarAnotacionDTO:
    """
    DTO para actualizar anotación.
    """

    id: int
    contenido: Optional[str] = None
    coordenadas: Optional[Dict[str, float]] = None
    estilo: Optional[Dict[str, Any]] = None
    estado: Optional[str] = None


@dataclass
class ExportarAnotacionesDTO:
    """
    DTO para exportar anotaciones.
    """

    documento_id: int
    formato: str = 'xfdf'  # xfdf, json
    incluir_resueltas: bool = True


@dataclass
class AnotacionesExportadasDTO:
    """
    DTO con anotaciones exportadas.
    """

    documento_id: int
    formato: str
    contenido: str
    nombre_archivo: str
    total_anotaciones: int


@dataclass
class SelloDTO:
    """
    DTO para sellos predefinidos.
    """

    tipo: str  # aprobado, rechazado, revisado, etc.
    texto: str
    color: str
    pagina: int
    x: float
    y: float
    ancho: float = 150
    alto: float = 50
    rotacion: float = 0
