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


from app.wrappers.entorno_webmail import DIRECTORIO_EJECUCION as _DIR_EJECUCION


def _env_webmail() -> dict:
    """Entorno para los subprocesos del correo.

    Antes abria entero el .env del correo (46 variables, con todos sus secretos).
    Desde la fase 2 el panel no corre como root y no puede leer ese archivo: los
    valores que hacen falta, y solo esos, se copian a la configuracion del panel
    con prefijo WEBMAIL_. Ver wrappers/entorno_webmail.py.
    """
    from app.wrappers.entorno_webmail import entorno_webmail
    return entorno_webmail()
@router.post("/ask")
async def ask(r: Request, body: AskReq, a=Depends(get_current_admin)):
    q = (body.question or "").strip()[:500]
    if not q:
        raise HTTPException(400, "pregunta vacía")
    days = max(1, min(body.days, 90))
    orden = [f"{WEBMAIL}/venv/bin/python", "-m", "app.copiloto.run", q, str(days)]
    try:
        p = await asyncio.to_thread(subprocess.run, orden, cwd=_DIR_EJECUCION, env=_env_webmail(),
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
