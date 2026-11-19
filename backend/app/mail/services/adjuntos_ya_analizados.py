"""Adjuntos ya analizados y limpios: memoria compartida con el filtro de Postfix (19/11/2026).

Al enviar, el correo web analizaba cada adjunto (antivirus, reglas y detonación en contenedor) y,
segundos después, el filtro de Postfix (milter/) volvía a analizar los mismos bytes: un adjunto
nuevo costaba el doble y algunos envíos tardaban de 10 a 40 s.

El filtro ya guarda en Redis la huella SHA-256 de lo que salió LIMPIO (milter/cache_adjuntos.py).
Aquí se usa esa misma memoria: si la huella está, no se analiza otra vez; si el análisis sale
limpio y sin motores caídos, se guarda para que el filtro no lo repita.

Solo se recuerda lo limpio; lo sospechoso se analiza siempre. Si Redis no responde se analiza
como antes: la memoria nunca frena ni rompe el envío.
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import os
from typing import Awaitable, Callable

logger = logging.getLogger(__name__)

# Los mismos valores que milter/cache_adjuntos.py: las dos partes leen y escriben las mismas claves.
PREFIJO = "maquita:milter:limpio:"
VIGENCIA_S = int(float(os.getenv("MILTER_CACHE_LIMPIOS_S", str(24 * 3600))))
ESPERA_REDIS_S = 0.3

Analizador = Callable[[bytes, str, str], Awaitable[dict]]


def huella(contenido: bytes) -> str:
    return hashlib.sha256(contenido).hexdigest()


def es_resultado_limpio(veredicto: dict | None) -> bool:
    """Limpio de verdad: sin amenazas y sin ningún motor obligatorio caído."""
    return (
        bool(veredicto)
        and veredicto.get("result") == "clean"
        and not veredicto.get("errors")
    )


async def _ya_limpio(redis, clave: str) -> bool:
    if redis is None:
        return False
    try:
        resta = await asyncio.wait_for(redis.ttl(clave), ESPERA_REDIS_S)
        return bool(resta and int(resta) > 0)
    except Exception as e:
        logger.warning("ADJUNTOS_YA_ANALIZADOS sin Redis al consultar: %r", e)
        return False


async def _recordar(redis, clave: str) -> None:
    if redis is None:
        return
    try:
        await asyncio.wait_for(redis.set(clave, "1", ex=VIGENCIA_S), ESPERA_REDIS_S)
    except Exception as e:
        logger.warning("ADJUNTOS_YA_ANALIZADOS sin Redis al guardar: %r", e)


async def analizar_con_memoria(
    redis, contenido: bytes, nombre: str, tipo: str, analizar: Analizador
) -> dict:
    """Veredicto del adjunto, sin repetir el análisis de lo que ya salió limpio."""
    clave = PREFIJO + huella(contenido)
    if await _ya_limpio(redis, clave):
        return {
            "result": "clean",
            "threats": [],
            "details": {"memoria": "limpio-ya-analizado"},
        }
    veredicto = await analizar(contenido, nombre, tipo)
    if es_resultado_limpio(veredicto):
        await _recordar(redis, clave)
    return veredicto
