# -*- coding: utf-8 -*-
"""
Las anotaciones del usuario, pasadas al PDF de verdad.
======================================================

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


class MezclaAnotaciones(object):
    """Las anotaciones del usuario, pasadas al PDF de verdad."""

    def aplicar_anotaciones_desde_bytes(self, datos_bytes: bytes, anotaciones: list) -> bytes:
        """Aplica anotaciones PDF (highlight, subrayado, tachado, texto, nota, dibujo).

        Coordenadas esperadas en sistema canvas (y=0 arriba), unidades = puntos PDF a zoom 1.
        Se convierten internamente a coordenadas PDF (y=0 abajo).
        """
        try:
            doc = fitz.open(stream=datos_bytes, filetype='pdf')
            for ann in anotaciones:
                pagina_idx = ann.get('pagina', 1) - 1
                if pagina_idx < 0 or pagina_idx >= len(doc):
                    continue
                page = doc[pagina_idx]
                ph = page.rect.height          # altura de la página en puntos
                tipo = ann.get('tipo', '')
                x    = float(ann.get('x', 0))
                y_c  = float(ann.get('y', 0))  # desde arriba (canvas)
                w    = float(ann.get('ancho', 100))
                h    = float(ann.get('alto', 20))
                # conversión Y: canvas-top → PDF-bottom
                y0 = ph - y_c - h   # borde inferior en PDF
                y1 = ph - y_c       # borde superior en PDF
                rect = fitz.Rect(x, y0, x + w, y1)

                if tipo == 'highlight':
                    color = self._hex_a_rgb(ann.get('color', '#FFE500'))
                    a = page.add_highlight_annot(rect)
                    a.set_colors(stroke=color)
                    a.update()

                elif tipo == 'underline':
                    color = self._hex_a_rgb(ann.get('color', '#1473e6'))
                    a = page.add_underline_annot(rect)
                    a.set_colors(stroke=color)
                    a.update()

                elif tipo == 'strikeout':
                    color = self._hex_a_rgb(ann.get('color', '#dc2626'))
                    a = page.add_strikeout_annot(rect)
                    a.set_colors(stroke=color)
                    a.update()

                elif tipo == 'texto':
                    texto  = ann.get('texto', '')
                    tamano = float(ann.get('tamano', 12))
                    color  = self._hex_a_rgb(ann.get('color', '#000000'))
                    # rectángulo mínimo para el texto
                    r = fitz.Rect(x, max(0, y0), x + max(w, 80), min(ph, y1 + max(h, 20)))
                    a = page.add_freetext_annot(
                        rect=r,
                        text=texto,
                        fontsize=tamano,
                        text_color=color,
                        fill_color=(1, 1, 0.9),
                        border_color=(0.7, 0.7, 0.7),
                    )
                    a.update()

                elif tipo == 'nota':
                    texto = ann.get('texto', '')
                    point = fitz.Point(x, ph - y_c)
                    a = page.add_text_annot(point, texto)
                    a.update()

                elif tipo == 'dibujo':
                    trazos_raw = ann.get('trazos', [])
                    if trazos_raw:
                        color  = self._hex_a_rgb(ann.get('color', '#000000'))
                        grosor = float(ann.get('grosor', 2))
                        ink_list = []
                        for trazo in trazos_raw:
                            pts = [fitz.Point(p[0], ph - p[1]) for p in trazo if len(p) >= 2]
                            if pts:
                                ink_list.append(pts)
                        if ink_list:
                            a = page.add_ink_annot(ink_list)
                            a.set_colors(stroke=color)
                            a.set_border(width=grosor)
                            a.update()

            buf = io.BytesIO()
            doc.save(buf, garbage=4, deflate=True)
            doc.close()
            return buf.getvalue()
        except Exception as e:
            logger.error(f"Error aplicando anotaciones: {e}")
            raise DocumentoInvalido(f"Error al aplicar anotaciones: {e}")


    def _hex_a_rgb(self, hex_color: str) -> tuple:
        """Convierte color hex (#RRGGBB) a tupla RGB normalizada (0-1)."""
        hex_color = hex_color.lstrip('#')
        if len(hex_color) == 3:
            hex_color = ''.join(c * 2 for c in hex_color)
        return (
            int(hex_color[0:2], 16) / 255,
            int(hex_color[2:4], 16) / 255,
            int(hex_color[4:6], 16) / 255,
        )
