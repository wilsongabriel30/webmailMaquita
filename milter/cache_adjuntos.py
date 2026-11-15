"""Adjuntos ya analizados y limpios, por huella SHA-256 (06/11/2026; compartida el 15/11/2026).

Las imágenes de la firma viajan en casi todos los correos y cada una costaba 1-3 s de análisis:
una respuesta con 7 imágenes de firma y un PDF retenía el envío 13 s (en Zimbra era inmediato).
Un archivo idéntico (mismos bytes) que ya salió LIMPIO no se vuelve a analizar durante unas horas.
Solo se guardan resultados limpios y sin errores de motor; lo sospechoso se analiza siempre.

15/11/2026: la memoria era de CADA proceso y desde el 07/11 el milter corre en 6 procesos, así que
la misma firma se volvía a analizar en cada uno (2-3 s por correo interno). Ahora la huella se
guarda además en Redis, que comparten todos los procesos y sobrevive a los reinicios del milter.
Si Redis no responde se sigue solo con la memoria del proceso: nunca frena ni rompe el análisis.
"""

from __future__ import annotations

import hashlib
import logging
import os
import time

log = logging.getLogger("maquita_milter")

VIGENCIA_S = float(os.getenv("MILTER_CACHE_LIMPIOS_S", str(24 * 3600)))
MAXIMO = 20000
PREFIJO = "maquita:milter:limpio:"
REINTENTO_S = 30.0  # tras un fallo de Redis no se vuelve a intentar durante este tiempo
_limpios: dict[str, float] = {}
_redis = {"cliente": None, "desde": 0.0}


def _url_redis() -> str:
    url = os.getenv("REDIS_URL", "")
    if url:
        return url
    try:
        for linea in open("/opt/maquita-webmail/backend/.env"):
            if linea.startswith("REDIS_URL="):
                return linea.split("=", 1)[1].strip()
    except Exception:
        pass
    return ""


def _cliente():
    """Cliente de Redis o None. Se crea a demanda (después del fork) y se descarta si falla."""
    if _redis["cliente"] is not None:
        return _redis["cliente"]
    if time.monotonic() < _redis["desde"]:
        return None
    try:
        import redis

        url = _url_redis()
        if not url:
            raise RuntimeError("sin REDIS_URL")
        _redis["cliente"] = redis.Redis.from_url(
            url, socket_timeout=0.3, socket_connect_timeout=0.3
        )
    except Exception as e:
        _fallo(e)
    return _redis["cliente"]


def _fallo(e: Exception) -> None:
    _redis["cliente"] = None
    _redis["desde"] = time.monotonic() + REINTENTO_S
    log.warning("CACHE_ADJUNTOS_SIN_REDIS se sigue con la memoria del proceso: %r", e)


def huella(contenido: bytes) -> str:
    return hashlib.sha256(contenido).hexdigest()


def _anotar_local(h: str, segundos: float) -> None:
    if len(_limpios) >= MAXIMO:
        ahora = time.monotonic()
        for k in [k for k, v in _limpios.items() if v < ahora] or list(_limpios)[
            : MAXIMO // 10
        ]:
            _limpios.pop(k, None)
    _limpios[h] = time.monotonic() + segundos


def es_limpio(h: str) -> bool:
    vence = _limpios.get(h)
    if vence is not None:
        if vence >= time.monotonic():
            return True
        _limpios.pop(h, None)
    r = _cliente()
    if r is None:
        return False
    try:
        resta = r.ttl(PREFIJO + h)
    except Exception as e:
        _fallo(e)
        return False
    if resta and resta > 0:
        _anotar_local(h, float(resta))
        return True
    return False


def guardar_limpio(h: str) -> None:
    _anotar_local(h, VIGENCIA_S)
    r = _cliente()
    if r is None:
        return
    try:
        r.set(PREFIJO + h, "1", ex=int(VIGENCIA_S))
    except Exception as e:
        _fallo(e)
