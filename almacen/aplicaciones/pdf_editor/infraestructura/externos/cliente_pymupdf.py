# -*- coding: utf-8 -*-
"""
Adaptador PyMuPDF (fitz) para operaciones PDF.

PyMuPDF es la librería principal para:
- Renderizado de alta calidad
- Extracción de texto
- Manipulación de páginas
- Extracción de imágenes
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


from .cliente_paginas import MezclaPaginas
from .cliente_render import MezclaDibujo
from .cliente_texto import MezclaTexto
from .cliente_operaciones import MezclaOperaciones
from .cliente_anotaciones import MezclaAnotaciones
from .cliente_letras import MezclaLetras
from .cliente_reflujo import MezclaReflujo


class ClientePyMuPDF(MezclaPaginas, MezclaDibujo, MezclaTexto, MezclaOperaciones, MezclaAnotaciones, MezclaLetras, MezclaReflujo):
    """
    Cliente adaptador para PyMuPDF.

    Proporciona operaciones de:
    - Renderizado de páginas
    - Extracción de información
    - Manipulación de páginas
    - Generación de miniaturas
    """

    def __init__(self):
        """Inicializa el cliente verificando que PyMuPDF esté disponible."""
        if fitz is None:
            raise ImportError(
                "PyMuPDF no está instalado. Ejecute: pip install PyMuPDF"
            )
        logger.info("Cliente PyMuPDF inicializado")

    # =========================================================================
    # OPERACIONES DIRECTAS DESDE BYTES (sin guardar en disco)
    # =========================================================================

    # --- Umbrales para decidir cuando hace falta OCR (ver _necesita_ocr) ---
    UMBRAL_TEXTO_MINIMO = 20        # menos de esto = pagina practicamente vacia
    UMBRAL_COBERTURA_IMAGEN = 0.25  # imagen que cubre >= 25% de la pagina
    UMBRAL_TEXTO_ESCANEADO = 1000   # con imagen grande, hasta aqui se considera escaneado

    # ---------------------------------------------------------------
    # ANOTACIONES (highlight, subrayado, tachado, texto, nota, dibujo)
    # ---------------------------------------------------------------

    # ==================== REEMPLAZO REAL DE TEXTO ====================
    # El navegador no puede escribir con la fuente incrustada del PDF: solo tiene las
    # 14 estándar, y por eso el texto reescrito "cambiaba de letra". Aquí sí se puede:
    # se lee el estilo real del fragmento (fuente, cuerpo, color), se BORRA de verdad
    # con una redacción y se vuelve a escribir con la MISMA fuente del documento.

    # Base14 de repuesto cuando la fuente incrustada no sirve (no trae los glifos que
    # el usuario escribió, o es un subconjunto imposible de reutilizar)
    _BASE14 = {
        ('serif', False, False): 'tiro',  ('serif', True, False): 'tibo',
        ('serif', False, True): 'tiit',   ('serif', True, True): 'tibi',
        ('sans', False, False): 'helv',   ('sans', True, False): 'hebo',
        ('sans', False, True): 'heit',    ('sans', True, True): 'hebi',
        ('mono', False, False): 'cour',   ('mono', True, False): 'cobo',
        ('mono', False, True): 'coit',    ('mono', True, True): 'cobi',
    }


    # Fuentes del sistema métricamente equivalentes a las típicas de Word/Office.
    # Se usan cuando la fuente incrustada del PDF no sirve (subconjunto sin los glifos
    # que el usuario escribió): dan un resultado MUCHO más parecido que las 14 estándar.
    _EQUIVALENTES = [
        # Caligráficas / manuscritas: las de los títulos de tesis (Monotype Corsiva,
        # Lucida Calligraphy, Segoe Script…). Sin esta entrada caían en Arial y el
        # título quedaba irreconocible.
        (('corsiva', 'calligra', 'script', 'chancery', 'handwriting', 'brush',
          'freestyle', 'edwardian', 'vivaldi', 'bradley', 'papyrus', 'cursive',
          'lucidahand', 'segoeprint', 'segoescript', 'french', 'kunstler',
          'monotypecorsiva', 'chorus'),                    'TeX Gyre Chorus'),
        (('calibri', 'carlito'),                          'Carlito'),
        (('cambria', 'caladea'),                          'Caladea'),
        (('arial', 'helvetica', 'liberationsans', 'segoe', 'tahoma', 'verdana', 'calibri'), 'Liberation Sans'),
        # Palatino y Book Antiqua tienen equivalente de verdad instalado (P052); antes
        # caían en un palo seco, que es un cambio de letra que se ve a la legua.
        (('palatino', 'bookantiqua', 'palladio'),         'P052'),
        (('centurygothic', 'avantgarde', 'adventor'),     'TeX Gyre Adventor'),
        (('bookman', 'bookmanoldstyle'),                  'TeX Gyre Bonum'),
        # OJO: aquí NO puede ir 'book' a secas. Casaba con «DejaVu Sans Book» y mandaba
        # un palo seco a una serif (31-jul-2026).
        (('times', 'timesnewroman', 'liberationserif', 'georgia', 'garamond'),      'Liberation Serif'),
        (('courier', 'consolas', 'mono'),                 'Liberation Mono'),
    ]

    # Resolución a la que se mide la tinta. 200 ppp da ~0,36 pt de precisión, de sobra
    # para el ojo, y el recorte que se renderiza es de una palabra: cuesta milisegundos.
    _PPP_MEDIDA = 200
