"""Panel Agentes — agentes autónomos con IA local (Agent 365). Admin.

Reusa el framework de agentes del webmail vía subprocess. Seguro: 'simulación'
por defecto; 'apply' solo cuando se pide explícito (y la política lo permita).

Autor: Wilson Argüello — Equipo de Tecnología, Fundación Maquita
"""
import json
import subprocess

from fastapi import APIRouter, Request, Depends, HTTPException
from pydantic import BaseModel

from app.auth.dependencies import get_current_admin

router = APIRouter(prefix="/api/agents", tags=["agents"])
WEBMAIL = "/opt/maquita-webmail/backend"


def _sh(cmd: str, timeout: int = 160):
    try:
        return subprocess.run(["bash", "-c", cmd], capture_output=True, text=True, timeout=timeout)
    except Exception:
        return None


def _slice(out: str, op: str, cl: str):
    i, j = out.find(op), out.rfind(cl)
    if i >= 0 and j > i:
        try:
            return json.loads(out[i:j + 1])
        except Exception:
            return None
    return None


@router.get("/list")
async def list_agents(r: Request, a=Depends(get_current_admin)):
    p = _sh(f'cd {WEBMAIL} && set -a && . .env && set +a && venv/bin/python -c '
            f'"import json; from app.agents.runner import list_agents; print(json.dumps(list_agents()))"',
            timeout=30)
    data = _slice((p.stdout or "") if p else "", "[", "]")
    return {"agents": data or []}


class RunReq(BaseModel):
    name: str
    apply: bool = False


@router.post("/run")
async def run(r: Request, body: RunReq, a=Depends(get_current_admin)):
    name = "".join(c for c in body.name if c.isalnum() or c in "_-")
    if not name:
        raise HTTPException(400, "agente inválido")
    flag = "--apply" if body.apply else ""
    p = _sh(f'cd {WEBMAIL} && set -a && . .env && set +a && '
            f'venv/bin/python -m app.agents.run {name} {flag}')
    if not p:
        raise HTTPException(500, "No se pudo ejecutar el agente")
    res = _slice(p.stdout or "", "{", "}") or {"error": (p.stderr or p.stdout or "")[-600:]}
    try:
        await r.app.state.db.execute(
            "INSERT INTO admin_audit (admin_id, admin_username, action, target, ip_address) "
            "VALUES ($1,$2,$3,$4,$5)", a["id"], a["username"], "agent_run",
            f"{name}{' apply' if body.apply else ''}",
            r.headers.get("X-Real-IP", r.client.host if r.client else ""))
    except Exception:
        pass
    return res
