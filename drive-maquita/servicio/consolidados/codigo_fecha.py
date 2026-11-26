# -*- coding: utf-8 -*-
"""Códigos que Excel guardó como fecha: devolver el texto que la persona ve.

En las matrices, muchos «Cód LATINIUM» se escribieron como «6.2» o «3.5.03» y
la hoja los convirtió en fecha (06/02, 03/05/2003) con un formato que los
sigue MOSTRANDO como código (`d.m`, `d.m.yy`). IMPORTRANGE y QUERY traían lo
que se ve; aquí se lee el valor crudo, y el consolidado mostraba
«2024-02-06 00:00:00» (05/10/2026).

`texto_visible` devuelve el código tal como se ve cuando el formato es de ese
tipo, y None en cualquier otro caso: una fecha de verdad (con barras, guiones,
nombre de mes o año de cuatro cifras) se deja como fecha.
"""
import datetime
import re

_PIEZA = re.compile(r"d+|m+|y+")


def texto_visible(valor, formato):
    if not isinstance(valor, (datetime.datetime, datetime.date)) or not formato:
        return None
    limpio = re.sub(r"\[[^\]]*\]|;.*$|\"[^\"]*\"|\\\\", "", str(formato)).strip().lower()
    if "." not in limpio or not re.fullmatch(r"[dmy.]+", limpio):
        return None
    piezas = _PIEZA.findall(limpio)
    letras = [p[0] for p in piezas]
    if "d" not in letras or "m" not in letras or len(piezas) > 3 or any(len(p) > 2 for p in piezas):
        return None                     # mmm (nombre de mes) o yyyy: es una fecha
    partes = []
    for pieza in piezas:
        numero = {"d": valor.day, "m": valor.month, "y": valor.year % 100}[pieza[0]]
        partes.append("%0*d" % (2 if (len(pieza) > 1 or pieza[0] == "y") else 1, numero))
    return ".".join(partes)
