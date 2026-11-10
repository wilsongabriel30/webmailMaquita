"""Los dominios de correo de la casa, para la política de reenvío y las alertas de fraude.

Hasta el 09/11/2026 `account_protection.py` y `fraud_detector.py` traían cada uno su propia
lista `INTERNAL_DOMAINS = {"ejemplo.com"}` (valores de ejemplo que nadie sustituyó): todo
reenvío, incluso a un dominio propio, recibía 403, y cualquier regla generaba alerta de
«reenvío externo». Aquí hay una única fuente:

1. `organizacion.dominios_propios()` (fichero de la organización en el servidor), y
2. los dominios activos de la tabla `domain` (`SELECT domain FROM domain WHERE active = true`),
   con caché en memoria de 10 minutos para no consultar la base en cada petición.

Sin base de datos (o si falla la consulta) se responde con los de la organización.
"""

import logging
import time

from app import organizacion

logger = logging.getLogger("sieve.dominios")

CACHE_SEGUNDOS = 600
_cache: dict = {"ts": 0.0, "dominios": frozenset()}


def _de_organizacion() -> frozenset:
    return frozenset(d.lower() for d in organizacion.dominios_propios())


async def _de_la_base(db) -> frozenset:
    try:
        filas = await db.fetch("SELECT domain FROM domain WHERE active = true")
    except Exception as exc:  # la política no debe caerse porque falle la base
        logger.warning("No se pudieron leer los dominios de la tabla domain: %s", exc)
        return frozenset()
    return frozenset(str(f["domain"]).lower().strip() for f in filas if f["domain"])


async def dominios_internos(db=None) -> frozenset:
    """Los dominios propios (organización ∪ tabla `domain`), en minúsculas."""
    propios = _de_organizacion()
    if db is None:
        return propios
    ahora = time.monotonic()
    if ahora - _cache["ts"] < CACHE_SEGUNDOS:
        return propios | _cache["dominios"]
    de_base = await _de_la_base(db)
    if de_base or not _cache["dominios"]:
        _cache.update(ts=ahora, dominios=de_base)
    return propios | _cache["dominios"]


def dominio_de(direccion: str) -> str:
    """`Nombre <a@b.com>` o `a@b.com` → `b.com`; cadena vacía si no hay arroba."""
    direccion = (direccion or "").strip()
    if "<" in direccion and ">" in direccion:
        direccion = direccion[direccion.rfind("<") + 1 : direccion.rfind(">")]
    return direccion.rsplit("@", 1)[1].lower().strip() if "@" in direccion else ""


async def es_interno(direccion: str, db=None) -> bool:
    """Si la dirección pertenece a un dominio propio."""
    dominio = dominio_de(direccion)
    return bool(dominio) and dominio in await dominios_internos(db)


def olvidar_cache() -> None:
    """Vacía la caché (para pruebas o tras dar de alta un dominio)."""
    _cache.update(ts=0.0, dominios=frozenset())
