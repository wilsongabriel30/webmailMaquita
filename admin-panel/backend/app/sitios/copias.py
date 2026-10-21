"""Copias del sitio que controla su dueño: crear ahora (archivos + bases), listar, descargar, restaurar y borrar.

Son aparte de los respaldos del servidor (Respaldos, restic). El ayudante guarda como mucho 5 por sitio y, antes de
restaurar, hace una copia previa automática del estado de ese momento.
"""

import re

from fastapi import APIRouter, Depends, HTTPException, Request

from app.auth.dependencies import require_superadmin
from app.sitios.entrega import enlace
from app.sitios.router import _auditar, _ayudante, _dominio

router = APIRouter(prefix="/api/sitios", tags=["sitios"])
RE_COPIA = re.compile(r"^\d{8}-\d{6}$")


def _copia(valor: str) -> str:
    if not RE_COPIA.match(valor or ""):
        raise HTTPException(400, "Copia no válida")
    return valor


@router.get("/{dominio}/copias")
async def listar(dominio: str, admin: dict = Depends(require_superadmin)):
    return await _ayudante("copias", _dominio(dominio))


@router.post("/{dominio}/copias")
async def crear(dominio: str, r: Request, admin: dict = Depends(require_superadmin)):
    dominio = _dominio(dominio)
    res = await _ayudante("copia-crear", dominio, tiempo=1800)
    await _auditar(r, admin, "sitio_copia_crear", dominio, {"id": (res.get("copia") or {}).get("id")})
    return res


@router.post("/{dominio}/copias/{copia}/descargar")
async def descargar(dominio: str, copia: str, r: Request, admin: dict = Depends(require_superadmin)):
    dominio = _dominio(dominio)
    res = await _ayudante("copia-descargar", dominio, _copia(copia), tiempo=1800)
    await _auditar(r, admin, "sitio_copia_descargar", dominio, {"id": copia})
    return {"enlace": enlace(res.get("archivo", ""), res.get("nombre") or f"{dominio}-{copia}.tar.gz"),
            "bytes": res.get("bytes")}


@router.post("/{dominio}/copias/{copia}/restaurar")
async def restaurar(dominio: str, copia: str, r: Request, admin: dict = Depends(require_superadmin)):
    dominio = _dominio(dominio)
    res = await _ayudante("copia-restaurar", dominio, _copia(copia), tiempo=1800)
    await _auditar(r, admin, "sitio_copia_restaurar", dominio, {"id": copia, "previa": res.get("copia_previa")})
    return res


@router.delete("/{dominio}/copias/{copia}")
async def borrar(dominio: str, copia: str, r: Request, admin: dict = Depends(require_superadmin)):
    dominio = _dominio(dominio)
    res = await _ayudante("copia-borrar", dominio, _copia(copia))
    await _auditar(r, admin, "sitio_copia_borrar", dominio, {"id": copia})
    return res
