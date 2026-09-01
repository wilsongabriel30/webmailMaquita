# -*- coding: utf-8 -*-
"""
Value Objects: Coordenadas y posiciones en PDF.
"""

from dataclasses import dataclass
from typing import Optional, Tuple, Dict, Any


@dataclass(frozen=True)
class Posicion:
    """
    Representa una posición (punto) en una página PDF.

    Las coordenadas están en puntos (1/72 de pulgada).
    El origen (0,0) está en la esquina inferior izquierda.
    """

    x: float
    y: float

    def __post_init__(self):
        """Validaciones."""
        if self.x < 0 or self.y < 0:
            raise ValueError("Las coordenadas no pueden ser negativas")

    def desplazar(self, dx: float, dy: float) -> 'Posicion':
        """Retorna una nueva posición desplazada."""
        return Posicion(x=self.x + dx, y=self.y + dy)

    def escalar(self, factor: float) -> 'Posicion':
        """Retorna una nueva posición escalada."""
        return Posicion(x=self.x * factor, y=self.y * factor)

    def distancia_a(self, otra: 'Posicion') -> float:
        """Calcula la distancia a otra posición."""
        import math
        return math.sqrt((self.x - otra.x) ** 2 + (self.y - otra.y) ** 2)

    def to_dict(self) -> Dict[str, float]:
        """Convierte a diccionario."""
        return {'x': self.x, 'y': self.y}

    def to_tuple(self) -> Tuple[float, float]:
        """Convierte a tupla."""
        return (self.x, self.y)

    @classmethod
    def from_dict(cls, data: Dict[str, float]) -> 'Posicion':
        """Crea desde diccionario."""
        return cls(x=data['x'], y=data['y'])


@dataclass(frozen=True)
class BoundingBox:
    """
    Representa un rectángulo delimitador en una página PDF.

    Attributes:
        x: Coordenada X de la esquina inferior izquierda
        y: Coordenada Y de la esquina inferior izquierda
        ancho: Ancho del rectángulo
        alto: Alto del rectángulo
    """

    x: float
    y: float
    ancho: float
    alto: float

    def __post_init__(self):
        """Validaciones."""
        if self.ancho < 0:
            raise ValueError("El ancho no puede ser negativo")
        if self.alto < 0:
            raise ValueError("El alto no puede ser negativo")

    @property
    def x2(self) -> float:
        """Coordenada X de la esquina superior derecha."""
        return self.x + self.ancho

    @property
    def y2(self) -> float:
        """Coordenada Y de la esquina superior derecha."""
        return self.y + self.alto

    @property
    def centro(self) -> Posicion:
        """Centro del rectángulo."""
        return Posicion(
            x=self.x + self.ancho / 2,
            y=self.y + self.alto / 2
        )

    @property
    def area(self) -> float:
        """Área del rectángulo."""
        return self.ancho * self.alto

    @property
    def esquina_inferior_izquierda(self) -> Posicion:
        """Esquina inferior izquierda."""
        return Posicion(x=self.x, y=self.y)

    @property
    def esquina_superior_derecha(self) -> Posicion:
        """Esquina superior derecha."""
        return Posicion(x=self.x2, y=self.y2)

    def contiene_punto(self, punto: Posicion) -> bool:
        """Verifica si el rectángulo contiene un punto."""
        return (
            self.x <= punto.x <= self.x2 and
            self.y <= punto.y <= self.y2
        )

    def contiene_box(self, otro: 'BoundingBox') -> bool:
        """Verifica si este rectángulo contiene completamente a otro."""
        return (
            self.x <= otro.x and
            self.y <= otro.y and
            self.x2 >= otro.x2 and
            self.y2 >= otro.y2
        )

    def intersecta(self, otro: 'BoundingBox') -> bool:
        """Verifica si hay intersección con otro rectángulo."""
        return not (
            self.x2 < otro.x or
            otro.x2 < self.x or
            self.y2 < otro.y or
            otro.y2 < self.y
        )

    def interseccion(self, otro: 'BoundingBox') -> Optional['BoundingBox']:
        """Retorna la intersección con otro rectángulo, o None si no hay."""
        if not self.intersecta(otro):
            return None

        x = max(self.x, otro.x)
        y = max(self.y, otro.y)
        x2 = min(self.x2, otro.x2)
        y2 = min(self.y2, otro.y2)

        return BoundingBox(
            x=x,
            y=y,
            ancho=x2 - x,
            alto=y2 - y
        )

    def union(self, otro: 'BoundingBox') -> 'BoundingBox':
        """Retorna el rectángulo que contiene ambos."""
        x = min(self.x, otro.x)
        y = min(self.y, otro.y)
        x2 = max(self.x2, otro.x2)
        y2 = max(self.y2, otro.y2)

        return BoundingBox(
            x=x,
            y=y,
            ancho=x2 - x,
            alto=y2 - y
        )

    def expandir(self, margen: float) -> 'BoundingBox':
        """Expande el rectángulo en todas direcciones."""
        return BoundingBox(
            x=self.x - margen,
            y=self.y - margen,
            ancho=self.ancho + 2 * margen,
            alto=self.alto + 2 * margen
        )

    def escalar(self, factor: float) -> 'BoundingBox':
        """Escala el rectángulo manteniendo el centro."""
        nuevo_ancho = self.ancho * factor
        nuevo_alto = self.alto * factor
        dx = (nuevo_ancho - self.ancho) / 2
        dy = (nuevo_alto - self.alto) / 2

        return BoundingBox(
            x=self.x - dx,
            y=self.y - dy,
            ancho=nuevo_ancho,
            alto=nuevo_alto
        )

    def rotar_90(self, ancho_pagina: float, alto_pagina: float) -> 'BoundingBox':
        """Rota el rectángulo 90 grados en el contexto de una página."""
        return BoundingBox(
            x=self.y,
            y=ancho_pagina - self.x - self.ancho,
            ancho=self.alto,
            alto=self.ancho
        )

    def to_dict(self) -> Dict[str, float]:
        """Convierte a diccionario."""
        return {
            'x': self.x,
            'y': self.y,
            'ancho': self.ancho,
            'alto': self.alto
        }

    def to_rect(self) -> Tuple[float, float, float, float]:
        """Convierte a formato rect (x1, y1, x2, y2)."""
        return (self.x, self.y, self.x2, self.y2)

    @classmethod
    def from_dict(cls, data: Dict[str, float]) -> 'BoundingBox':
        """Crea desde diccionario."""
        return cls(
            x=data.get('x', 0),
            y=data.get('y', 0),
            ancho=data.get('ancho', data.get('width', 0)),
            alto=data.get('alto', data.get('height', 0))
        )

    @classmethod
    def from_rect(cls, rect: Tuple[float, float, float, float]) -> 'BoundingBox':
        """Crea desde formato rect (x1, y1, x2, y2)."""
        x1, y1, x2, y2 = rect
        return cls(
            x=min(x1, x2),
            y=min(y1, y2),
            ancho=abs(x2 - x1),
            alto=abs(y2 - y1)
        )

    @classmethod
    def from_puntos(cls, p1: Posicion, p2: Posicion) -> 'BoundingBox':
        """Crea desde dos puntos opuestos."""
        return cls(
            x=min(p1.x, p2.x),
            y=min(p1.y, p2.y),
            ancho=abs(p2.x - p1.x),
            alto=abs(p2.y - p1.y)
        )

    def __repr__(self) -> str:
        return f"BoundingBox({self.x:.1f}, {self.y:.1f}, {self.ancho:.1f}x{self.alto:.1f})"
