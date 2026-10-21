"""Lo que comparten las rutas de los sitios: alcance, ficha de la sesión y llamada auditada.

El alcance se comprueba aquí ANTES de llamar al intermediario, aunque él lo vuelva a comprobar:
lo ajeno no sale ni del portal. Un sitio está en alcance si es un dominio asignado (uno.example)
o un subdominio suyo (blog.uno.example). Fuera de alcance: 404, nunca 403.
"""

import re

from fastapi import HTTPException, Request

from app.sesion import auditar
from app.sitios import cliente

RE_SITIO = re.compile(r"^(?=.{4,200}$)([a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}$")
NO_ENCONTRADO = "No encontrado"


def dominio_de(admin: dict, sitio: str) -> str | None:
    """El dominio asignado al que pertenece `sitio` (el más largo si hay varios), o None."""
    candidatos = [d for d in admin["dominios"] if sitio == d or sitio.endswith("." + d)]
    return max(candidatos, key=len) if candidatos else None


def exigir_sitio(admin: dict, valor) -> tuple[str, str]:
    """(sitio, dominio asignado) o 404."""
    sitio = str(valor or "").strip().lower()
    if not RE_SITIO.match(sitio):
        raise HTTPException(404, NO_ENCONTRADO)
    dominio = dominio_de(admin, sitio)
    if not dominio:
        raise HTTPException(404, NO_ENCONTRADO)
    return sitio, dominio


def exigir_dominio(admin: dict, valor) -> str:
    """Un dominio asignado exacto (la zona DNS): ni subdominios ni ajenos."""
    dominio = str(valor or "").strip().lower()
    if dominio not in admin["dominios"]:
        raise HTTPException(404, NO_ENCONTRADO)
    return dominio


async def cuerpo(request: Request) -> dict:
    """El JSON de la petición como diccionario (vacío si no trae nada)."""
    try:
        datos = await request.json()
    except Exception:
        datos = {}
    return datos if isinstance(datos, dict) else {}


def ficha_de(request: Request) -> str:
    # admin_actual ya comprobó que la cabecera existe y es una sesión válida.
    return request.headers.get("Authorization", "")[7:]


async def llamar(request: Request, admin: dict, orden: str, dominio: str | None = None, args: dict | None = None,
                 accion: str | None = None, detalles: dict | None = None):
    """Llama al intermediario y, si sale bien y hay `accion`, lo deja en la auditoría.

    En `detalles` nunca van contraseñas; la respuesta (que puede traerlas) no se audita.
    """
    datos = await cliente.pedir(ficha_de(request), orden, dominio, args)
    if accion:
        await auditar(request, admin, accion, dominio or "", detalles)
    return datos


async def listar(request: Request, admin: dict) -> dict:
    datos = await cliente.pedir(ficha_de(request), "listar")
    return datos if isinstance(datos, dict) else {}


async def sitio_existente(request: Request, admin: dict, sitio: str) -> dict:
    """La ficha del sitio en el listado del intermediario, o 404."""
    datos = await listar(request, admin)
    for s in datos.get("sitios") or []:
        if isinstance(s, dict) and s.get("dominio") == sitio:
            return s
    raise HTTPException(404, NO_ENCONTRADO)
