"""Panel RAG — dominios habilitados + ingesta/test. Admin.

Reusa el motor RAG del webmail vía subprocess. Autor: Wilson Argüello — Tecnología, Fundación Maquita.
"""
import json
import shlex
import asyncio
import subprocess

from fastapi import APIRouter, Request, Depends, HTTPException
from pydantic import BaseModel

from app.auth.dependencies import get_current_admin

router = APIRouter(prefix="/api/rag", tags=["rag"])
WEBMAIL = "/opt/maquita-webmail/backend"


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
def _db(r: Request):
    return r.app.state.db


async def _run(args, timeout=185):
    orden = [f"{WEBMAIL}/venv/bin/python", "-m", "app.rag.run"] + shlex.split(args)
    try:
        p = await asyncio.to_thread(subprocess.run, orden, cwd=_DIR_EJECUCION, env=_env_webmail(),
                                    capture_output=True, text=True, timeout=timeout)
    except Exception as e:
        return {"error": str(e)}
    out = (p.stdout or "").strip()
    i, j = out.find("{"), out.rfind("}")
    try:
        return json.loads(out[i:j + 1]) if i >= 0 else {"error": (p.stderr or out)[-300:]}
    except Exception:
        return {"error": (p.stderr or out)[-300:]}


@router.get("/domains")
async def domains(r: Request, a=Depends(get_current_admin)):
    rows = await _db(r).fetch("SELECT domain, enabled FROM rag_domains ORDER BY domain")
    indexed = await _db(r).fetchval("SELECT count(*) FROM rag_chunks") or 0
    users = await _db(r).fetchval("SELECT count(DISTINCT username) FROM rag_chunks") or 0
    return {"domains": [dict(x) for x in rows], "indexed_total": indexed, "users_indexed": users}


class DomReq(BaseModel):
    domain: str


@router.post("/domains")
async def add_domain(r: Request, body: DomReq, a=Depends(get_current_admin)):
    dom = (body.domain or "").strip().lower()
    if not dom or "." not in dom:
        raise HTTPException(400, "dominio inválido")
    await _db(r).execute("INSERT INTO rag_domains (domain, enabled) VALUES ($1, true) ON CONFLICT (domain) DO NOTHING", dom)
    return {"ok": True}


class ToggleReq(BaseModel):
    domain: str
    enabled: bool


@router.post("/domains/toggle")
async def toggle(r: Request, body: ToggleReq, a=Depends(get_current_admin)):
    await _db(r).execute("UPDATE rag_domains SET enabled=$1 WHERE domain=$2", body.enabled, body.domain)
    return {"ok": True}


class UserReq(BaseModel):
    user: str


@router.post("/ingest")
async def ingest(r: Request, body: UserReq, a=Depends(get_current_admin)):
    u = "".join(c for c in (body.user or "") if c.isalnum() or c in "@._-")
    if not u:
        raise HTTPException(400, "usuario inválido")
    return await _run(f"--user {shlex.quote(u)}")


class AskReq(BaseModel):
    user: str
    question: str


@router.post("/ask")
async def ask_test(r: Request, body: AskReq, a=Depends(get_current_admin)):
    u = "".join(c for c in (body.user or "") if c.isalnum() or c in "@._-")
    q = (body.question or "").strip()[:300]
    if not u or not q:
        raise HTTPException(400, "faltan datos")
    return await _run(f"--user {shlex.quote(u)} --ask {shlex.quote(q)}", timeout=60)
