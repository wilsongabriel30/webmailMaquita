"""Panel Copiloto Maquita — Q&A de seguridad con IA local. Admin.

Reusa el copiloto del webmail (grounded en datos reales) vía subprocess.

Autor: Wilson Argüello — Equipo de Tecnología, Fundación Maquita
"""
import json
import shlex
import asyncio
import subprocess

from fastapi import APIRouter, Request, Depends, HTTPException
from pydantic import BaseModel

from app.auth.dependencies import get_current_admin

router = APIRouter(prefix="/api/copiloto", tags=["copiloto"])
WEBMAIL = "/opt/maquita-webmail/backend"


class AskReq(BaseModel):
    question: str
    days: int = 7


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


@router.post("/ask")
async def ask(r: Request, body: AskReq, a=Depends(get_current_admin)):
    q = (body.question or "").strip()[:500]
    if not q:
        raise HTTPException(400, "pregunta vacía")
    days = max(1, min(body.days, 90))
    orden = [f"{WEBMAIL}/venv/bin/python", "-m", "app.copiloto.run", q, str(days)]
    try:
        p = await asyncio.to_thread(subprocess.run, orden, cwd=WEBMAIL, env=_env_webmail(),
                                    capture_output=True, text=True, timeout=120)
    except Exception as e:
        raise HTTPException(500, str(e))
    out = (p.stdout or "").strip()
    i, j = out.find("{"), out.rfind("}")
    try:
        res = json.loads(out[i:j + 1]) if i >= 0 else {"error": (p.stderr or "")[-400:]}
    except Exception:
        res = {"error": (p.stderr or out)[-400:]}
    try:
        await r.app.state.db.execute(
            "INSERT INTO admin_audit (admin_id, admin_username, action, target, ip_address) "
            "VALUES ($1,$2,$3,$4,$5)", a["id"], a["username"], "copiloto_ask", q[:120],
            r.headers.get("X-Real-IP", r.client.host if r.client else ""))
    except Exception:
        pass
    return res
