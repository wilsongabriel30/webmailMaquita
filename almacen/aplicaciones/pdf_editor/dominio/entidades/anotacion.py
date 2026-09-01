# -*- coding: utf-8 -*-
"""
Entidad Anotacion - Representa anotaciones y comentarios en un PDF.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Dict, Any, List

from ..value_objects.tipos_pdf import TipoAnotacion, EstadoAnotacion
from ..value_objects.coordenadas import BoundingBox


@dataclass
class Anotacion:
    """
    Representa una anotación en un documento PDF.

    Attributes:
        documento_id: ID del documento padre
        usuario_id: ID del usuario que creó la anotación
        pagina: Número de página donde está la anotación
        tipo: Tipo de anotación (resaltado, nota, forma, etc.)
        contenido: Contenido de texto de la anotación
        coordenadas: Posición y dimensiones de la anotación
        estilo: Estilos visuales (color, grosor, etc.)
        estado: Estado de la anotación (activo, resuelto, etc.)
    """

    documento_id: int
    usuario_id: int
    pagina: int
    tipo: TipoAnotacion
    coordenadas: Dict[str, Any]
    id: Optional[int] = None
    contenido: Optional[str] = None
    estilo: Dict[str, Any] = field(default_factory=lambda: {
        'color': '#FFFF00',
        'opacidad': 0.5,
        'grosor': 1
    })
    estado: EstadoAnotacion = EstadoAnotacion.ACTIVO
    respuestas: List['Anotacion'] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    def __post_init__(self):
        """Validaciones después de inicialización."""
        if self.pagina < 1:
            raise ValueError("El número de página debe ser al menos 1")
        if not self.coordenadas:
            raise ValueError("Las coordenadas son obligatorias")

    @property
    def bounding_box(self) -> BoundingBox:
        """Retorna el BoundingBox de la anotación."""
        return BoundingBox(
            x=self.coordenadas.get('x', 0),
            y=self.coordenadas.get('y', 0),
            ancho=self.coordenadas.get('ancho', 0),
            alto=self.coordenadas.get('alto', 0)
        )

    def actualizar_contenido(self, contenido: str) -> None:
        """Actualiza el contenido de la anotación."""
        self.contenido = contenido
        self.updated_at = datetime.now()

    def actualizar_estilo(self, estilo: Dict[str, Any]) -> None:
        """Actualiza el estilo de la anotación."""
        self.estilo.update(estilo)
        self.updated_at = datetime.now()

    def mover(self, x: float, y: float) -> None:
        """Mueve la anotación a una nueva posición."""
        self.coordenadas['x'] = x
        self.coordenadas['y'] = y
        self.updated_at = datetime.now()

    def redimensionar(self, ancho: float, alto: float) -> None:
        """Cambia las dimensiones de la anotación."""
        self.coordenadas['ancho'] = ancho
        self.coordenadas['alto'] = alto
        self.updated_at = datetime.now()

    def resolver(self) -> None:
        """Marca la anotación como resuelta."""
        self.estado = EstadoAnotacion.RESUELTO
        self.updated_at = datetime.now()

    def reabrir(self) -> None:
        """Reabre una anotación resuelta."""
        if self.estado == EstadoAnotacion.RESUELTO:
            self.estado = EstadoAnotacion.ACTIVO
            self.updated_at = datetime.now()

    def eliminar(self) -> None:
        """Marca la anotación como eliminada."""
        self.estado = EstadoAnotacion.ELIMINADO
        self.updated_at = datetime.now()

    def agregar_respuesta(self, respuesta: 'Anotacion') -> None:
        """Agrega una respuesta a esta anotación."""
        self.respuestas.append(respuesta)
        self.updated_at = datetime.now()

    def to_dict(self) -> Dict[str, Any]:
        """Convierte la entidad a diccionario."""
        return {
            'id': self.id,
            'documento_id': self.documento_id,
            'usuario_id': self.usuario_id,
            'pagina': self.pagina,
            'tipo': self.tipo.value if isinstance(self.tipo, TipoAnotacion) else self.tipo,
            'contenido': self.contenido,
            'coordenadas': self.coordenadas,
            'estilo': self.estilo,
            'estado': self.estado.value if isinstance(self.estado, EstadoAnotacion) else self.estado,
            'respuestas': [r.to_dict() for r in self.respuestas],
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }

    def __repr__(self) -> str:
        return f"Anotacion(id={self.id}, tipo={self.tipo}, pagina={self.pagina})"


@dataclass
class Comentario:
    """
    Comentario de texto asociado a una anotación o documento.
    """

    usuario_id: int
    texto: str
    anotacion_id: Optional[int] = None
    documento_id: Optional[int] = None
    id: Optional[int] = None
    created_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        """Convierte a diccionario."""
        return {
            'id': self.id,
            'usuario_id': self.usuario_id,
            'texto': self.texto,
            'anotacion_id': self.anotacion_id,
            'documento_id': self.documento_id,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
