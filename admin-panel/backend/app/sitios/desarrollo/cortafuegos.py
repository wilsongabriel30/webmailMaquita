"""Cortafuegos de aplicaciones web de un sitio (ModSecurity v3 + OWASP CRS completo).

Modo (apagado, solo detectar o bloquear), nivel de paranoia 1 o 2, exclusiones por número de regla (en todo el sitio
o solo en una ruta) y visor de los últimos bloqueos. El ayudante valida cada valor y aplica con copia previa y
`nginx -t` (si nginx lo rechaza, deja lo anterior). Las reglas para WordPress, Joomla y el catálogo siguen igual.
"""

import re

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel

from app.auth.dependencies import get_current_admin, require_superadmin
from app.dns.ayudante import b64
from app.sitios.router import _auditar, _ayudante, _dominio

router = APIRouter(prefix="/api/sitios", tags=["sitios"])
RE_RUTA = re.compile(r"/[A-Za-z0-9._~/-]{0,200}")


class Exclusion(BaseModel):
    regla: int
    ruta: str | None = None


class Ajustes(BaseModel):
    modo: str = "bloquear"
    paranoia: int = 1
    exclusiones: list[Exclusion] = []


@router.get("/{dominio}/cortafuegos")
async def ver(dominio: str, admin: dict = Depends(get_current_admin)):
    return await _ayudante("waf", _dominio(dominio), tiempo=120)


@router.put("/{dominio}/cortafuegos")
async def guardar(dominio: str, body: Ajustes, r: Request, admin: dict = Depends(require_superadmin)):
    dominio = _dominio(dominio)
    if body.modo not in ("apagado", "detectar", "bloquear") or body.paranoia not in (1, 2) or len(body.exclusiones) > 50:
        raise HTTPException(400, "Ajustes no válidos: modo apagado/detectar/bloquear, paranoia 1 o 2, hasta 50 exclusiones")
    exclusiones = []
    for e in body.exclusiones:
        ruta = (e.ruta or "").strip() or None
        if not 900000 <= e.regla <= 999999 or (ruta and not RE_RUTA.fullmatch(ruta)):
            raise HTTPException(400, "Exclusión no válida: número de regla de CRS (9xxxxx) y, si hay, una ruta que empiece por «/»")
        exclusiones.append({"regla": e.regla, "ruta": ruta})
    ajustes = {"modo": body.modo, "paranoia": body.paranoia, "exclusiones": exclusiones}
    res = await _ayudante("waf-guardar", dominio, b64(ajustes), tiempo=120)
    await _auditar(r, admin, "sitio_waf_guardar", dominio, ajustes)
    return res


@router.get("/{dominio}/cortafuegos/bloqueos")
async def bloqueos(dominio: str, cuantos: int = Query(50, ge=1, le=200), admin: dict = Depends(get_current_admin)):
    return await _ayudante("waf-bloqueos", _dominio(dominio), str(cuantos), tiempo=120)
