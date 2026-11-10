"""Dibujar páginas de un PDF como imagen para elegir dónde va la firma (09/11/2026).

Pedido: «debo poder seleccionar la hoja y dibujar con el ratón el área donde irá la firma, como
en el editor PDF de Raíces». El navegador no puede dibujar sobre un PDF embebido, así que el
servidor entrega cada página como PNG (pypdfium2, ya instalado) junto con su tamaño en puntos
PDF; el frontend convierte el rectángulo dibujado en píxeles a puntos y Raíces estampa allí.
"""

from __future__ import annotations

import asyncio
import io
from dataclasses import dataclass

import pypdfium2 as pdfium

ANCHO_MINIMO_PX = 200
ANCHO_MAXIMO_PX = 1800
MAX_PAGINAS_PDF = 500


@dataclass
class PaginaDibujada:
    png: bytes
    pagina: int  # 1..n (la realmente dibujada)
    paginas: int  # total del documento
    ancho_pt: float  # tamaño de la página en puntos PDF
    alto_pt: float


def _dibujar(pdf: bytes, pagina: int, ancho_px: int) -> PaginaDibujada:
    doc = pdfium.PdfDocument(pdf)
    try:
        n = len(doc)
        if n < 1:
            raise ValueError("El PDF no tiene páginas")
        if n > MAX_PAGINAS_PDF:
            raise ValueError("El PDF tiene demasiadas páginas para la vista previa")
        if pagina == -1 or pagina > n:
            pagina = n
        if pagina < 1:
            pagina = 1
        hoja = doc[pagina - 1]
        try:
            w_pt, h_pt = hoja.get_size()
            ancho_px = max(ANCHO_MINIMO_PX, min(ANCHO_MAXIMO_PX, int(ancho_px or 900)))
            escala = ancho_px / float(w_pt) if w_pt else 1.0
            imagen = hoja.render(scale=escala, draw_annots=True).to_pil()
        finally:
            hoja.close()
        salida = io.BytesIO()
        imagen.convert("RGB").save(salida, format="PNG", optimize=True)
        return PaginaDibujada(salida.getvalue(), pagina, n, float(w_pt), float(h_pt))
    finally:
        doc.close()


async def dibujar_pagina(
    pdf: bytes, pagina: int = -1, ancho_px: int = 900
) -> PaginaDibujada:
    """Dibuja `pagina` (1..n; -1 = última) con `ancho_px` de ancho. CPU: corre en un hilo aparte."""
    return await asyncio.to_thread(_dibujar, pdf, pagina, ancho_px)
