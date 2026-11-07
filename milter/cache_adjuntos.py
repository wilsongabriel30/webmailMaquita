"""Adjuntos ya analizados y limpios, por huella SHA-256 (06/11/2026).

Las imágenes de la firma viajan en casi todos los correos y cada una costaba 1-3 s de análisis:
una respuesta con 7 imágenes de firma y un PDF retenía el envío 13 s (en Zimbra era inmediato).
Un archivo idéntico (mismos bytes) que ya salió LIMPIO no se vuelve a analizar durante unas horas.
Solo se guardan resultados limpios y sin errores de motor; lo sospechoso se analiza siempre.
Vive en memoria del milter: al reiniciarlo se vacía (no cambia la seguridad, solo el tiempo).
"""
from __future__ import annotations

import hashlib
import os
import time

VIGENCIA_S = float(os.getenv("MILTER_CACHE_LIMPIOS_S", str(6 * 3600)))
MAXIMO = 20000
_limpios: dict[str, float] = {}


def huella(contenido: bytes) -> str:
    return hashlib.sha256(contenido).hexdigest()


def es_limpio(h: str) -> bool:
    vence = _limpios.get(h)
    if vence is None:
        return False
    if vence < time.monotonic():
        _limpios.pop(h, None)
        return False
    return True


def guardar_limpio(h: str) -> None:
    if len(_limpios) >= MAXIMO:
        ahora = time.monotonic()
        for k in [k for k, v in _limpios.items() if v < ahora] or list(_limpios)[: MAXIMO // 10]:
            _limpios.pop(k, None)
    _limpios[h] = time.monotonic() + VIGENCIA_S
