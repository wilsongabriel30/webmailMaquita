"""Dirección del portal de administradores de dominio (8444): la general y la de cada empresa.

ORG_URL_PORTAL_DOMINIO si está definida; si no, el servidor del correo con el puerto del portal.
Si un dominio tiene portal propio (portal_empresa), su administrador entra por ESE nombre (su
certificado es el de la empresa), con el mismo puerto del portal.
"""

from urllib.parse import urlsplit

from app import organizacion

PUERTO_PORTAL_DOMINIO = "8444"


async def direcciones(db) -> tuple[str | None, dict]:
    """(dirección general o None, {dominio: dirección del portal propio})."""
    explicita = organizacion.url("ORG_URL_PORTAL_DOMINIO", "")
    puerto = (urlsplit(explicita).port if explicita else None) or PUERTO_PORTAL_DOMINIO
    por_dominio = {}
    try:
        filas = await db.fetch("SELECT host, dominio FROM portal_empresa WHERE activo = true")
        por_dominio = {f["dominio"].lower(): f"https://{f['host'].lower()}:{puerto}" for f in filas}
    except Exception:
        pass  # instalación sin portales por empresa
    if explicita:
        return explicita, por_dominio
    correo = organizacion.url("PUBLIC_BASE_URL", organizacion.url("ORG_URL_CORREO", ""))
    servidor = urlsplit(correo).hostname if correo else None
    return (f"https://{servidor}:{puerto}" if servidor else None), por_dominio


async def de_dominio(db, dominio: str) -> str | None:
    """La dirección por la que entra el administrador de ese dominio."""
    general, por_dominio = await direcciones(db)
    return por_dominio.get(dominio.lower()) or general
