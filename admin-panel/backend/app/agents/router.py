"""Panel Agentes — agentes autónomos con IA local (Agent 365). Admin.

Reusa el framework de agentes del webmail vía subprocess. Seguro: 'simulación'
por defecto; 'apply' solo cuando se pide explícito (y la política lo permita).

Autor: Wilson Argüello — Equipo de Tecnología, Fundación Maquita
"""
import json
import asyncio
import subprocess

from fastapi import APIRouter, Request, Depends, HTTPException
from pydantic import BaseModel

from app.auth.dependencies import get_current_admin

router = APIRouter(prefix="/api/agents", tags=["agents"])
WEBMAIL = "/opt/maquita-webmail/backend"


def _env_webmail() -> dict:
    """Entorno para ejecutar el motor del webmail: copia del entorno actual mas su
    .env, leido EN PYTHON.

    Antes esto se hacia con `bash -c "... set -a && . .env && set +a && ..."`, y
    se rompio en cuanto el .env gano valores con espacios y parentesis sin
    comillas: bash intentaba ejecutarlos y devolvia «command not found» y «syntax
    error near unexpected token», dejando el comando sin configuracion. Leerlo
    aqui evita el shell y el problema. Mismo patron que ya usa safeattach.
    """
    import os
    env = dict(os.environ)
    try:
        with open(os.path.join(WEBMAIL, ".env"), encoding="utf-8") as fh:
            for linea in fh:
                linea = linea.strip()
                if not linea or linea.startswith("#") or "=" not in linea:
                    continue
                k, v = linea.split("=", 1)
                env[k.strip()] = v.strip().strip('"').strip("'")
    except OSError:
        pass
    return env


async def _ejecutar(orden: list, timeout: int = 160):
    """Ejecuta el motor del webmail SIN shell: lista de argumentos y entorno propio."""
    try:
        return await asyncio.to_thread(
            subprocess.run, orden, cwd=WEBMAIL, env=_env_webmail(),
            capture_output=True, text=True, timeout=timeout)
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
    p = await _ejecutar(
        [f"{WEBMAIL}/venv/bin/python", "-c",
         "import json; from app.agents.runner import list_agents; print(json.dumps(list_agents()))"],
        timeout=30)
    data = _slice((p.stdout or "") if p else "", "[", "]")
    return {"agents": data or []}


class RunReq(BaseModel):
    name: str
    apply: bool = False
    user: str = ""


@router.post("/run")
async def run(r: Request, body: RunReq, a=Depends(get_current_admin)):
    name = "".join(c for c in body.name if c.isalnum() or c in "_-")
    if not name:
        raise HTTPException(400, "agente inválido")
    flag = "--apply" if body.apply else ""
    u = "".join(c for c in (body.user or "") if c.isalnum() or c in "@._-")
    uflag = f"--user {u}" if u else ""
    orden = [f"{WEBMAIL}/venv/bin/python", "-m", "app.agents.run", name]
    if flag:
        orden.append(flag)
    if u:
        orden += ["--user", u]
    p = await _ejecutar(orden)
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
