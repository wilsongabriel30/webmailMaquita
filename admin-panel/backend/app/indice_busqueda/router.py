"""Índice de texto completo del correo (panel → Servicios → tarjeta «Búsqueda de texto completo»).

Estado del índice (activo, texto de adjuntos, buzones indexados, herramientas del decodificador) y
«Reindexar buzón», que rehace el índice de una cuenta en segundo plano: por ejemplo, para que entren
los adjuntos de correos antiguos. Todo pasa por el ayudante root maquita-fts (deploy/dovecot/fts) a
través de maquita-sudo, que vuelve a validar el buzón. Reindexar no toca los mensajes: tampoco los
que están bajo retención legal.
"""

import re

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from app.auth.dependencies import get_current_admin, require_superadmin
from app.dns.ayudante import auditar, ayudante

router = APIRouter(prefix="/api/indice-busqueda", tags=["indice-busqueda"])

RE_BUZON = re.compile(
    r"[a-z0-9][a-z0-9._+-]{0,63}@[a-z0-9]([a-z0-9-]*[a-z0-9])?(\.[a-z0-9]([a-z0-9-]*[a-z0-9])?)+"
)


def buzon_valido(valor: str) -> str | None:
    buzon = (valor or "").strip().lower()
    return buzon if len(buzon) <= 254 and RE_BUZON.fullmatch(buzon) else None


@router.get("")
async def estado(admin: dict = Depends(get_current_admin)):
    return await ayudante("fts", "estado", tiempo=120)


class Reindexar(BaseModel):
    buzon: str


@router.post("/reindexar")
async def reindexar(body: Reindexar, r: Request, admin: dict = Depends(require_superadmin)):
    buzon = buzon_valido(body.buzon)
    if not buzon:
        raise HTTPException(400, "Buzón con formato inválido")
    res = await ayudante("fts", "reindexar", buzon, tiempo=300)
    await auditar(r, admin, "indice_busqueda_reindexar", buzon, {"carpetas": res.get("carpetas")})
    return res
