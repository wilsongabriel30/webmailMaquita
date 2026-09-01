# -*- coding: utf-8 -*-
"""
Entidad Pagina - Representa una página individual de un PDF.
"""

from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List, Tuple


@dataclass
class Pagina:
    """
    Representa una página individual de un documento PDF.

    Attributes:
        numero: Número de página (1-indexed)
        documento_id: ID del documento padre
        ancho: Ancho de la página en puntos (1/72 pulgadas)
        alto: Alto de la página en puntos
        rotacion: Rotación de la página (0, 90, 180, 270)
        contenido_texto: Texto extraído de la página
        tiene_imagenes: Indica si la página contiene imágenes
        tiene_formularios: Indica si la página tiene campos de formulario
        anotaciones_count: Número de anotaciones en la página
    """

    numero: int
    documento_id: int
    ancho: float = 612.0  # Tamaño carta por defecto (8.5 x 11 pulgadas)
    alto: float = 792.0
    rotacion: int = 0
    contenido_texto: Optional[str] = None
    tiene_imagenes: bool = False
    tiene_formularios: bool = False
    anotaciones_count: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        """Validaciones después de inicialización."""
        if self.numero < 1:
            raise ValueError("El número de página debe ser al menos 1")
        if self.rotacion not in (0, 90, 180, 270):
            raise ValueError("La rotación debe ser 0, 90, 180 o 270 grados")

    @property
    def dimensiones(self) -> Tuple[float, float]:
        """Retorna las dimensiones (ancho, alto) considerando la rotación."""
        if self.rotacion in (90, 270):
            return (self.alto, self.ancho)
        return (self.ancho, self.alto)

    @property
    def orientacion(self) -> str:
        """Retorna la orientación de la página."""
        ancho, alto = self.dimensiones
        if ancho > alto:
            return 'horizontal'
        elif alto > ancho:
            return 'vertical'
        return 'cuadrada'

    def rotar(self, grados: int) -> None:
        """
        Rota la página.

        Args:
            grados: Grados a rotar (90, 180, 270 o -90, -180, -270)
        """
        # Normalizar a grados positivos
        grados = grados % 360
        if grados not in (0, 90, 180, 270):
            raise ValueError("La rotación debe ser múltiplo de 90 grados")

        self.rotacion = (self.rotacion + grados) % 360

    def establecer_texto(self, texto: str) -> None:
        """Establece el texto extraído de la página."""
        self.contenido_texto = texto

    def buscar_texto(self, termino: str) -> List[int]:
        """
        Busca un término en el texto de la página.

        Args:
            termino: Texto a buscar

        Returns:
            Lista de posiciones donde se encontró el término
        """
        if not self.contenido_texto:
            return []

        posiciones = []
        texto_lower = self.contenido_texto.lower()
        termino_lower = termino.lower()

        pos = 0
        while True:
            pos = texto_lower.find(termino_lower, pos)
            if pos == -1:
                break
            posiciones.append(pos)
            pos += 1

        return posiciones

    def to_dict(self) -> Dict[str, Any]:
        """Convierte la entidad a diccionario."""
        return {
            'numero': self.numero,
            'documento_id': self.documento_id,
            'ancho': self.ancho,
            'alto': self.alto,
            'rotacion': self.rotacion,
            'tiene_imagenes': self.tiene_imagenes,
            'tiene_formularios': self.tiene_formularios,
            'anotaciones_count': self.anotaciones_count,
            'orientacion': self.orientacion,
            'metadata': self.metadata
        }

    def __repr__(self) -> str:
        return f"Pagina(numero={self.numero}, doc_id={self.documento_id}, {self.ancho}x{self.alto})"
