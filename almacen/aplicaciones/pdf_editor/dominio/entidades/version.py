# -*- coding: utf-8 -*-
"""
Entidad Version - Control de versiones de documentos PDF.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Dict, Any, List


@dataclass
class VersionDocumento:
    """
    Representa una versión de un documento PDF.

    Attributes:
        documento_id: ID del documento original
        numero_version: Número secuencial de la versión
        ruta_archivo: Ruta al archivo de esta versión
        usuario_id: ID del usuario que creó la versión
        descripcion: Descripción de los cambios
        cambios: Detalle de los cambios realizados
    """

    documento_id: int
    numero_version: int
    ruta_archivo: str
    usuario_id: int
    descripcion: Optional[str] = None
    cambios: Dict[str, Any] = field(default_factory=dict)
    id: Optional[int] = None
    created_at: datetime = field(default_factory=datetime.now)

    def __post_init__(self):
        """Validaciones después de inicialización."""
        if self.numero_version < 1:
            raise ValueError("El número de versión debe ser al menos 1")
        if not self.ruta_archivo:
            raise ValueError("La ruta del archivo es obligatoria")

    @classmethod
    def crear_nueva(
        cls,
        documento_id: int,
        version_anterior: int,
        ruta_archivo: str,
        usuario_id: int,
        descripcion: str = None,
        cambios: Dict[str, Any] = None
    ) -> 'VersionDocumento':
        """
        Crea una nueva versión incrementando el número.

        Args:
            documento_id: ID del documento
            version_anterior: Número de la versión anterior
            ruta_archivo: Ruta al nuevo archivo
            usuario_id: Usuario que crea la versión
            descripcion: Descripción de los cambios
            cambios: Detalle de cambios

        Returns:
            Nueva instancia de VersionDocumento
        """
        return cls(
            documento_id=documento_id,
            numero_version=version_anterior + 1,
            ruta_archivo=ruta_archivo,
            usuario_id=usuario_id,
            descripcion=descripcion,
            cambios=cambios or {}
        )

    def registrar_cambio(self, tipo: str, detalle: Any) -> None:
        """
        Registra un cambio en esta versión.

        Args:
            tipo: Tipo de cambio (paginas_eliminadas, anotaciones_agregadas, etc.)
            detalle: Detalle del cambio
        """
        if tipo not in self.cambios:
            self.cambios[tipo] = []

        if isinstance(self.cambios[tipo], list):
            self.cambios[tipo].append(detalle)
        else:
            self.cambios[tipo] = [self.cambios[tipo], detalle]

    def obtener_resumen_cambios(self) -> str:
        """Obtiene un resumen textual de los cambios."""
        if not self.cambios:
            return "Sin cambios registrados"

        resumen = []
        for tipo, detalles in self.cambios.items():
            if isinstance(detalles, list):
                resumen.append(f"- {tipo}: {len(detalles)} elemento(s)")
            else:
                resumen.append(f"- {tipo}: {detalles}")

        return "\n".join(resumen)

    def to_dict(self) -> Dict[str, Any]:
        """Convierte a diccionario."""
        return {
            'id': self.id,
            'documento_id': self.documento_id,
            'numero_version': self.numero_version,
            'ruta_archivo': self.ruta_archivo,
            'usuario_id': self.usuario_id,
            'descripcion': self.descripcion,
            'cambios': self.cambios,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }

    def __repr__(self) -> str:
        return f"VersionDocumento(doc_id={self.documento_id}, v{self.numero_version})"


@dataclass
class HistorialCambios:
    """
    Agrupa el historial completo de versiones de un documento.
    """

    documento_id: int
    versiones: List[VersionDocumento] = field(default_factory=list)

    def agregar_version(self, version: VersionDocumento) -> None:
        """Agrega una versión al historial."""
        self.versiones.append(version)
        self.versiones.sort(key=lambda v: v.numero_version)

    def obtener_version(self, numero: int) -> Optional[VersionDocumento]:
        """Obtiene una versión específica."""
        for v in self.versiones:
            if v.numero_version == numero:
                return v
        return None

    @property
    def version_actual(self) -> Optional[VersionDocumento]:
        """Retorna la versión más reciente."""
        if self.versiones:
            return self.versiones[-1]
        return None

    @property
    def total_versiones(self) -> int:
        """Retorna el número total de versiones."""
        return len(self.versiones)

    def to_dict(self) -> Dict[str, Any]:
        """Convierte a diccionario."""
        return {
            'documento_id': self.documento_id,
            'total_versiones': self.total_versiones,
            'versiones': [v.to_dict() for v in self.versiones]
        }
