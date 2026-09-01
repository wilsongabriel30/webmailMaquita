# -*- coding: utf-8 -*-
"""
Pintar la página: imagen del visor y miniaturas.
================================================

Parte de `ClientePyMuPDF`. Se separó el 29-jul-2026, cuando aquella
clase había llegado a 1.764 líneas y 50 métodos en un solo archivo.

No se usa suelta: `ClientePyMuPDF` hereda de ella, así que desde fuera
se sigue llamando igual que siempre.

Autoría: Equipo de Tecnología Maquita
"""

import io
import logging
import os
import re
from typing import List, Dict, Any, Optional, Tuple

try:
    import fitz  # PyMuPDF
except ImportError:
    fitz = None

from ...dominio.entidades.pagina import Pagina
from ...dominio.excepciones import DocumentoInvalido, PaginaNoEncontrada, RenderError


logger = logging.getLogger(__name__)


# Respuestas de fc-match y fuentes ya cargadas: valen para todo el proceso, las
# fuentes del sistema no cambian mientras el servidor está en pie.
_CACHE_FC_MATCH = {}
_CACHE_FUENTES = {}


class MezclaDibujo(object):
    """Pintar la página: imagen del visor y miniaturas."""

    def renderizar_pagina(
        self,
        ruta_pdf: str,
        pagina: int,
        zoom: float = 1.0,
        formato: str = 'png',
        dpi: int = 150
    ) -> bytes:
        """
        Renderiza una página a imagen.

        Args:
            ruta_pdf: Ruta al archivo PDF
            pagina: Número de página (1-indexed)
            zoom: Factor de zoom (1.0 = 100%)
            formato: Formato de salida (png, jpeg, ppm)
            dpi: Resolución en DPI

        Returns:
            Bytes de la imagen

        Raises:
            PaginaNoEncontrada: Si la página no existe
            RenderError: Si falla el renderizado
        """
        try:
            doc = fitz.open(ruta_pdf)

            if pagina < 1 or pagina > len(doc):
                doc.close()
                raise PaginaNoEncontrada(0, pagina, len(doc))

            page = doc[pagina - 1]

            # Calcular matriz de transformación
            # zoom * dpi/72 para obtener la resolución deseada
            mat = fitz.Matrix(zoom * dpi / 72, zoom * dpi / 72)

            # Renderizar
            pix = page.get_pixmap(matrix=mat, alpha=False)

            # Convertir a bytes
            if formato.lower() == 'png':
                img_bytes = pix.tobytes("png")
            elif formato.lower() in ('jpeg', 'jpg'):
                img_bytes = pix.tobytes("jpeg")
            else:
                img_bytes = pix.tobytes("png")

            doc.close()
            return img_bytes

        except PaginaNoEncontrada:
            raise
        except Exception as e:
            logger.error(f"Error renderizando página {pagina}: {e}")
            raise RenderError(str(e), pagina=pagina)


    def generar_thumbnail(
        self,
        ruta_pdf: str,
        pagina: int,
        ancho: int = 150
    ) -> bytes:
        """
        Genera una miniatura de una página.

        Args:
            ruta_pdf: Ruta al archivo PDF
            pagina: Número de página
            ancho: Ancho de la miniatura en pixels

        Returns:
            Bytes de la imagen PNG
        """
        try:
            doc = fitz.open(ruta_pdf)

            if pagina < 1 or pagina > len(doc):
                doc.close()
                raise PaginaNoEncontrada(0, pagina, len(doc))

            page = doc[pagina - 1]
            rect = page.rect

            # Calcular zoom para obtener el ancho deseado
            zoom = ancho / rect.width
            mat = fitz.Matrix(zoom, zoom)

            pix = page.get_pixmap(matrix=mat, alpha=False)
            img_bytes = pix.tobytes("png")

            doc.close()
            return img_bytes

        except PaginaNoEncontrada:
            raise
        except Exception as e:
            logger.error(f"Error generando thumbnail: {e}")
            raise RenderError(str(e), pagina=pagina)
