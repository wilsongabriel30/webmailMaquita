# -*- coding: utf-8 -*-
"""
Modelo SQLAlchemy para Documentos PDF.
"""

from datetime import datetime
from sqlalchemy import Column, Integer, String, BigInteger, Boolean, Text, DateTime
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.declarative import declarative_base

from ....dominio.entidades.documento_pdf import DocumentoPDF
from ....dominio.value_objects.tipos_pdf import EstadoDocumento

from .base_orm import Base


class ModeloDocumentoPDF(Base):
    """
    Modelo SQLAlchemy para la tabla documentos_pdf.
    """

    __tablename__ = 'documentos_pdf'
    __table_args__ = {'schema': 'public'}

    id = Column(Integer, primary_key=True, autoincrement=True)
    usuario_id = Column(Integer, nullable=False, index=True)
    nombre_archivo = Column(String(500), nullable=False)
    nombre_original = Column(String(500))
    ruta_archivo = Column(String(1000), nullable=False)
    tamano_bytes = Column(BigInteger)
    num_paginas = Column(Integer)
    tiene_ocr = Column(Boolean, default=False)
    texto_extraido = Column(Text)
    # 'metadata' es reservado en SQLAlchemy Declarative; el atributo Python
    # se llama 'metadatos' pero la columna en BD sigue siendo 'metadata'
    metadatos = Column('metadata', JSONB, default={})
    permisos = Column(JSONB, default={'publico': False})
    estado = Column(String(50), default='activo', index=True)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    def to_entidad(self) -> DocumentoPDF:
        """
        Convierte el modelo a entidad de dominio.

        Returns:
            Entidad DocumentoPDF
        """
        return DocumentoPDF(
            id=self.id,
            usuario_id=self.usuario_id,
            nombre_archivo=self.nombre_archivo,
            nombre_original=self.nombre_original,
            ruta_archivo=self.ruta_archivo,
            tamano_bytes=self.tamano_bytes,
            num_paginas=self.num_paginas,
            tiene_ocr=self.tiene_ocr,
            texto_extraido=self.texto_extraido,
            metadata=self.metadatos or {},
            permisos=self.permisos or {'publico': False},
            estado=EstadoDocumento(self.estado) if self.estado else EstadoDocumento.ACTIVO,
            created_at=self.created_at,
            updated_at=self.updated_at
        )

    @classmethod
    def from_entidad(cls, entidad: DocumentoPDF) -> 'ModeloDocumentoPDF':
        """
        Crea modelo desde entidad de dominio.

        Args:
            entidad: Entidad DocumentoPDF

        Returns:
            Instancia del modelo
        """
        return cls(
            id=entidad.id,
            usuario_id=entidad.usuario_id,
            nombre_archivo=entidad.nombre_archivo,
            nombre_original=entidad.nombre_original,
            ruta_archivo=entidad.ruta_archivo,
            tamano_bytes=entidad.tamano_bytes,
            num_paginas=entidad.num_paginas,
            tiene_ocr=entidad.tiene_ocr,
            texto_extraido=entidad.texto_extraido,
            metadatos=entidad.metadata,
            permisos=entidad.permisos,
            estado=entidad.estado.value if isinstance(entidad.estado, EstadoDocumento) else entidad.estado,
            created_at=entidad.created_at,
            updated_at=entidad.updated_at
        )

    def actualizar_desde_entidad(self, entidad: DocumentoPDF) -> None:
        """
        Actualiza el modelo con datos de la entidad.

        Args:
            entidad: Entidad con los nuevos datos
        """
        self.nombre_archivo = entidad.nombre_archivo
        self.nombre_original = entidad.nombre_original
        self.ruta_archivo = entidad.ruta_archivo
        self.tamano_bytes = entidad.tamano_bytes
        self.num_paginas = entidad.num_paginas
        self.tiene_ocr = entidad.tiene_ocr
        self.texto_extraido = entidad.texto_extraido
        self.metadatos = entidad.metadata
        self.permisos = entidad.permisos
        self.estado = entidad.estado.value if isinstance(entidad.estado, EstadoDocumento) else entidad.estado
        self.updated_at = datetime.now()

    def __repr__(self) -> str:
        return f"<ModeloDocumentoPDF(id={self.id}, nombre='{self.nombre_original}')>"
