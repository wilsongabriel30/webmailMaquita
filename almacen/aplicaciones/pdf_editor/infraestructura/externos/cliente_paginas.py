# -*- coding: utf-8 -*-
"""
Las páginas: girar, quitar, reordenar y combinar.
=================================================

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


class MezclaPaginas(object):
    """Las páginas: girar, quitar, reordenar y combinar."""

    def obtener_info(self, ruta_pdf: str) -> Dict[str, Any]:
        """
        Obtiene información básica del PDF.

        Args:
            ruta_pdf: Ruta al archivo PDF

        Returns:
            Diccionario con información del PDF

        Raises:
            DocumentoInvalido: Si no se puede abrir el PDF
        """
        try:
            doc = fitz.open(ruta_pdf)

            info = {
                'num_paginas': len(doc),
                'metadata': {
                    'title': doc.metadata.get('title', ''),
                    'author': doc.metadata.get('author', ''),
                    'subject': doc.metadata.get('subject', ''),
                    'keywords': doc.metadata.get('keywords', ''),
                    'creator': doc.metadata.get('creator', ''),
                    'producer': doc.metadata.get('producer', ''),
                    'creationDate': doc.metadata.get('creationDate', ''),
                    'modDate': doc.metadata.get('modDate', ''),
                },
                'es_encriptado': doc.is_encrypted,
                'necesita_password': doc.needs_pass,
                'permite_impresion': doc.permissions & fitz.PDF_PERM_PRINT > 0 if doc.permissions else True,
                'permite_copia': doc.permissions & fitz.PDF_PERM_COPY > 0 if doc.permissions else True,
            }

            # Información de la primera página
            if len(doc) > 0:
                pagina = doc[0]
                rect = pagina.rect
                info['ancho_primera_pagina'] = rect.width
                info['alto_primera_pagina'] = rect.height

            doc.close()
            return info

        except Exception as e:
            logger.error(f"Error obteniendo info de PDF: {e}")
            raise DocumentoInvalido(str(e), razon=str(e))


    def obtener_paginas(self, ruta_pdf: str) -> List[Pagina]:
        """
        Obtiene información de todas las páginas.

        Args:
            ruta_pdf: Ruta al archivo PDF

        Returns:
            Lista de entidades Pagina
        """
        try:
            doc = fitz.open(ruta_pdf)
            paginas = []

            for i, page in enumerate(doc):
                rect = page.rect
                pagina = Pagina(
                    numero=i + 1,
                    documento_id=0,  # Se asignará después
                    ancho=rect.width,
                    alto=rect.height,
                    rotacion=page.rotation,
                    tiene_imagenes=len(page.get_images()) > 0,
                    # page.widgets() devuelve un generador en PyMuPDF moderno: no admite len()
                    tiene_formularios=any(True for _ in page.widgets()) if hasattr(page, 'widgets') else False
                )
                paginas.append(pagina)

            doc.close()
            return paginas

        except Exception as e:
            logger.error(f"Error obteniendo páginas: {e}")
            raise DocumentoInvalido(str(e))


    def rotar_pagina(
        self,
        ruta_pdf: str,
        pagina: int,
        grados: int
    ) -> None:
        """
        Rota una página del PDF.

        Args:
            ruta_pdf: Ruta al archivo PDF
            pagina: Número de página
            grados: Grados a rotar (90, 180, 270)
        """
        try:
            doc = fitz.open(ruta_pdf)

            if pagina < 1 or pagina > len(doc):
                doc.close()
                raise PaginaNoEncontrada(0, pagina, len(doc))

            page = doc[pagina - 1]
            page.set_rotation(page.rotation + grados)

            doc.save(ruta_pdf, incremental=True, encryption=fitz.PDF_ENCRYPT_KEEP)
            doc.close()

        except PaginaNoEncontrada:
            raise
        except Exception as e:
            logger.error(f"Error rotando página: {e}")
            raise DocumentoInvalido(f"Error al rotar: {e}")


    def eliminar_pagina(
        self,
        ruta_pdf: str,
        pagina: int
    ) -> None:
        """
        Elimina una página del PDF.

        Args:
            ruta_pdf: Ruta al archivo PDF
            pagina: Número de página a eliminar
        """
        try:
            doc = fitz.open(ruta_pdf)

            if pagina < 1 or pagina > len(doc):
                doc.close()
                raise PaginaNoEncontrada(0, pagina, len(doc))

            if len(doc) <= 1:
                doc.close()
                raise DocumentoInvalido("No se puede eliminar la única página")

            doc.delete_page(pagina - 1)
            # PyMuPDF no permite guardar con garbage sobre el mismo archivo abierto:
            # se guarda a un temporal y se reemplaza de forma atomica
            ruta_tmp = ruta_pdf + '.tmp'
            doc.save(ruta_tmp, garbage=4, deflate=True)
            doc.close()
            os.replace(ruta_tmp, ruta_pdf)

        except (PaginaNoEncontrada, DocumentoInvalido):
            raise
        except Exception as e:
            logger.error(f"Error eliminando página: {e}")
            raise DocumentoInvalido(f"Error al eliminar: {e}")


    def reordenar_paginas(
        self,
        ruta_pdf: str,
        orden: List[int]
    ) -> None:
        """
        Reordena las páginas del PDF.

        Args:
            ruta_pdf: Ruta al archivo PDF
            orden: Nuevo orden (lista de números de página originales)
        """
        try:
            doc = fitz.open(ruta_pdf)

            if len(orden) != len(doc):
                doc.close()
                raise DocumentoInvalido(
                    f"El orden debe tener {len(doc)} páginas, tiene {len(orden)}"
                )

            # Convertir a índices 0-based
            orden_0 = [p - 1 for p in orden]

            # Verificar que todos los índices son válidos
            for idx in orden_0:
                if idx < 0 or idx >= len(doc):
                    doc.close()
                    raise DocumentoInvalido(f"Índice de página inválido: {idx + 1}")

            # Crear nuevo documento con el orden correcto
            nuevo_doc = fitz.open()
            for idx in orden_0:
                nuevo_doc.insert_pdf(doc, from_page=idx, to_page=idx)

            nuevo_doc.save(ruta_pdf, garbage=4, deflate=True)
            nuevo_doc.close()
            doc.close()

        except DocumentoInvalido:
            raise
        except Exception as e:
            logger.error(f"Error reordenando páginas: {e}")
            raise DocumentoInvalido(f"Error al reordenar: {e}")


    def extraer_paginas(
        self,
        ruta_pdf: str,
        paginas: List[int]
    ) -> bytes:
        """
        Extrae páginas específicas a un nuevo PDF.

        Args:
            ruta_pdf: Ruta al archivo PDF original
            paginas: Lista de páginas a extraer (1-indexed)

        Returns:
            Bytes del nuevo PDF
        """
        try:
            doc = fitz.open(ruta_pdf)

            # Validar páginas
            for p in paginas:
                if p < 1 or p > len(doc):
                    doc.close()
                    raise PaginaNoEncontrada(0, p, len(doc))

            # Crear nuevo documento
            nuevo_doc = fitz.open()
            for p in paginas:
                nuevo_doc.insert_pdf(doc, from_page=p - 1, to_page=p - 1)

            # Obtener bytes
            buffer = io.BytesIO()
            nuevo_doc.save(buffer, garbage=4, deflate=True)
            bytes_pdf = buffer.getvalue()

            nuevo_doc.close()
            doc.close()

            return bytes_pdf

        except PaginaNoEncontrada:
            raise
        except Exception as e:
            logger.error(f"Error extrayendo páginas: {e}")
            raise DocumentoInvalido(f"Error al extraer: {e}")


    def insertar_pagina_blanca(
        self,
        ruta_pdf: str,
        posicion: int,
        ancho: float = 612,
        alto: float = 792
    ) -> None:
        """
        Inserta una página en blanco.

        Args:
            ruta_pdf: Ruta al archivo PDF
            posicion: Posición donde insertar (1-indexed)
            ancho: Ancho de la página en puntos
            alto: Alto de la página en puntos
        """
        try:
            doc = fitz.open(ruta_pdf)

            if posicion < 1:
                posicion = 1
            if posicion > len(doc) + 1:
                posicion = len(doc) + 1

            doc.new_page(pno=posicion - 1, width=ancho, height=alto)
            doc.save(ruta_pdf, incremental=True, encryption=fitz.PDF_ENCRYPT_KEEP)
            doc.close()

        except Exception as e:
            logger.error(f"Error insertando página: {e}")
            raise DocumentoInvalido(f"Error al insertar: {e}")


    def combinar_pdfs(self, rutas: List[str]) -> bytes:
        """
        Combina múltiples PDFs en uno.

        Args:
            rutas: Lista de rutas a los PDFs

        Returns:
            Bytes del PDF combinado
        """
        try:
            resultado = fitz.open()

            for ruta in rutas:
                doc = fitz.open(ruta)
                resultado.insert_pdf(doc)
                doc.close()

            buffer = io.BytesIO()
            resultado.save(buffer, garbage=4, deflate=True)
            bytes_pdf = buffer.getvalue()

            resultado.close()
            return bytes_pdf

        except Exception as e:
            logger.error(f"Error combinando PDFs: {e}")
            raise DocumentoInvalido(f"Error al combinar: {e}")


    def extraer_paginas_desde_bytes(self, datos_bytes: bytes, paginas: List[int]) -> bytes:
        """Extrae páginas específicas de un PDF en bytes. paginas es 1-indexed."""
        try:
            doc = fitz.open(stream=datos_bytes, filetype='pdf')
            total = len(doc)
            for p in paginas:
                if p < 1 or p > total:
                    doc.close()
                    raise DocumentoInvalido(f"Página {p} no existe (total: {total})")
            nuevo = fitz.open()
            for p in paginas:
                nuevo.insert_pdf(doc, from_page=p - 1, to_page=p - 1)
            buf = io.BytesIO()
            nuevo.save(buf, garbage=4, deflate=True)
            nuevo.close()
            doc.close()
            return buf.getvalue()
        except DocumentoInvalido:
            raise
        except Exception as e:
            logger.error(f"Error extrayendo páginas: {e}")
            raise DocumentoInvalido(f"Error al extraer: {e}")
