# -*- coding: utf-8 -*-
"""
Entidad DocumentoPDF - Núcleo del dominio.

Representa un documento PDF con todas sus propiedades y comportamientos.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List, Dict, Any
from uuid import uuid4

from ..value_objects.tipos_pdf import EstadoDocumento


@dataclass
class DocumentoPDF:
    """
    Entidad principal que representa un documento PDF.

    Attributes:
        id: Identificador único del documento
        usuario_id: ID del usuario propietario
        nombre_archivo: Nombre del archivo almacenado (UUID)
        nombre_original: Nombre original del archivo subido
        ruta_archivo: Ruta completa al archivo en disco
        tamano_bytes: Tamaño del archivo en bytes
        num_paginas: Número total de páginas
        tiene_ocr: Indica si se ha aplicado OCR
        texto_extraido: Texto extraído del documento (para búsqueda)
        metadata: Metadatos del PDF (autor, título, fecha creación, etc.)
        permisos: Configuración de permisos (público, compartido, etc.)
        estado: Estado actual del documento
        created_at: Fecha de creación
        updated_at: Fecha de última modificación
    """

    usuario_id: int
    nombre_archivo: str
    ruta_archivo: str
    id: Optional[int] = None
    nombre_original: Optional[str] = None
    tamano_bytes: Optional[int] = None
    num_paginas: Optional[int] = None
    tiene_ocr: bool = False
    texto_extraido: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    permisos: Dict[str, Any] = field(default_factory=lambda: {'publico': False})
    estado: EstadoDocumento = EstadoDocumento.ACTIVO
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    def __post_init__(self):
        """Validaciones después de inicialización."""
        if not self.nombre_archivo:
            raise ValueError("El nombre de archivo es obligatorio")
        if not self.ruta_archivo:
            raise ValueError("La ruta del archivo es obligatoria")
        if self.usuario_id is None or self.usuario_id <= 0:
            raise ValueError("El ID de usuario debe ser válido")

    @classmethod
    def crear_nuevo(
        cls,
        usuario_id: int,
        nombre_original: str,
        ruta_base: str,
        tamano_bytes: int = None
    ) -> 'DocumentoPDF':
        """
        Crea un nuevo documento PDF con nombre único.

        Args:
            usuario_id: ID del usuario propietario
            nombre_original: Nombre original del archivo
            ruta_base: Directorio base para almacenamiento
            tamano_bytes: Tamaño del archivo

        Returns:
            Nueva instancia de DocumentoPDF
        """
        import os

        # Generar nombre único
        extension = os.path.splitext(nombre_original)[1].lower()
        nombre_archivo = f"{uuid4().hex}{extension}"
        ruta_archivo = os.path.join(ruta_base, str(usuario_id), nombre_archivo)

        return cls(
            usuario_id=usuario_id,
            nombre_archivo=nombre_archivo,
            nombre_original=nombre_original,
            ruta_archivo=ruta_archivo,
            tamano_bytes=tamano_bytes
        )

    def actualizar_metadata(self, metadata: Dict[str, Any]) -> None:
        """Actualiza los metadatos del documento."""
        self.metadata.update(metadata)
        self.updated_at = datetime.now()

    def establecer_num_paginas(self, num_paginas: int) -> None:
        """Establece el número de páginas."""
        if num_paginas < 1:
            raise ValueError("El número de páginas debe ser al menos 1")
        self.num_paginas = num_paginas
        self.updated_at = datetime.now()

    def marcar_ocr_aplicado(self, texto: str = None) -> None:
        """Marca el documento como procesado con OCR."""
        self.tiene_ocr = True
        if texto:
            self.texto_extraido = texto
        self.updated_at = datetime.now()

    def establecer_permisos(self, publico: bool = False, usuarios: List[int] = None) -> None:
        """Configura los permisos del documento."""
        self.permisos = {
            'publico': publico,
            'usuarios_permitidos': usuarios or []
        }
        self.updated_at = datetime.now()

    def es_accesible_por(self, usuario_id: int) -> bool:
        """
        Verifica si un usuario puede acceder al documento.

        Args:
            usuario_id: ID del usuario a verificar

        Returns:
            True si el usuario tiene acceso
        """
        if self.usuario_id == usuario_id:
            return True
        if self.permisos.get('publico', False):
            return True
        usuarios_permitidos = self.permisos.get('usuarios_permitidos', [])
        return usuario_id in usuarios_permitidos

    def eliminar(self) -> None:
        """Marca el documento como eliminado (soft delete)."""
        self.estado = EstadoDocumento.ELIMINADO
        self.updated_at = datetime.now()

    def restaurar(self) -> None:
        """Restaura un documento eliminado."""
        if self.estado == EstadoDocumento.ELIMINADO:
            self.estado = EstadoDocumento.ACTIVO
            self.updated_at = datetime.now()

    def to_dict(self) -> Dict[str, Any]:
        """Convierte la entidad a diccionario."""
        return {
            'id': self.id,
            'usuario_id': self.usuario_id,
            'nombre_archivo': self.nombre_archivo,
            'nombre_original': self.nombre_original,
            'ruta_archivo': self.ruta_archivo,
            'tamano_bytes': self.tamano_bytes,
            'num_paginas': self.num_paginas,
            'tiene_ocr': self.tiene_ocr,
            'metadata': self.metadata,
            'permisos': self.permisos,
            'estado': self.estado.value if isinstance(self.estado, EstadoDocumento) else self.estado,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }

    def __repr__(self) -> str:
        return f"DocumentoPDF(id={self.id}, nombre='{self.nombre_original}', paginas={self.num_paginas})"
