"""Despliegue desde git de los sitios PHP y CPU y memoria por sitio (v1.11), en el panel general.

Las mismas órdenes que usa el portal de cada cliente (deploy/sitios/lib/git_sitio.py, git_despliegue.py y
recursos.py), por maquita-sudo. El despliegue corre en segundo plano en el servidor: «Desplegar» vuelve enseguida y
la pantalla consulta el estado. El secreto del gancho vuelve una sola vez y no va a la auditoría.
"""

import base64
import json
import re

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from app.auth.dependencies import get_current_admin, require_superadmin
from app.sitios.router import _auditar, _ayudante, _dominio

router = APIRouter(prefix="/api/sitios", tags=["sitios"])
RE_VERSION = re.compile(r"^\d{8}-\d{6}$")


@router.get("/{dominio}/recursos")
async def recursos(dominio: str, admin: dict = Depends(get_current_admin)):
    return await _ayudante("recursos", _dominio(dominio))


@router.get("/{dominio}/git")
async def git_estado(dominio: str, admin: dict = Depends(get_current_admin)):
    return await _ayudante("git-estado", _dominio(dominio))


class ConfGit(BaseModel):
    repo: str
    rama: str = "main"
    carpeta: str = ""
    raiz_web: str = ""
    exclusiones: list[str] = []


@router.put("/{dominio}/git")
async def git_configurar(dominio: str, body: ConfGit, r: Request, admin: dict = Depends(require_superadmin)):
    dominio = _dominio(dominio)
    if len(body.exclusiones) > 20:
        raise HTTPException(400, "Se admiten hasta 20 archivos o carpetas que el despliegue no toca")
    datos = {k: v.strip() if isinstance(v, str) else [e.strip() for e in v if e.strip()] for k, v in body.model_dump().items()}
    texto = base64.urlsafe_b64encode(json.dumps(datos, ensure_ascii=False).encode()).decode().rstrip("=")
    if len(texto) > 8000:
        raise HTTPException(400, "Configuración demasiado larga")
    res = await _ayudante("git-configurar", dominio, texto, tiempo=120)
    await _auditar(r, admin, "sitio_git_configurar", dominio, {"repo": datos["repo"], "rama": datos["rama"]})
    return res


@router.post("/{dominio}/git/clave")
async def git_clave(dominio: str, r: Request, admin: dict = Depends(require_superadmin)):
    dominio = _dominio(dominio)
    res = await _ayudante("git-clave", dominio)
    await _auditar(r, admin, "sitio_git_clave", dominio)
    return res


class Accion(BaseModel):
    accion: str


@router.post("/{dominio}/git/gancho")
async def git_gancho(dominio: str, body: Accion, r: Request, admin: dict = Depends(require_superadmin)):
    dominio = _dominio(dominio)
    if body.accion not in ("activar", "desactivar"):
        raise HTTPException(400, "Acción no válida")
    res = await _ayudante("git-gancho", dominio, body.accion)
    await _auditar(r, admin, f"sitio_git_gancho_{body.accion}", dominio)
    return res


@router.post("/{dominio}/git/desplegar", status_code=202)
async def git_desplegar(dominio: str, r: Request, admin: dict = Depends(require_superadmin)):
    dominio = _dominio(dominio)
    res = await _ayudante("git-desplegar", dominio, "panel")
    await _auditar(r, admin, "sitio_git_desplegar", dominio)
    return res


class Version(BaseModel):
    version: str


@router.post("/{dominio}/git/volver")
async def git_volver(dominio: str, body: Version, r: Request, admin: dict = Depends(require_superadmin)):
    dominio = _dominio(dominio)
    if not RE_VERSION.match(body.version):
        raise HTTPException(400, "Versión no válida")
    res = await _ayudante("git-volver", dominio, body.version, tiempo=1200)
    await _auditar(r, admin, "sitio_git_volver", dominio, {"version": body.version})
    return res


class Confirmacion(BaseModel):
    confirmacion: str


@router.delete("/{dominio}/git")
async def git_quitar(dominio: str, body: Confirmacion, r: Request, admin: dict = Depends(require_superadmin)):
    dominio = _dominio(dominio)
    if (body.confirmacion or "").strip().lower() != dominio:
        raise HTTPException(400, "Escriba el dominio para confirmar")
    res = await _ayudante("git-quitar", dominio, dominio, tiempo=300)
    await _auditar(r, admin, "sitio_git_quitar", dominio)
    return res
