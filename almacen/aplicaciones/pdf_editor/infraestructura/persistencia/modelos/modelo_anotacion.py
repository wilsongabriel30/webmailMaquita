# -*- coding: utf-8 -*-
"""
Modelo SQLAlchemy para Anotaciones PDF.
"""

from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.declarative import declarative_base

from ....dominio.entidades.anotacion import Anotacion
from ....dominio.value_objects.tipos_pdf import TipoAnotacion, EstadoAnotacion

from .base_orm import Base


class ModeloAnotacionPDF(Base):
    """
    Modelo SQLAlchemy para la tabla anotaciones_pdf.
    """

    __tablename__ = 'anotaciones_pdf'
    __table_args__ = {'schema': 'public'}

    id = Column(Integer, primary_key=True, autoincrement=True)
    documento_id = Column(Integer, ForeignKey('public.documentos_pdf.id', ondelete='CASCADE'), nullable=False, index=True)
    usuario_id = Column(Integer, nullable=False, index=True)
    pagina = Column(Integer, nullable=False)
    tipo = Column(String(50), nullable=False)
    contenido = Column(Text)
    coordenadas = Column(JSONB, nullable=False)
    estilo = Column(JSONB, default={})
    estado = Column(String(20), default='activo')
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    def to_entidad(self) -> Anotacion:
        """Convierte a entidad de dominio."""
        return Anotacion(
            id=self.id,
            documento_id=self.documento_id,
            usuario_id=self.usuario_id,
            pagina=self.pagina,
            tipo=TipoAnotacion(self.tipo) if self.tipo in [t.value for t in TipoAnotacion] else self.tipo,
            contenido=self.contenido,
            coordenadas=self.coordenadas or {},
            estilo=self.estilo or {},
            estado=EstadoAnotacion(self.estado) if self.estado else EstadoAnotacion.ACTIVO,
            created_at=self.created_at,
            updated_at=self.updated_at
        )

    @classmethod
    def from_entidad(cls, entidad: Anotacion) -> 'ModeloAnotacionPDF':
        """Crea modelo desde entidad."""
        return cls(
            id=entidad.id,
            documento_id=entidad.documento_id,
            usuario_id=entidad.usuario_id,
            pagina=entidad.pagina,
            tipo=entidad.tipo.value if isinstance(entidad.tipo, TipoAnotacion) else entidad.tipo,
            contenido=entidad.contenido,
            coordenadas=entidad.coordenadas,
            estilo=entidad.estilo,
            estado=entidad.estado.value if isinstance(entidad.estado, EstadoAnotacion) else entidad.estado,
            created_at=entidad.created_at,
            updated_at=entidad.updated_at
        )

    def actualizar_desde_entidad(self, entidad: Anotacion) -> None:
        """Actualiza modelo desde entidad."""
        self.contenido = entidad.contenido
        self.coordenadas = entidad.coordenadas
        self.estilo = entidad.estilo
        self.estado = entidad.estado.value if isinstance(entidad.estado, EstadoAnotacion) else entidad.estado
        self.updated_at = datetime.now()

    def __repr__(self) -> str:
        return f"<ModeloAnotacionPDF(id={self.id}, tipo='{self.tipo}')>"
