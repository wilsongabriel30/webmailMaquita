# -*- coding: utf-8 -*-
"""
Operaciones sobre el documento entero: comprimir, proteger, marca de agua.
==========================================================================

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


class MezclaOperaciones(object):
    """Operaciones sobre el documento entero: comprimir, proteger, marca de agua."""

    def comprimir_desde_bytes(self, datos_bytes: bytes, calidad: str = 'media') -> bytes:
        """Comprime un PDF dado como bytes. calidad: 'alta' | 'media' | 'baja'."""
        try:
            doc = fitz.open(stream=datos_bytes, filetype='pdf')
            opciones = {
                'alta':  dict(garbage=4, deflate=True, clean=True, deflate_images=True, deflate_fonts=True),
                'media': dict(garbage=3, deflate=True, clean=True),
                'baja':  dict(garbage=2, deflate=True),
            }
            params = opciones.get(calidad, opciones['media'])
            buf = io.BytesIO()
            doc.save(buf, **params)
            doc.close()
            return buf.getvalue()
        except Exception as e:
            logger.error(f"Error comprimiendo PDF: {e}")
            raise DocumentoInvalido(f"Error al comprimir: {e}")


    def proteger_con_password(
        self,
        datos_bytes: bytes,
        password: str,
        permisos_impresion: bool = True,
        permisos_copia: bool = False
    ) -> bytes:
        """Protege un PDF con contraseña AES-256."""
        try:
            doc = fitz.open(stream=datos_bytes, filetype='pdf')
            perm = fitz.PDF_PERM_ACCESSIBILITY
            if permisos_impresion:
                perm |= fitz.PDF_PERM_PRINT | fitz.PDF_PERM_PRINT_HQ
            if permisos_copia:
                perm |= fitz.PDF_PERM_COPY
            buf = io.BytesIO()
            doc.save(
                buf,
                encryption=fitz.PDF_ENCRYPT_AES_256,
                user_pw=password,
                owner_pw=password + '_adm',
                permissions=perm
            )
            doc.close()
            return buf.getvalue()
        except Exception as e:
            logger.error(f"Error protegiendo PDF: {e}")
            raise DocumentoInvalido(f"Error al proteger: {e}")


    def agregar_marca_agua(
        self,
        datos_bytes: bytes,
        texto: str,
        opacidad: float = 0.25,
        tamano: float = 60,
        rotacion: float = 45
    ) -> bytes:
        """Agrega marca de agua de texto a todas las páginas."""
        try:
            doc = fitz.open(stream=datos_bytes, filetype='pdf')
            # Color gris claro proporcional a la opacidad
            gray = max(0.2, 1.0 - opacidad * 0.7)
            color = (gray, gray, gray)
            for page in doc:
                rect = page.rect
                centro = fitz.Point(rect.width / 2, rect.height / 2)
                # TextWriter soporta ángulos arbitrarios via morph; insert_text solo 0/90/180/270
                tw = fitz.TextWriter(page.rect, opacity=max(0.05, opacidad), color=color)
                # Estimar ancho del texto para centrarlo antes de rotar
                ancho_aprox = tamano * 0.5 * len(texto)
                punto = fitz.Point(centro.x - ancho_aprox / 2, centro.y)
                tw.append(punto, texto, fontsize=tamano)
                tw.write_text(page, morph=(centro, fitz.Matrix(rotacion)))
            buf = io.BytesIO()
            doc.save(buf, garbage=4, deflate=True)
            doc.close()
            return buf.getvalue()
        except Exception as e:
            logger.error(f"Error agregando marca de agua: {e}")
            raise DocumentoInvalido(f"Error al agregar marca de agua: {e}")


    def agregar_encabezado_pie(
        self,
        datos_bytes: bytes,
        encabezado=None,
        pie=None,
        tamano_fuente: int = 10,
        margen: str = 'normal',
        nombre_archivo: str = ''
    ):
        """Pone encabezado y/o pie de página en todas las páginas.

        `encabezado` y `pie` pueden ser un diccionario con `izquierda`, `centro`
        y `derecha` —tres textos por banda, como en Word— o una cadena suelta,
        que se entiende como el texto de la izquierda.

        El trabajo vive en `encabezado_pie.py`: aquí solo queda la llamada, para
        no engordar este archivo. Devuelve `(pdf, aviso)`.
        """
        from . import encabezado_pie
        try:
            return encabezado_pie.aplicar(
                datos_bytes, encabezado=encabezado, pie=pie,
                tamano=tamano_fuente, margen=margen,
                nombre_archivo=nombre_archivo)
        except ValueError:
            raise
        except Exception as e:
            logger.error(f"Error agregando encabezado/pie: {e}")
            raise DocumentoInvalido(f"Error: {e}")


    def censurar_texto(self, datos_bytes: bytes, terminos: List[str]) -> bytes:
        """Censura (redacta permanentemente) texto específico en todo el documento."""
        try:
            doc = fitz.open(stream=datos_bytes, filetype='pdf')
            for page in doc:
                hay_redacciones = False
                for termino in terminos:
                    if not termino.strip():
                        continue
                    rects = page.search_for(termino.strip())
                    for rect in rects:
                        page.add_redact_annot(rect, fill=(0, 0, 0))
                        hay_redacciones = True
                if hay_redacciones:
                    page.apply_redactions()
            buf = io.BytesIO()
            doc.save(buf, garbage=4, deflate=True)
            doc.close()
            return buf.getvalue()
        except Exception as e:
            logger.error(f"Error censurando PDF: {e}")
            raise DocumentoInvalido(f"Error al censurar: {e}")
