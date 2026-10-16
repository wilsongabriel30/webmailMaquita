"""Cortafuegos del servidor (panel → Protección → Cortafuegos), sobre iptables.

Servicios con su origen (todos, solo administración, cerrado), IP de administración, puertos
adicionales para aplicaciones propias, bloqueos manuales e IP bloqueadas por fail2ban. Cada cambio se
aplica con vuelta atrás automática a los 60 s si no se confirma, y no se acepta una configuración que
cierre el panel a la IP desde la que se está usando.
"""

import re

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from app.auth.dependencies import get_current_admin, require_superadmin
from app.dns.ayudante import auditar, ayudante, b64

router = APIRouter(prefix="/api/cortafuegos", tags=["cortafuegos"])
RE_IP = re.compile(r"^[0-9a-fA-F:.]{2,45}$")


def _ip_cliente(r: Request) -> str:
    ip = (r.headers.get("X-Real-IP") or (r.client.host if r.client else "")).strip()
    if not RE_IP.match(ip):
        raise HTTPException(400, "No se pudo determinar su IP")
    return ip


@router.get("")
async def estado(r: Request, admin: dict = Depends(get_current_admin)):
    datos = await ayudante("cortafuegos", "estado")
    datos["su_ip"] = _ip_cliente(r)
    return datos


class Config(BaseModel):
    servicios: dict[str, str]
    admin: list[str]
    extras: list[dict] = []
    bloqueados: list[dict] = []


@router.put("")
async def aplicar(body: Config, r: Request, admin: dict = Depends(require_superadmin)):
    ip = _ip_cliente(r)
    res = await ayudante("cortafuegos", "aplicar", b64(body.model_dump()), ip)
    await auditar(r, admin, "cortafuegos_aplicar", "servidor", {"desde": ip, "config": body.model_dump()})
    return res


@router.post("/confirmar")
async def confirmar(r: Request, admin: dict = Depends(require_superadmin)):
    res = await ayudante("cortafuegos", "confirmar")
    await auditar(r, admin, "cortafuegos_confirmar", "servidor")
    return res


@router.post("/deshacer")
async def deshacer(r: Request, admin: dict = Depends(require_superadmin)):
    res = await ayudante("cortafuegos", "revertir")
    await auditar(r, admin, "cortafuegos_deshacer", "servidor")
    return res


class Desbloqueo(BaseModel):
    jaula: str
    ip: str


@router.post("/desbloquear")
async def desbloquear(body: Desbloqueo, r: Request, admin: dict = Depends(require_superadmin)):
    res = await ayudante("cortafuegos", "desbloquear", body.jaula, body.ip)
    await auditar(r, admin, "cortafuegos_desbloquear", body.ip, {"jaula": body.jaula})
    return res
