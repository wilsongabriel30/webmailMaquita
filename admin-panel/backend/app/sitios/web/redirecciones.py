"""Redirecciones del sitio: de una ruta a otra dirección, o de todo el dominio, con 301 o 302."""

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from app.auth.dependencies import require_superadmin
from app.sitios.web.comun import guardar

router = APIRouter(prefix="/api/sitios", tags=["sitios"])
MAXIMO = 200


class Redireccion(BaseModel):
    origen: str  # «/ruta» o «*» (todo el dominio)
    destino: str
    codigo: Literal[301, 302] = 301
    subrutas: bool = False
    conservar_ruta: bool = True


class Redirecciones(BaseModel):
    redirecciones: list[Redireccion]


@router.put("/{dominio}/web/redirecciones")
async def guardar_redirecciones(dominio: str, body: Redirecciones, r: Request, admin: dict = Depends(require_superadmin)):
    if len(body.redirecciones) > MAXIMO:
        raise HTTPException(400, f"Se admiten hasta {MAXIMO} redirecciones por sitio")
    datos = [x.model_dump() for x in body.redirecciones]
    return await guardar(r, admin, dominio, "web-redirecciones", datos, "sitio_web_redirecciones", tope=20000)
