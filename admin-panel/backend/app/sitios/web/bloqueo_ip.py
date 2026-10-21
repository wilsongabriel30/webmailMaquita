"""Bloqueo de IP por sitio: direcciones o redes IPv4/IPv6 que reciben 403 solo en este sitio."""

import ipaddress

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from app.auth.dependencies import require_superadmin
from app.sitios.web.comun import guardar

router = APIRouter(prefix="/api/sitios", tags=["sitios"])
MAXIMO = 500


class Bloqueo(BaseModel):
    redes: list[str]


@router.put("/{dominio}/web/bloqueo")
async def guardar_bloqueo(dominio: str, body: Bloqueo, r: Request, admin: dict = Depends(require_superadmin)):
    if len(body.redes) > MAXIMO:
        raise HTTPException(400, f"Se admiten hasta {MAXIMO} IP o redes por sitio")
    redes = []
    for valor in body.redes:
        valor = valor.strip()
        if not valor:
            continue
        try:
            red = ipaddress.ip_network(valor, strict=False)
        except ValueError:
            raise HTTPException(400, f"IP o red no válida: {valor[:50]}")
        if red.prefixlen == 0:
            raise HTTPException(400, "No se puede bloquear Internet entero (/0)")
        redes.append(valor)
    return await guardar(r, admin, dominio, "web-bloqueo", redes, "sitio_web_bloqueo", tope=20000)
