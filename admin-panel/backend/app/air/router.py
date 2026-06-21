"""Panel AIR — investigación y respuesta automática (admin).

Lee los incidentes que registra el motor AIR del webmail (tabla threat_actions),
permite 'investigar ahora' (corre el motor con triage Qwen) y contener cuentas.

Autor: Wilson Argüello — Equipo de Tecnología, Fundación Maquita
"""
import subprocess

from fastapi import APIRouter, Request, Depends, HTTPException
from pydantic import BaseModel

from app.auth.dependencies import get_current_admin

router = APIRouter(prefix="/api/air", tags=["air"])
WEBMAIL = "/opt/maquita-webmail/backend"


def _db(r: Request):
    return r.app.state.db


def _sev(action: str) -> str:
    a = action or ""
    if a == "account_locked" or "high" in a:
        return "high"
    if "medium" in a:
        return "medium"
    return "low"


@router.get("/incidents")
async def incidents(request: Request, hours: int = 168,
                    admin: dict = Depends(get_current_admin)):
    rows = await _db(request).fetch(
        "SELECT id, action, target, detail, auto, created_at FROM threat_actions "
        "WHERE actor='AIR' AND created_at > now() - ($1||' hours')::interval "
        "ORDER BY created_at DESC LIMIT 200", str(hours))
    inc = [{"id": r["id"], "action": r["action"], "username": r["target"],
            "detail": r["detail"], "auto": r["auto"], "severity": _sev(r["action"]),
            "created_at": r["created_at"].isoformat() if r["created_at"] else None}
           for r in rows]
    return {"count": len(inc), "incidents": inc}


@router.post("/investigate")
async def investigate(request: Request, hours: int = 24,
                      admin: dict = Depends(get_current_admin)):
    try:
        p = subprocess.run(
            ["bash", "-c",
             f"cd {WEBMAIL} && set -a && . .env && set +a && "
             f"venv/bin/python -m app.air.run {int(hours)}"],
            capture_output=True, text=True, timeout=150)
        return {"ok": p.returncode == 0, "output": (p.stdout or p.stderr or "")[-4000:]}
    except Exception as e:
        raise HTTPException(500, f"No se pudo investigar: {e}")


class LockReq(BaseModel):
    username: str


@router.post("/lock")
async def lock(request: Request, body: LockReq,
               admin: dict = Depends(get_current_admin)):
    u = (body.username or "").strip().lower()
    if not u:
        raise HTTPException(400, "username requerido")
    await _db(request).execute("UPDATE mailbox SET active=false WHERE username=$1", u)
    await _db(request).execute(
        "INSERT INTO threat_actions(action,target,detail,actor,auto,created_at) "
        "VALUES('account_locked',$1,$2,$3,false,now())",
        u, f"contención manual desde panel por {admin['username']}", admin["username"])
    return {"locked": True, "username": u}
