"""Actualizaciones del servidor (panel → Protección → Actualizaciones).

El código viene del repositorio: canal «estable» (etiquetas vX.Y.Z firmadas por el equipo) o, solo en
servidores de prueba, una rama. La instalación la hace el ayudante root maquita-actualizar en segundo
plano (respaldo, migraciones, dependencias, frontends, validación y vuelta atrás si algo empeora); aquí
solo se consulta, se lanza y se configura.
"""

import re

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from app.auth.dependencies import get_current_admin, require_superadmin
from app.dns.ayudante import auditar, ayudante, b64

router = APIRouter(prefix="/api/actualizaciones", tags=["actualizaciones"])
RE_REF = re.compile(r"^(?:v\d{1,4}\.\d{1,4}\.\d{1,4}|origin/[A-Za-z0-9][A-Za-z0-9._/-]{0,99})$")


@router.get("")
async def estado(admin: dict = Depends(get_current_admin)):
    return await ayudante("actualizar", "estado")


@router.post("/buscar")
async def buscar(admin: dict = Depends(get_current_admin)):
    return await ayudante("actualizar", "buscar", tiempo=300)


class Aplicar(BaseModel):
    ref: str


@router.post("/aplicar")
async def aplicar(body: Aplicar, r: Request, admin: dict = Depends(require_superadmin)):
    if not RE_REF.match(body.ref) or ".." in body.ref:
        raise HTTPException(400, "Versión no válida")
    res = await ayudante("actualizar", "aplicar", body.ref, tiempo=120)
    await auditar(r, admin, "actualizacion_aplicar", "servidor", {"ref": body.ref})
    return res


class Config(BaseModel):
    canal: str = "estable"
    automatico: bool = True


@router.put("/config")
async def config(body: Config, r: Request, admin: dict = Depends(require_superadmin)):
    res = await ayudante("actualizar", "config", b64(body.model_dump()))
    await auditar(r, admin, "actualizacion_config", "servidor", body.model_dump())
    return res
