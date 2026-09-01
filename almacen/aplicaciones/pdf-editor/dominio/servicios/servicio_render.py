# -*- coding: utf-8 -*-
"""
Servicio de Dominio: Renderizado de páginas PDF.

Define la lógica de negocio para el renderizado,
sin depender de implementaciones específicas.
"""

from dataclasses import dataclass
from typing import Optional, Tuple

from ..value_objects.tipos_pdf import CalidadRenderizado, DPI_POR_CALIDAD


@dataclass
class ConfiguracionRender:
    """Configuración para renderizado de páginas."""

    calidad: CalidadRenderizado = CalidadRenderizado.MEDIA
    formato: str = 'png'  # png, jpeg, svg
    fondo_transparente: bool = False
    escala: float = 1.0

    @property
    def dpi(self) -> int:
        """Obtiene los DPI según la calidad."""
        return DPI_POR_CALIDAD.get(self.calidad, 150)

    @property
    def factor_escala(self) -> float:
        """Factor de escala combinando DPI y escala manual."""
        return (self.dpi / 72.0) * self.escala

    def calcular_dimensiones(
        self,
        ancho_pagina: float,
        alto_pagina: float
    ) -> Tuple[int, int]:
        """
        Calcula las dimensiones de la imagen resultante.

        Args:
            ancho_pagina: Ancho de la página en puntos
            alto_pagina: Alto de la página en puntos

        Returns:
            Tupla (ancho_pixels, alto_pixels)
        """
        factor = self.factor_escala
        return (
            int(ancho_pagina * factor),
            int(alto_pagina * factor)
        )


class ServicioRender:
    """
    Servicio de dominio para lógica de renderizado.

    Este servicio contiene la lógica de negocio relacionada con
    el renderizado de páginas, sin implementar el renderizado real.
    """

    @staticmethod
    def calcular_configuracion_optima(
        ancho_contenedor: int,
        alto_contenedor: int,
        ancho_pagina: float,
        alto_pagina: float,
        max_dpi: int = 300
    ) -> ConfiguracionRender:
        """
        Calcula la configuración óptima de renderizado.

        Args:
            ancho_contenedor: Ancho del contenedor en pixels
            alto_contenedor: Alto del contenedor en pixels
            ancho_pagina: Ancho de la página en puntos
            alto_pagina: Alto de la página en puntos
            max_dpi: DPI máximo permitido

        Returns:
            Configuración óptima de renderizado
        """
        # Calcular el factor de escala necesario
        escala_ancho = ancho_contenedor / ancho_pagina
        escala_alto = alto_contenedor / alto_pagina
        escala = min(escala_ancho, escala_alto)

        # Convertir a DPI equivalente
        dpi_necesario = int(escala * 72)

        # Determinar calidad
        if dpi_necesario <= 72:
            calidad = CalidadRenderizado.BAJA
        elif dpi_necesario <= 150:
            calidad = CalidadRenderizado.MEDIA
        elif dpi_necesario <= 300:
            calidad = CalidadRenderizado.ALTA
        else:
            calidad = CalidadRenderizado.MAXIMA

        return ConfiguracionRender(
            calidad=calidad,
            escala=min(escala, max_dpi / 72.0)
        )

    @staticmethod
    def calcular_zoom(
        zoom_actual: float,
        delta: float,
        min_zoom: float = 0.25,
        max_zoom: float = 4.0
    ) -> float:
        """
        Calcula el nuevo nivel de zoom.

        Args:
            zoom_actual: Zoom actual (1.0 = 100%)
            delta: Cambio de zoom (+/-)
            min_zoom: Zoom mínimo (0.25 = 25%)
            max_zoom: Zoom máximo (4.0 = 400%)

        Returns:
            Nuevo nivel de zoom
        """
        nuevo_zoom = zoom_actual + delta
        return max(min_zoom, min(max_zoom, nuevo_zoom))

    @staticmethod
    def calcular_posicion_centrada(
        ancho_contenedor: int,
        alto_contenedor: int,
        ancho_pagina: int,
        alto_pagina: int
    ) -> Tuple[int, int]:
        """
        Calcula la posición para centrar una página.

        Args:
            ancho_contenedor: Ancho del contenedor
            alto_contenedor: Alto del contenedor
            ancho_pagina: Ancho de la página renderizada
            alto_pagina: Alto de la página renderizada

        Returns:
            Tupla (x, y) para centrar la página
        """
        x = max(0, (ancho_contenedor - ancho_pagina) // 2)
        y = max(0, (alto_contenedor - alto_pagina) // 2)
        return (x, y)

    @staticmethod
    def es_calidad_suficiente(
        dpi_actual: int,
        zoom: float
    ) -> bool:
        """
        Determina si la calidad actual es suficiente para el zoom.

        Args:
            dpi_actual: DPI del renderizado actual
            zoom: Nivel de zoom actual

        Returns:
            True si la calidad es suficiente
        """
        # Se considera suficiente si el DPI efectivo es >= 100
        dpi_efectivo = dpi_actual / zoom
        return dpi_efectivo >= 100
