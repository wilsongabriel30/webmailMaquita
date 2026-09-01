# -*- coding: utf-8 -*-
"""
DTOs para Documentos PDF.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Dict, Any, List


@dataclass
class DocumentoDTO:
    """
    DTO completo de documento PDF.
    """

    id: int
    usuario_id: int
    nombre_archivo: str
    nombre_original: str
    tamano_bytes: int
    num_paginas: int
    tiene_ocr: bool
    metadata: Dict[str, Any]
    permisos: Dict[str, Any]
    estado: str
    created_at: datetime
    updated_at: datetime

    # Campos calculados
    tamano_formateado: str = ''
    puede_editar: bool = False
    puede_firmar: bool = False

    def __post_init__(self):
        """Calcular campos derivados."""
        if self.tamano_bytes:
            self.tamano_formateado = self._formatear_tamano(self.tamano_bytes)

    @staticmethod
    def _formatear_tamano(bytes: int) -> str:
        """Formatea el tamaño en unidades legibles."""
        for unidad in ['B', 'KB', 'MB', 'GB']:
            if bytes < 1024:
                return f"{bytes:.1f} {unidad}"
            bytes /= 1024
        return f"{bytes:.1f} TB"

    @classmethod
    def desde_entidad(cls, entidad, usuario_actual: int = None) -> 'DocumentoDTO':
        """Crea DTO desde entidad de dominio."""
        return cls(
            id=entidad.id,
            usuario_id=entidad.usuario_id,
            nombre_archivo=entidad.nombre_archivo,
            nombre_original=entidad.nombre_original or entidad.nombre_archivo,
            tamano_bytes=entidad.tamano_bytes or 0,
            num_paginas=entidad.num_paginas or 0,
            tiene_ocr=entidad.tiene_ocr,
            metadata=entidad.metadata,
            permisos=entidad.permisos,
            estado=entidad.estado.value if hasattr(entidad.estado, 'value') else entidad.estado,
            created_at=entidad.created_at,
            updated_at=entidad.updated_at,
            puede_editar=entidad.usuario_id == usuario_actual if usuario_actual else False,
            puede_firmar=entidad.usuario_id == usuario_actual if usuario_actual else False
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convierte a diccionario para JSON."""
        return {
            'id': self.id,
            'usuario_id': self.usuario_id,
            'nombre_archivo': self.nombre_archivo,
            'nombre_original': self.nombre_original,
            'tamano_bytes': self.tamano_bytes,
            'tamano_formateado': self.tamano_formateado,
            'num_paginas': self.num_paginas,
            'tiene_ocr': self.tiene_ocr,
            'metadata': self.metadata,
            'estado': self.estado,
            'puede_editar': self.puede_editar,
            'puede_firmar': self.puede_firmar,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }


@dataclass
class DocumentoResumenDTO:
    """
    DTO resumido para listados.
    """

    id: int
    nombre_original: str
    num_paginas: int
    tamano_formateado: str
    tiene_ocr: bool
    created_at: datetime
    thumbnail_url: Optional[str] = None

    @classmethod
    def desde_entidad(cls, entidad, base_url: str = '') -> 'DocumentoResumenDTO':
        """Crea DTO resumido desde entidad."""
        tamano = entidad.tamano_bytes or 0
        for unidad in ['B', 'KB', 'MB', 'GB']:
            if tamano < 1024:
                tamano_str = f"{tamano:.1f} {unidad}"
                break
            tamano /= 1024
        else:
            tamano_str = f"{tamano:.1f} TB"

        return cls(
            id=entidad.id,
            nombre_original=entidad.nombre_original or entidad.nombre_archivo,
            num_paginas=entidad.num_paginas or 0,
            tamano_formateado=tamano_str,
            tiene_ocr=entidad.tiene_ocr,
            created_at=entidad.created_at,
            thumbnail_url=f"{base_url}/api/pdf/documentos/{entidad.id}/thumbnail/1" if base_url else None
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convierte a diccionario."""
        return {
            'id': self.id,
            'nombre_original': self.nombre_original,
            'num_paginas': self.num_paginas,
            'tamano_formateado': self.tamano_formateado,
            'tiene_ocr': self.tiene_ocr,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'thumbnail_url': self.thumbnail_url
        }


@dataclass
class SubirDocumentoDTO:
    """
    DTO para solicitud de subida de documento.
    """

    archivo: Any  # FileStorage de Flask
    usuario_id: int
    nombre_original: Optional[str] = None

    def __post_init__(self):
        """Extraer nombre si no se proporcionó."""
        if not self.nombre_original and hasattr(self.archivo, 'filename'):
            self.nombre_original = self.archivo.filename


@dataclass
class ActualizarDocumentoDTO:
    """
    DTO para actualización de documento.
    """

    id: int
    nombre_original: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    permisos: Optional[Dict[str, Any]] = None
