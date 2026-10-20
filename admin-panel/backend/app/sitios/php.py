"""Versiones de PHP y extensiones («Avanzado» → PHP): instalar otra versión, pasar un sitio a ella e instalar
extensiones. Las versiones distintas de la de Debian vienen del repositorio de Ondřej Surý (packages.sury.org)."""

import re

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from app.auth.dependencies import require_superadmin
from app.sitios.router import _auditar, _ayudante, _dominio

router = APIRouter(prefix="/api/sitios", tags=["sitios"])
RE_VERSION = re.compile(r"^[578]\.[0-9]$")
RE_EXTENSION = re.compile(r"^[a-z0-9]{2,20}$")


def _version(v: str) -> str:
    if not RE_VERSION.match(v or ""):
        raise HTTPException(400, "Versión de PHP no válida")
    return v


@router.get("/php")
async def estado(admin: dict = Depends(require_superadmin)):
    return await _ayudante("php-estado", tiempo=180)


@router.get("/{dominio}/php")
async def estado_sitio(dominio: str, admin: dict = Depends(require_superadmin)):
    return await _ayudante("php-estado", _dominio(dominio), tiempo=180)


@router.post("/php/repositorio")
async def activar_repositorio(r: Request, admin: dict = Depends(require_superadmin)):
    res = await _ayudante("php-repositorio", tiempo=900)
    await _auditar(r, admin, "php_repositorio", "packages.sury.org", {})
    return res


@router.post("/php/versiones/{version}")
async def instalar_version(version: str, r: Request, admin: dict = Depends(require_superadmin)):
    res = await _ayudante("php-instalar", _version(version), tiempo=1200)
    await _auditar(r, admin, "php_instalar", version, {})
    return res


@router.get("/php/versiones/{version}/extensiones")
async def extensiones(version: str, admin: dict = Depends(require_superadmin)):
    return await _ayudante("php-extensiones", _version(version), tiempo=180)


class Extension(BaseModel):
    accion: str  # instalar | quitar


@router.post("/php/versiones/{version}/extensiones/{extension}")
async def extension(version: str, extension: str, body: Extension, r: Request, admin: dict = Depends(require_superadmin)):
    if not RE_EXTENSION.match(extension) or body.accion not in ("instalar", "quitar"):
        raise HTTPException(400, "Extensión o acción no válida")
    res = await _ayudante("php-extension", _version(version), extension, body.accion, tiempo=900)
    await _auditar(r, admin, f"php_extension_{body.accion}", version, {"extension": extension})
    return res


class Version(BaseModel):
    version: str


@router.put("/{dominio}/php")
async def cambiar_version(dominio: str, body: Version, r: Request, admin: dict = Depends(require_superadmin)):
    dominio = _dominio(dominio)
    res = await _ayudante("php-version", dominio, _version(body.version), tiempo=300)
    await _auditar(r, admin, "sitio_php_version", dominio, {"version": body.version})
    return res
