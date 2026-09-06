# -*- coding: utf-8 -*-
"""Validación del emoji de una reacción (refuerzo de A-1).

El cliente ya escapa el emoji al pintarlo, pero el servidor guardaba cualquier cadena. Aquí
se acepta solo algo que parezca un emoji: corto (hasta 16 puntos de código, para
secuencias con modificadores y ZWJ), sin marcas de HTML ni caracteres de control.
"""
import re

_PROHIBIDO = re.compile(r'[<>&"\'\x00-\x1f\x7f]')
MAX_PUNTOS = 16


def normalizar_emoji(valor):
    """Devuelve el emoji limpio, o None si no vale."""
    if not isinstance(valor, str):
        return None
    e = valor.strip()
    if not e or len(e) > MAX_PUNTOS or _PROHIBIDO.search(e):
        return None
    return e
