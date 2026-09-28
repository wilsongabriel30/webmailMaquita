"""Direcciones por dominio: a cada cuenta, el servidor de su empresa.

Un mismo servidor de correo atiende a varias empresas, y cada una entra por su propio nombre
(`mail.<empresa>`, ver resolucion.py). Todo lo que el sistema le dice a una persona sobre
«dónde está tu correo» —la configuración de Outlook o del teléfono, el enlace de un aviso—
debe llevar el nombre de SU empresa, no el de la casa.

LA REGLA
  Si el dominio de la cuenta tiene un portal activo, se usa ese servidor.
  Si no, el servidor general (ORG_URL_CORREO / PUBLIC_BASE_URL).

LO QUE EXIGE DAR DE ALTA UN PORTAL
El nombre tiene que existir en el DNS y estar en el certificado, y no solo en el de la web:
la configuración que se entrega a Outlook apunta IMAP (993) y SMTP (465) a ese mismo nombre.
Un portal activo sin certificado en esos puertos rompe el alta de cuentas en Outlook.

Se apaga con DIRECCIONES_POR_DOMINIO=0: todo vuelve al servidor general.
"""

import time

from app import organizacion
from app.portales.resolucion import host_peticion

CACHE_SEGUNDOS = 60

_por_dominio: dict[str, str] = {}
_servidores: frozenset = frozenset()
_cache_hasta: float = 0.0


def activo() -> bool:
    return organizacion.valor("DIRECCIONES_POR_DOMINIO", "1").strip().lower() not in ("0", "no", "false")


def olvidar_cache() -> None:
    global _cache_hasta
    _cache_hasta = 0.0


async def _cargar(db) -> None:
    global _por_dominio, _servidores, _cache_hasta
    ahora = time.monotonic()
    if _cache_hasta > ahora:
        return
    try:
        filas = await db.fetch(
            "SELECT host, dominio FROM portal_empresa WHERE activo = true ORDER BY creado_en, host"
        )
        por_dominio: dict[str, str] = {}
        for f in filas:
            # Una empresa puede tener varios nombres: vale el primero que se dio de alta.
            por_dominio.setdefault(f["dominio"].lower(), f["host"].lower())
        _por_dominio = por_dominio
        _servidores = frozenset(f["host"].lower() for f in filas)
        _cache_hasta = ahora + CACHE_SEGUNDOS
    except Exception:
        # Sin tabla o sin base: todo el mundo al servidor general, que siempre funciona.
        _por_dominio, _servidores = {}, frozenset()
        _cache_hasta = ahora + 5


def servidor_general() -> str:
    return organizacion.servidor(organizacion.url_correo())


def dominio_de(correo: str) -> str:
    return (correo or "").rsplit("@", 1)[-1].strip().lower() if "@" in (correo or "") else ""


async def servidor_de_dominio(db, dominio: str) -> str | None:
    """El servidor del portal de ese dominio, o None si no tiene."""
    if db is None or not activo() or not dominio:
        return None
    await _cargar(db)
    return _por_dominio.get(dominio.lower())


async def servidor_de_cuenta(db, correo: str, general: str | None = None) -> str:
    return await servidor_de_dominio(db, dominio_de(correo)) or general or servidor_general()


async def url_de_cuenta(db, correo: str) -> str:
    """'https://mail.<empresa>' para esa cuenta; la dirección general si su empresa no tiene portal."""
    servidor = await servidor_de_dominio(db, dominio_de(correo))
    return f"https://{servidor}" if servidor else organizacion.url_correo()


async def url_de_peticion(db, request) -> str:
    """La dirección por la que está entrando quien hace la petición, si es un portal conocido.

    El nombre llega en una cabecera que escribe el cliente: solo se acepta si coincide con un
    portal dado de alta. Cualquier otro valor se ignora y se responde con la dirección general.
    """
    if db is not None and activo():
        await _cargar(db)
        servidor = host_peticion(request)
        if servidor in _servidores:
            return f"https://{servidor}"
    return organizacion.url_correo()


def cambiar_base(url: str, base: str) -> str:
    """Pasa un enlace de la dirección general a la de una empresa. Los demás enlaces no se tocan."""
    general = organizacion.url_correo()
    if base and base != general and url.startswith(general + "/"):
        return base.rstrip("/") + url[len(general):]
    return url


async def agrupar_por_url(db, correos) -> dict[str, list]:
    """{dirección: [cuentas]}: para enviar a cada empresa el enlace con su nombre."""
    grupos: dict[str, list] = {}
    for correo in correos:
        grupos.setdefault(await url_de_cuenta(db, correo), []).append(correo)
    return grupos
