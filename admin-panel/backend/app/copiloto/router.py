"""Panel Copiloto Maquita — Q&A de seguridad con IA local. Admin.

Reusa el copiloto del webmail (grounded en datos reales) vía subprocess.

Autor: Wilson Argüello — Equipo de Tecnología, Fundación Maquita
"""
import json
import shlex
import subprocess

from fastapi import APIRouter, Request, Depends, HTTPException
from pydantic import BaseModel

from app.auth.dependencies import get_current_admin

router = APIRouter(prefix="/api/copiloto", tags=["copiloto"])
WEBMAIL = "/opt/maquita-webmail/backend"


class AskReq(BaseModel):
    question: str
    days: int = 7


@router.post("/ask")
async def ask(r: Request, body: AskReq, a=Depends(get_current_admin)):
    q = (body.question or "").strip()[:500]
    if not q:
        raise HTTPException(400, "pregunta vacía")
    days = max(1, min(body.days, 90))
    cmd = (f"cd {WEBMAIL} && set -a && . .env && set +a && "
           f"venv/bin/python -m app.copiloto.run {shlex.quote(q)} {days}")
    try:
        p = subprocess.run(["bash", "-c", cmd], capture_output=True, text=True, timeout=120)
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
