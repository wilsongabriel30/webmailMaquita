"""Cuerpo reescrito en trozos para el protocolo milter (05/11/2026).

El protocolo milter limita cada SMFIR_REPLBODY a 65.535 bytes y purepythonmilter lo valida
(`Length of 'chunk' must be <= 65535`). El milter mandaba el cuerpo reescrito por Safe Links en
un solo ReplaceBodyChunk, así que todo correo entrante de más de 64 KB fallaba el análisis
(MILTER_ANALISIS_FALLIDO) y se entregaba sin Safe Links. Aquí se parte en trozos: el servidor
los envía en orden y Postfix los concatena.
"""
from __future__ import annotations

from purepythonmilter import ReplaceBodyChunk

TROZO = 65535


def trocear(cuerpo: bytes, tam: int = TROZO) -> list:
    if not cuerpo:
        return []
    return [ReplaceBodyChunk(chunk=cuerpo[i:i + tam]) for i in range(0, len(cuerpo), tam)]
