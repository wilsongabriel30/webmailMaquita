"""Portales por empresa: cada empresa entra al correo por su propio nombre de servidor.

Idea: quien escribe `mail.<empresa>` ve la marca de esa empresa y solo puede entrar con
una cuenta de ese dominio. El portal padre no restringe nada: desde ahí entra cualquier
cuenta de la casa.

Así cada empresa percibe su propio servidor de correo, aunque por debajo sea uno solo.

La relación entre el nombre del servidor y el dominio de correo vive en la tabla
`portal_empresa`, no en el código, para poder añadir empresas sin tocar el programa.
"""

import time

CACHE_SEGUNDOS = 60

_cache: dict[str, str] = {}
_cache_hasta: float = 0.0


def host_peticion(request) -> str:
    """Nombre de servidor por el que llegó la petición, sin puerto y en minúsculas."""
    host = request.headers.get("host", "") or ""
    # Quita el puerto, cuidando el formato de IPv6 entre corchetes
    if host.startswith("["):
        host = host.split("]", 1)[0].lstrip("[")
    elif ":" in host:
        host = host.split(":", 1)[0]
    return host.strip().lower().rstrip(".")


async def _portales(db) -> dict[str, str]:
    """Mapa {nombre de servidor: dominio de correo}, con caché de un minuto."""
    global _cache, _cache_hasta
    ahora = time.monotonic()
    if _cache_hasta > ahora:
        return _cache
    try:
        filas = await db.fetch(
            "SELECT host, dominio FROM portal_empresa WHERE activo = true"
        )
        _cache = {f["host"].lower(): f["dominio"].lower() for f in filas}
        _cache_hasta = ahora + CACHE_SEGUNDOS
    except Exception:
        # Si la tabla aún no existe o la base no responde, no se restringe nada:
        # es preferible que la gente pueda entrar a dejarla fuera por un fallo interno.
        _cache = {}
        _cache_hasta = ahora + 5
    return _cache


def olvidar_cache() -> None:
    """Descarta la caché (para las pruebas y para cuando se edita la tabla)."""
    global _cache_hasta
    _cache_hasta = 0.0


async def dominio_del_portal(db, request) -> str | None:
    """Dominio de correo al que está restringido este portal.

    Devuelve `None` cuando el portal no restringe (el padre, o un nombre desconocido).
    """
    return (await _portales(db)).get(host_peticion(request))


async def cuenta_admitida(db, request, username: str) -> bool:
    """¿Esta cuenta puede entrar por el portal desde el que se está pidiendo?

    Desde el portal padre entra cualquiera. Desde el portal de una empresa, solo las
    cuentas de esa empresa.
    """
    dominio = await dominio_del_portal(db, request)
    if dominio is None:
        return True
    _, _, dominio_cuenta = username.partition("@")
    return dominio_cuenta.lower() == dominio
