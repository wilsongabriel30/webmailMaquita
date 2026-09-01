# -*- coding: utf-8 -*-
"""
DTOs para Formularios PDF.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Dict, Any, List


@dataclass
class CampoFormularioDTO:
    """
    DTO de campo de formulario.
    """

    id: str
    nombre: str
    tipo: str
    pagina: int
    coordenadas: Dict[str, float]
    propiedades: Dict[str, Any]
    valor_defecto: Optional[Any] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convierte a diccionario."""
        return {
            'id': self.id,
            'nombre': self.nombre,
            'tipo': self.tipo,
            'pagina': self.pagina,
            'coordenadas': self.coordenadas,
            'propiedades': self.propiedades,
            'valor_defecto': self.valor_defecto
        }


@dataclass
class FormularioDTO:
    """
    DTO de formulario completo.
    """

    id: int
    documento_id: int
    nombre: Optional[str]
    campos: List[CampoFormularioDTO]
    validaciones: Dict[str, Any]
    created_at: datetime
    updated_at: datetime

    @classmethod
    def desde_entidad(cls, entidad) -> 'FormularioDTO':
        """Crea DTO desde entidad."""
        campos = [
            CampoFormularioDTO(
                id=c.id,
                nombre=c.nombre,
                tipo=c.tipo.value if hasattr(c.tipo, 'value') else c.tipo,
                pagina=c.pagina,
                coordenadas=c.coordenadas,
                propiedades=c.propiedades,
                valor_defecto=c.valor_defecto
            )
            for c in entidad.campos
        ]

        return cls(
            id=entidad.id,
            documento_id=entidad.documento_id,
            nombre=entidad.nombre,
            campos=campos,
            validaciones=entidad.validaciones,
            created_at=entidad.created_at,
            updated_at=entidad.updated_at
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convierte a diccionario."""
        return {
            'id': self.id,
            'documento_id': self.documento_id,
            'nombre': self.nombre,
            'campos': [c.to_dict() for c in self.campos],
            'validaciones': self.validaciones,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }


@dataclass
class CrearCampoDTO:
    """
    DTO para crear campo de formulario.
    """

    nombre: str
    tipo: str
    pagina: int
    coordenadas: Dict[str, float]
    propiedades: Dict[str, Any] = field(default_factory=dict)
    valor_defecto: Optional[Any] = None


@dataclass
class RellenarFormularioDTO:
    """
    DTO para rellenar formulario.
    """

    documento_id: int
    usuario_id: int
    datos: Dict[str, Any]
    completar: bool = False


@dataclass
class RespuestaFormularioDTO:
    """
    DTO de respuesta de formulario.
    """

    id: int
    formulario_id: int
    usuario_id: int
    datos: Dict[str, Any]
    completado: bool
    created_at: datetime

    def to_dict(self) -> Dict[str, Any]:
        """Convierte a diccionario."""
        return {
            'id': self.id,
            'formulario_id': self.formulario_id,
            'usuario_id': self.usuario_id,
            'datos': self.datos,
            'completado': self.completado,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }


@dataclass
class ExportarDatosFormularioDTO:
    """
    DTO para exportar datos de formulario.
    """

    documento_id: int
    formato: str = 'json'  # json, csv, xfdf
