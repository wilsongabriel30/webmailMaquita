# -*- coding: utf-8 -*-
"""
Reconocer varias hojas A LA VEZ para «Extraer texto».
=====================================================

«Digitalizar» ya repartía sus páginas entre varios procesos (`ocr_pagina_texto.py`),
pero «Extraer texto» seguía yendo hoja por hoja: sobre un escaneo de 6 páginas eran
10,7 s con el usuario esperando delante. Aquí se hace el mismo reparto para esa otra
ruta (31-jul-2026).

Detalles que importan y no se ven en el código:

* **El PDF va a `/dev/shm`, que es RAM, no disco.** Los procesos hijos necesitan poder
  abrir el documento por su cuenta —un objeto de PyMuPDF no viaja entre procesos—, y
  pasarles los bytes significaría tener el documento repetido tantas veces como
  procesos. Abriéndolo desde `/dev/shm` el sistema lo comparte (mmap): una sola copia
  en memoria, y sin tocar el disco. Si no hubiera `/dev/shm`, se cae al temporal de
  siempre.
* **Escala de grises.** Igual que en la ruta de una sola hoja: una A4 a 300 dpi ocupa
  8,7 MB en gris contra 26,1 MB en color, y tesseract binariza igualmente. Con 8 hojas
  a la vez la diferencia deja de ser un detalle.
* **Nunca dentro del worker de gunicorn.** Tesseract es CPU pura y el worker es
  eventlet: repartir procesos ahí congelaría a los demás usuarios. Por eso, si se
  detecta eventlet parcheado, esto se va solo a la vía de una en una. Hoy quien llama
  es `conversor_cli.py ocr`, que ya es un proceso aparte.

Autoría: Equipo de Tecnología Maquita — 2026-07-31
"""

import logging
import os
import sys
import tempfile
from concurrent.futures import ProcessPoolExecutor

import fitz

logger = logging.getLogger(__name__)

DPI = 300
CARPETA_RAM = '/dev/shm'


def _procesos(cuantas_hojas):
    """Cuántas hojas a la vez. Se dejan núcleos libres para el resto de FARO."""
    return max(1, min(8, (os.cpu_count() or 2) - 2, cuantas_hojas))


def _hay_eventlet():
    """¿Estamos dentro de un worker eventlet? Entonces nada de repartir procesos."""
    modulo = sys.modules.get('eventlet')
    if modulo is None:
        return False
    try:
        return bool(modulo.patcher.is_monkey_patched('thread'))
    except Exception:
        return True     # ante la duda, la vía prudente


def reconocer_pagina(pagina, idioma='spa', dpi=DPI):
    """El texto que tesseract lee dentro de UNA hoja ya abierta.

    Es el único sitio donde se renderiza para OCR: lo usan tanto la vía de una hoja
    como cada proceso del reparto, para que las dos reconozcan exactamente igual.
    """
    try:
        import pytesseract
        from PIL import Image
        from .cliente_texto import _idioma_disponible

        matriz = fitz.Matrix(dpi / 72, dpi / 72)
        pix = pagina.get_pixmap(matrix=matriz, colorspace=fitz.csGRAY)
        imagen = Image.frombytes('L', [pix.width, pix.height], pix.samples)
        # El pixmap ya no hace falta: se suelta antes de que tesseract trabaje, para
        # no tener las dos copias de la hoja vivas a la vez.
        pix = None

        texto = pytesseract.image_to_string(
            imagen, lang=_idioma_disponible(idioma), config='--psm 1')
        return texto.strip()
    except ImportError:
        logger.warning('pytesseract no disponible para OCR')
        return ''
    except Exception as e:
        logger.warning('OCR falló en una hoja: %s', e)
        return ''


def _trabajo(argumentos):
    """Una hoja en su propio proceso. A nivel de módulo porque tiene que viajar."""
    ruta_pdf, numero, idioma, dpi = argumentos
    documento = fitz.open(ruta_pdf)
    try:
        return numero, reconocer_pagina(documento[numero], idioma, dpi)
    except Exception as e:
        logger.warning('OCR falló en la hoja %d: %s', numero + 1, e)
        return numero, ''
    finally:
        documento.close()


def reconocer_paginas(datos_bytes, numeros, idioma='spa', dpi=DPI):
    """El texto reconocido de las hojas pedidas: {número de hoja (desde 0): texto}.

    Si el reparto no se puede hacer —una sola hoja, worker eventlet, o el pool
    falla— se reconoce de una en una. Nunca se queda sin responder: es preferible
    tardar a devolver el documento vacío.
    """
    numeros = list(numeros)
    if not numeros:
        return {}

    procesos = _procesos(len(numeros))
    if procesos > 1 and not _hay_eventlet():
        carpeta = CARPETA_RAM if os.path.isdir(CARPETA_RAM) else None
        descriptor, ruta = tempfile.mkstemp(suffix='.pdf', prefix='ocrlote_', dir=carpeta)
        try:
            with os.fdopen(descriptor, 'wb') as fh:
                fh.write(datos_bytes)
            trabajos = [(ruta, n, idioma, dpi) for n in numeros]
            with ProcessPoolExecutor(max_workers=procesos) as pool:
                resultado = dict(pool.map(_trabajo, trabajos))
            logger.info('OCR: %d hoja(s) repartidas entre %d proceso(s) [%s]',
                        len(numeros), procesos, idioma)
            return resultado
        except Exception as e:
            logger.warning('El reparto en procesos falló (%s): se sigue de una en una', e)
        finally:
            try:
                os.remove(ruta)
            except OSError:
                pass

    documento = fitz.open(stream=datos_bytes, filetype='pdf')
    try:
        return {n: reconocer_pagina(documento[n], idioma, dpi) for n in numeros}
    finally:
        documento.close()
