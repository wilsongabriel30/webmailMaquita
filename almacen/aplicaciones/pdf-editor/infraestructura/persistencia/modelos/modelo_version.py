# -*- coding: utf-8 -*-
"""
Modelo SQLAlchemy para Versiones de Documento.
"""

from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.declarative import declarative_base

from ....dominio.entidades.version import VersionDocumento

Base = declarative_base()


class ModeloVersionPDF(Base):
    """
    Modelo SQLAlchemy para la tabla versiones_pdf.
    """

    __tablename__ = 'versiones_pdf'
    __table_args__ = (
        UniqueConstraint('documento_id', 'numero_version', name='uq_documento_version'),
        {'schema': 'public'}
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    documento_id = Column(Integer, ForeignKey('documentos_pdf.id', ondelete='CASCADE'), nullable=False, index=True)
    numero_version = Column(Integer, nullable=False)
    ruta_archivo = Column(String(1000), nullable=False)
    usuario_id = Column(Integer, nullable=False)
    descripcion = Column(Text)
    cambios = Column(JSONB, default={})
    created_at = Column(DateTime, default=datetime.now)

    def to_entidad(self) -> VersionDocumento:
        """Convierte a entidad de dominio."""
        return VersionDocumento(
            id=self.id,
            documento_id=self.documento_id,
            numero_version=self.numero_version,
            ruta_archivo=self.ruta_archivo,
            usuario_id=self.usuario_id,
            descripcion=self.descripcion,
            cambios=self.cambios or {},
            created_at=self.created_at
        )

    @classmethod
    def from_entidad(cls, entidad: VersionDocumento) -> 'ModeloVersionPDF':
        """Crea modelo desde entidad."""
        return cls(
            id=entidad.id,
            documento_id=entidad.documento_id,
            numero_version=entidad.numero_version,
            ruta_archivo=entidad.ruta_archivo,
            usuario_id=entidad.usuario_id,
            descripcion=entidad.descripcion,
            cambios=entidad.cambios,
            created_at=entidad.created_at
        )

    def __repr__(self) -> str:
        return f"<ModeloVersionPDF(doc_id={self.documento_id}, v{self.numero_version})>"
