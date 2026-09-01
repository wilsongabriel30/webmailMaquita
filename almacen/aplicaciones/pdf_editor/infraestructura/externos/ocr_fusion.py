# -*- coding: utf-8 -*-
"""
Juntar el texto que ya traia el PDF con el que saca el OCR.
===========================================================
Una hoja puede ser mixta: parte escrita a ordenador (texto de verdad dentro del
PDF) y parte escaneada (una foto con letras). Ninguna de las dos fuentes vale
por si sola:

- quedarse solo con el texto incrustado pierde lo que hay dentro de la imagen;
- quedarse solo con el OCR empeora lo que ya estaba bien escrito (Tesseract
  confunde letras, se come tildes y desordena las columnas).

Antes se elegia una de las dos por su LARGO ('si el OCR saca mas caracteres, me
quedo con el OCR'), y con una hoja mixta eso descartaba justo lo que faltaba.
Aqui se conserva el texto incrustado tal cual y se le anaden SOLO los renglones
que el OCR aporta de nuevo.

Autoria: Equipo de Tecnologia Maquita — 2026-07-31
"""

import re

# Proporcion de palabras de un renglon que ya tienen que estar en el texto
# incrustado para darlo por repetido. No se compara letra a letra porque el OCR
# rara vez reproduce exacto: un 'VII' se lee 'vil' y una 'ó' se pierde.
REPETIDO_DESDE = 0.6

# Palabras de menos de esto no cuentan para comparar: 'de', 'la', 'y' estan en
# todas partes y darian por repetido cualquier renglon.
LARGO_MINIMO_PALABRA = 3


def _palabras(texto):
    return [p for p in re.findall(r'\w+', (texto or '').lower())
            if len(p) >= LARGO_MINIMO_PALABRA]


def renglon_repetido(renglon, vocabulario):
    """¿Este renglon del OCR dice algo que el texto incrustado ya decia?"""
    palabras = _palabras(renglon)
    if not palabras:
        return True
    repetidas = sum(1 for p in palabras if p in vocabulario)
    return repetidas >= len(palabras) * REPETIDO_DESDE


def aportacion_del_ocr(texto_incrustado, texto_ocr):
    """Los renglones del OCR que NO estaban ya en el texto incrustado."""
    vocabulario = set(_palabras(texto_incrustado))
    nuevos = []
    for renglon in (texto_ocr or '').splitlines():
        limpio = renglon.strip()
        if not limpio:
            continue
        if renglon_repetido(limpio, vocabulario):
            continue
        nuevos.append(limpio)
    return nuevos


def fusionar(texto_incrustado, texto_ocr):
    """Devuelve (texto, metodo) juntando lo escrito a ordenador y lo escaneado.

    El texto incrustado va SIEMPRE primero y sin tocar: es el bueno. Debajo, lo
    que el OCR haya encontrado de mas —que es lo que vive dentro de las imagenes.
    """
    incrustado = (texto_incrustado or '').strip()
    reconocido = (texto_ocr or '').strip()
    if not reconocido:
        return incrustado, 'texto_incrustado'
    if not incrustado:
        return reconocido, 'ocr_tesseract'

    nuevos = aportacion_del_ocr(incrustado, reconocido)
    if not nuevos:
        return incrustado, 'texto_incrustado'
    return incrustado + '\n' + '\n'.join(nuevos), 'texto_incrustado+ocr'
