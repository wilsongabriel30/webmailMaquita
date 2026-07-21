"""
Proteccion de Salida (panel admin): limites, actividad y recuperacion de cuentas
bloqueadas. Llama al helper privilegiado /usr/local/sbin/maquita-outbound.
El backend admin corre como root, por eso invoca el helper directamente.
Autor: Wilson Arguello — Equipo de Tecnologia, Fundacion Maquita.
"""
import asyncio, json
from fastapi import APIRouter, Request, Depends, HTTPException
from pydantic import BaseModel
from app.auth.dependencies import get_current_admin

router = APIRouter(prefix="/api/admin/outbound", tags=["outbound"])
HELPER = "/usr/local/sbin/maquita-outbound"


async def _run(*args: str) -> dict:
    proc = await asyncio.create_subprocess_exec(
        HELPER, *args,
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    out, e = await asyncio.wait_for(proc.communicate(), timeout=90)
    txt = (out or b"").decode().strip()
    try:
        data = json.loads(txt) if txt else {}
    except json.JSONDecodeError:
        raise HTTPException(500, txt or (e or b"").decode().strip() or "salida invalida")
    if isinstance(data, dict) and data.get("error"):
        raise HTTPException(400, data["error"])
    return data


@router.get("/limits")
async def limits(r: Request, a=Depends(get_current_admin)):
    return await _run("get-limits")


class LimitsReq(BaseModel):
    burst: int
    rate_per_min: int
    whitelist: list[str] | None = None


@router.put("/limits")
async def set_limits(body: LimitsReq, r: Request, a=Depends(get_current_admin)):
    res = await _run("set-limits", str(body.burst), str(body.rate_per_min))
    if body.whitelist is not None:
        await _run("set-whitelist", ",".join(body.whitelist))
    return res


@router.get("/activity")
async def activity(r: Request, hours: int = 1, a=Depends(get_current_admin)):
    return await _run("activity", str(hours))


class EmailReq(BaseModel):
    email: str


@router.post("/lock")
async def lock(body: EmailReq, r: Request, a=Depends(get_current_admin)):
    return await _run("lock", body.email)


@router.post("/unlock")
async def unlock(body: EmailReq, r: Request, a=Depends(get_current_admin)):
    return await _run("unlock", body.email)


@router.get("/status/{email}")
async def status(email: str, r: Request, a=Depends(get_current_admin)):
    return await _run("status", email)
