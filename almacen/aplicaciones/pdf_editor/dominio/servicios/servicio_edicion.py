# -*- coding: utf-8 -*-
"""
Servicio de Dominio: Edición de contenido PDF.

Define la lógica de negocio para edición de texto e imágenes.
"""

from dataclasses import dataclass
from typing import List, Dict, Any, Optional

from ..value_objects.coordenadas import BoundingBox


@dataclass
class ElementoTexto:
    """Representa un elemento de texto en una página."""

    texto: str
    bbox: BoundingBox
    fuente: str
    tamano: float
    color: str
    pagina: int
    indice: int = 0

    def contiene_punto(self, x: float, y: float) -> bool:
        """Verifica si el punto está dentro del elemento."""
        from ..value_objects.coordenadas import Posicion
        return self.bbox.contiene_punto(Posicion(x=x, y=y))


@dataclass
class ElementoImagen:
    """Representa una imagen en una página."""

    bbox: BoundingBox
    formato: str  # png, jpeg, etc
    ancho_original: int
    alto_original: int
    pagina: int
    indice: int = 0
    datos: Optional[bytes] = None


class ServicioEdicion:
    """
    Servicio de dominio para lógica de edición.
    """

    @staticmethod
    def validar_edicion_texto(
        texto_original: str,
        texto_nuevo: str,
        max_longitud: int = 10000
    ) -> tuple[bool, Optional[str]]:
        """
        Valida una edición de texto.

        Args:
            texto_original: Texto original
            texto_nuevo: Nuevo texto
            max_longitud: Longitud máxima permitida

        Returns:
            Tupla (es_valido, mensaje_error)
        """
        if not texto_nuevo:
            return False, "El texto no puede estar vacío"

        if len(texto_nuevo) > max_longitud:
            return False, f"El texto excede el máximo de {max_longitud} caracteres"

        # Verificar caracteres no imprimibles problemáticos
        caracteres_problematicos = ['\x00', '\x0b', '\x0c']
        for char in caracteres_problematicos:
            if char in texto_nuevo:
                return False, "El texto contiene caracteres no válidos"

        return True, None

    @staticmethod
    def calcular_ajuste_bbox(
        bbox_original: BoundingBox,
        texto_original: str,
        texto_nuevo: str,
        caracteres_por_punto: float = 0.6
    ) -> BoundingBox:
        """
        Calcula el nuevo bounding box después de editar texto.

        Args:
            bbox_original: Área original del texto
            texto_original: Texto original
            texto_nuevo: Nuevo texto
            caracteres_por_punto: Aproximación de caracteres por punto

        Returns:
            Nuevo bounding box estimado
        """
        if not texto_original:
            return bbox_original

        # Calcular ratio de cambio de longitud
        ratio = len(texto_nuevo) / len(texto_original)

        # Ajustar ancho proporcionalmente (simplificación)
        nuevo_ancho = bbox_original.ancho * min(ratio, 2.0)  # Limitar expansión

        return BoundingBox(
            x=bbox_original.x,
            y=bbox_original.y,
            ancho=nuevo_ancho,
            alto=bbox_original.alto
        )

    @staticmethod
    def encontrar_elementos_en_area(
        elementos: List[ElementoTexto],
        area: BoundingBox
    ) -> List[ElementoTexto]:
        """
        Encuentra elementos de texto dentro de un área.

        Args:
            elementos: Lista de elementos de texto
            area: Área de búsqueda

        Returns:
            Elementos que intersectan con el área
        """
        return [e for e in elementos if area.intersecta(e.bbox)]

    @staticmethod
    def calcular_posicion_marca_agua(
        ancho_pagina: float,
        alto_pagina: float,
        ancho_marca: float,
        alto_marca: float,
        posicion: str = 'centro'
    ) -> tuple[float, float]:
        """
        Calcula la posición de una marca de agua.

        Args:
            ancho_pagina: Ancho de la página
            alto_pagina: Alto de la página
            ancho_marca: Ancho de la marca de agua
            alto_marca: Alto de la marca de agua
            posicion: centro, esquina_superior_izquierda, etc.

        Returns:
            Tupla (x, y) de posición
        """
        posiciones = {
            'centro': (
                (ancho_pagina - ancho_marca) / 2,
                (alto_pagina - alto_marca) / 2
            ),
            'superior_izquierda': (20, alto_pagina - alto_marca - 20),
            'superior_derecha': (ancho_pagina - ancho_marca - 20, alto_pagina - alto_marca - 20),
            'inferior_izquierda': (20, 20),
            'inferior_derecha': (ancho_pagina - ancho_marca - 20, 20),
        }

        return posiciones.get(posicion, posiciones['centro'])

    @staticmethod
    def generar_texto_encabezado(
        plantilla: str,
        pagina_actual: int,
        total_paginas: int,
        metadata: Dict[str, Any] = None
    ) -> str:
        """
        Genera texto de encabezado/pie de página.

        Args:
            plantilla: Plantilla con marcadores ({pagina}, {total}, {fecha}, {titulo})
            pagina_actual: Número de página actual
            total_paginas: Total de páginas
            metadata: Metadatos del documento

        Returns:
            Texto formateado
        """
        from datetime import datetime

        metadata = metadata or {}

        texto = plantilla.replace('{pagina}', str(pagina_actual))
        texto = texto.replace('{total}', str(total_paginas))
        texto = texto.replace('{fecha}', datetime.now().strftime('%d/%m/%Y'))
        texto = texto.replace('{titulo}', metadata.get('title', ''))
        texto = texto.replace('{autor}', metadata.get('author', ''))

        return texto
