# -*- coding: utf-8 -*-
"""
Leer y buscar texto, con reconocimiento si hace falta.
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

# Los idiomas de tesseract, preguntados una sola vez: instalar uno nuevo requiere
# reiniciar el servicio, así que la lista no cambia mientras el proceso está en pie.
_CACHE_IDIOMAS = None


def _idiomas_instalados():
    """Los idiomas que tesseract tiene instalados en ESTE servidor."""
    global _CACHE_IDIOMAS
    if _CACHE_IDIOMAS is None:
        try:
            import subprocess
            salida = subprocess.run(['tesseract', '--list-langs'],
                                    capture_output=True, text=True, timeout=10).stdout
            _CACHE_IDIOMAS = {l.strip() for l in salida.split('\n')[1:] if l.strip()}
        except Exception:
            _CACHE_IDIOMAS = {'spa', 'eng'}
    return _CACHE_IDIOMAS


def _idioma_disponible(idioma):
    """El código de idioma para tesseract, comprobando que esté instalado.

    Si el que se pide no está, se reconoce con español+inglés y se DEJA DICHO en el
    registro: un reconocimiento en el idioma equivocado sale mal y, sin este aviso,
    nadie entiende por qué.
    """
    equivalencias = {'es': 'spa', 'en': 'eng', 'pt': 'por'}
    pedido = equivalencias.get((idioma or '').strip().lower(), (idioma or 'spa').strip().lower())
    instalados = _idiomas_instalados()
    if pedido in instalados:
        return pedido
    respaldo = '+'.join(sorted(x for x in ('spa', 'eng') if x in instalados)) or 'eng'
    logger.warning('El idioma %r no está instalado en el servidor (hay: %s). Se reconoce '
                   'con %s.', pedido, ', '.join(sorted(instalados)), respaldo)
    return respaldo




# Respuestas de fc-match y fuentes ya cargadas: valen para todo el proceso, las
# fuentes del sistema no cambian mientras el servidor está en pie.
_CACHE_FC_MATCH = {}
_CACHE_FUENTES = {}


from . import ocr_fusion
from . import ocr_lote
from . import texto_parrafos


class MezclaTexto(object):
    """Leer y buscar texto, con reconocimiento si hace falta."""

    def extraer_texto(
        self,
        ruta_pdf: str,
        pagina: int = None
    ) -> str:
        """
        Extrae texto del PDF.

        Args:
            ruta_pdf: Ruta al archivo PDF
            pagina: Número de página (None = todas)

        Returns:
            Texto extraído
        """
        try:
            doc = fitz.open(ruta_pdf)
            texto = []

            if pagina:
                if pagina < 1 or pagina > len(doc):
                    doc.close()
                    raise PaginaNoEncontrada(0, pagina, len(doc))
                texto.append(doc[pagina - 1].get_text())
            else:
                for page in doc:
                    texto.append(page.get_text())

            doc.close()
            return "\n".join(texto)

        except PaginaNoEncontrada:
            raise
        except Exception as e:
            logger.error(f"Error extrayendo texto: {e}")
            return ""


    def buscar_texto(
        self,
        ruta_pdf: str,
        termino: str,
        pagina: int = None
    ) -> List[Dict[str, Any]]:
        """
        Busca texto en el documento.

        Args:
            ruta_pdf: Ruta al archivo PDF
            termino: Término a buscar
            pagina: Página específica (None = todas)

        Returns:
            Lista de resultados con posiciones
        """
        try:
            doc = fitz.open(ruta_pdf)
            resultados = []

            paginas_buscar = range(len(doc))
            if pagina:
                if pagina < 1 or pagina > len(doc):
                    doc.close()
                    return []
                paginas_buscar = [pagina - 1]

            for pno in paginas_buscar:
                page = doc[pno]
                rects = page.search_for(termino)

                for rect in rects:
                    resultados.append({
                        'pagina': pno + 1,
                        'x': rect.x0,
                        'y': rect.y0,
                        'ancho': rect.width,
                        'alto': rect.height,
                        'texto': termino
                    })

            doc.close()
            return resultados

        except Exception as e:
            logger.error(f"Error buscando texto: {e}")
            return []


    def buscar_en_bytes(self, datos_bytes: bytes, termino: str) -> List[Dict[str, Any]]:
        """Busca texto en un PDF dado como bytes. Retorna lista de ubicaciones."""
        try:
            doc = fitz.open(stream=datos_bytes, filetype='pdf')
            resultados = []
            for pno in range(len(doc)):
                rects = doc[pno].search_for(termino)
                for rect in rects:
                    resultados.append({
                        'pagina': pno + 1,
                        'x': round(rect.x0, 1),
                        'y': round(rect.y0, 1),
                        'ancho': round(rect.width, 1),
                        'alto': round(rect.height, 1)
                    })
            doc.close()
            return resultados
        except Exception as e:
            logger.error(f"Error buscando en bytes: {e}")
            return []


    def extraer_texto_desde_bytes(self, datos_bytes: bytes, pagina: int = None,
                                  idioma: str = 'spa', forzar_ocr: bool = False) -> Dict[str, Any]:
        """
        Extrae texto de un PDF. Primero intenta texto incrustado (get_text) y aplica
        OCR real con Tesseract cuando la pagina no tiene texto, tiene muy poco, o es
        un escaneado metido dentro de un PDF digital (poco texto + imagen grande).
        Con forzar_ocr=True se hace OCR de todas las paginas pedidas sin heuristica.
        """
        try:
            doc = fitz.open(stream=datos_bytes, filetype='pdf')
            rangos = [pagina - 1] if pagina else range(len(doc))
            paginas_info = []
            uso_ocr = False

            # Primera pasada, barata: el texto que ya trae cada hoja y cuales hay que
            # pasar por tesseract. Se miran TODAS antes de reconocer ninguna, para
            # poder repartir esas hojas entre varios procesos (`ocr_lote`) en vez de
            # irlas haciendo de una en una con el usuario esperando delante.
            incrustado = {}
            pendientes = []
            # El mismo texto, ya recompuesto por párrafos (ver `texto_parrafos`).
            por_parrafos = {}
            for pno in rangos:
                if 0 <= pno < len(doc):
                    page = doc[pno]
                    texto = page.get_text().strip()
                    incrustado[pno] = texto
                    por_parrafos[pno] = texto_parrafos.parrafos_de_pagina(page).strip()
                    if forzar_ocr or self._necesita_ocr(texto, self._cobertura_imagenes(page)):
                        pendientes.append(pno)
            doc.close()

            reconocido = ocr_lote.reconocer_paginas(datos_bytes, pendientes, idioma)

            # Segunda pasada: juntar lo que ya traia la hoja con lo reconocido.
            for pno in sorted(incrustado):
                texto = incrustado[pno]
                metodo = 'texto_incrustado'
                if pno in reconocido:
                    # Se juntan las dos fuentes en vez de elegir la mas larga: en una
                    # hoja mixta la mas larga es la incrustada y asi se perdia lo que
                    # estaba dentro de la imagen. El detalle, en `ocr_fusion.py`.
                    texto, metodo = ocr_fusion.fusionar(texto, reconocido[pno])
                    if metodo != 'texto_incrustado':
                        uso_ocr = True
                # Lo que se entrega sale por párrafos, no renglón a renglón: la
                # fusión de arriba necesita los renglones crudos, por eso se
                # recompone aquí y no antes.
                if metodo == 'texto_incrustado':
                    texto = por_parrafos.get(pno, texto)
                else:
                    texto = texto_parrafos.reflujar_texto(texto)

                paginas_info.append({
                    'pagina': pno + 1,
                    'texto': texto,
                    'caracteres': len(texto),
                    'metodo': metodo
                })

            texto_total = '\n\n'.join(
                f'=== Pagina {p["pagina"]} ({p["metodo"]}) ===\n{p["texto"]}' for p in paginas_info
            )
            return {
                'total_paginas': len(paginas_info),
                'texto_total': texto_total,
                'paginas': paginas_info,
                'ocr_utilizado': uso_ocr
            }
        except Exception as e:
            logger.error(f"Error extrayendo texto: {e}")
            raise DocumentoInvalido(f"Error al extraer texto: {e}")


    def _cobertura_imagenes(self, page) -> float:
        """Proporcion de la pagina cubierta por imagenes (0.0 a 1.0)."""
        try:
            area_pagina = abs(page.rect.width * page.rect.height)
            if area_pagina <= 0:
                return 0.0
            area_imagenes = 0.0
            for info in page.get_image_info():
                r = fitz.Rect(info['bbox'])
                area_imagenes += abs(r.width * r.height)
            return min(area_imagenes / area_pagina, 1.0)
        except Exception:
            return 0.0


    def _necesita_ocr(self, texto: str, cobertura: float) -> bool:
        """Decide si hay que pasar Tesseract por la pagina.

        El criterio anterior era solo 'menos de 20 caracteres'. Eso fallaba con las
        paginas ESCANEADAS INSERTADAS dentro de un PDF digital: traen un texto
        incrustado minimo (una numeracion romana, un titulo como 'CERTIFICADO
        INSTITUCIONAL') y el contenido real dentro de una imagen. Como superaban los
        20 caracteres, nunca se les hacia OCR y se devolvia solo el titulo.
        Reportado el 20-jul-2026 sobre la pagina 7 de un documento de 130 paginas,
        que devolvia 68 caracteres y ninguna palabra de la carta escaneada.
        """
        if len(texto) < self.UMBRAL_TEXTO_MINIMO:
            return True
        # Una imagen grande puede tener texto dentro AUNQUE la hoja traiga mucho
        # texto escrito a ordenador: es la hoja mixta (un contrato con un acta
        # escaneada pegada debajo). Antes se exigia ademas menos de 1.000
        # caracteres incrustados, asi que a esas hojas no se les pasaba OCR y lo
        # de la imagen no salia nunca — «saca el texto pero incompleto»,
        # 31-jul-2026. Ahora manda la imagen: si ocupa lo suficiente, se lee.
        # Lo que el OCR repita no estorba: `ocr_fusion` solo suma lo que falta.
        return cobertura >= self.UMBRAL_COBERTURA_IMAGEN
