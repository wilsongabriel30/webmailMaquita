"""Respaldos del servidor (panel → Protección → Respaldos).

Restic, cifrado con la clave de recuperación del servidor: repositorio local y, opcional, un destino externo
(SFTP, REST, S3 o carpeta montada). Desde aquí: estado e instantáneas, respaldar ahora, retención y destino,
ver la clave de recuperación (para guardarla fuera), restaurar un sitio web o un buzón, y comprobar los
respaldos. Las operaciones largas las lanza el ayudante root maquita-respaldos en segundo plano.
"""

import re

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from app.auth.dependencies import get_current_admin, require_superadmin
from app.dns.ayudante import auditar, ayudante, b64

router = APIRouter(prefix="/api/respaldos", tags=["respaldos"])
RE_INSTANTANEA = re.compile(r"^[0-9a-f]{8,64}$")
RE_DOMINIO = re.compile(r"^(?=.{4,200}$)([a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}$")
RE_CORREO = re.compile(r"^[a-z0-9][a-z0-9._+-]{0,63}@([a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}$")


@router.get("")
async def estado(admin: dict = Depends(get_current_admin)):
    return await ayudante("respaldos", "estado", tiempo=120)


@router.post("/respaldar")
async def respaldar(r: Request, admin: dict = Depends(require_superadmin)):
    res = await ayudante("respaldos", "respaldar")
    await auditar(r, admin, "respaldo_manual", "servidor")
    return res


@router.post("/comprobar")
async def comprobar(r: Request, admin: dict = Depends(require_superadmin)):
    res = await ayudante("respaldos", "comprobar")
    await auditar(r, admin, "respaldo_comprobar", "servidor")
    return res


class Config(BaseModel):
    automatico: bool = True
    conservar: dict[str, int] = {}
    destino: dict[str, str] = {}
    credenciales: dict[str, str] | None = None  # S3 / REST; no se devuelven nunca


@router.put("/config")
async def config(body: Config, r: Request, admin: dict = Depends(require_superadmin)):
    datos = body.model_dump(exclude={"credenciales"})
    res = await ayudante("respaldos", "config", b64(datos))
    if body.credenciales is not None:
        await ayudante("respaldos", "credenciales", b64(body.credenciales))
    await auditar(r, admin, "respaldo_config", "servidor", {**datos, "credenciales": sorted(body.credenciales or {})})
    return res


@router.post("/clave")
async def clave(r: Request, admin: dict = Depends(require_superadmin)):
    """Clave de recuperación (para guardarla FUERA del servidor) y clave SSH pública (para el destino SFTP)."""
    res = await ayudante("respaldos", "clave")
    await auditar(r, admin, "respaldo_ver_clave", "servidor")
    return res


class Restaurar(BaseModel):
    tipo: str  # sitio | buzon
    objeto: str
    instantanea: str


@router.post("/restaurar")
async def restaurar(body: Restaurar, r: Request, admin: dict = Depends(require_superadmin)):
    objeto = (body.objeto or "").strip().lower()
    if not RE_INSTANTANEA.match(body.instantanea):
        raise HTTPException(400, "Instantánea no válida")
    if body.tipo == "sitio" and RE_DOMINIO.match(objeto):
        orden = "restaurar-sitio"
    elif body.tipo == "buzon" and RE_CORREO.match(objeto):
        orden = "restaurar-buzon"
    else:
        raise HTTPException(400, "Indique un sitio o un buzón válido")
    res = await ayudante("respaldos", orden, objeto, body.instantanea)
    await auditar(r, admin, f"respaldo_{orden.replace('-', '_')}", objeto, {"instantanea": body.instantanea})
    return res
