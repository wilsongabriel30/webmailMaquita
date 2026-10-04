"""
Geo-acceso: control de qué países pueden acceder al webmail/IMAP/submission.
Default: solo Ecuador. El admin abre/cierra países (p. ej. cuando alguien viaja).
La red interna y el VPN siempre tienen acceso (no dependen de esta lista).
Autor: Wilson Argüello — Equipo de Tecnología, Fundación Maquita
"""
import asyncio
import re
from fastapi import APIRouter, Request, Depends, HTTPException
from pydantic import BaseModel
from app.auth.dependencies import get_current_admin, require_superadmin

router = APIRouter(prefix="/api/geo-access", tags=["geo-access"])
from app import organizacion
from app.wrappers.privilegios import con_sudo

SCRIPT = "/usr/local/sbin/geoip-country.sh"
_CC_RE = re.compile(r"^[a-z]{2}$")


def _db(r: Request):
    return r.app.state.db


@router.get("/countries")
async def list_countries(r: Request, a=Depends(get_current_admin)):
    rows = await _db(r).fetch(
        "SELECT code, name, enabled, updated_by, updated_at "
        "FROM geo_webmail_countries ORDER BY name")
    return {"countries": [dict(x) for x in rows]}


class ToggleReq(BaseModel):
    code: str
    enabled: bool


@router.post("/toggle")
async def toggle(r: Request, body: ToggleReq, a=Depends(require_superadmin)):
    code = (body.code or "").lower().strip()
    if not _CC_RE.match(code):
        raise HTTPException(400, "Código de país inválido (ISO-2, ej. 'es')")
    base = (organizacion.valor("ORG_PAIS_BASE", "ec") or "ec").lower()
    if code == base and not body.enabled:
        raise HTTPException(400, "El país base no se puede cerrar")
    action = "enable" if body.enabled else "disable"
    # El guion toca nftables (root) y el panel corre sin privilegios: va por maquita-sudo, que
    # valida la acción y el código de país.
    proc = await asyncio.create_subprocess_exec(
        *con_sudo(SCRIPT, action, code),
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    try:
        out, err = await asyncio.wait_for(proc.communicate(), timeout=90)
    except asyncio.TimeoutError:
        proc.kill()
        raise HTTPException(504, "El cambio tardó demasiado (descarga de rangos)")
    if proc.returncode != 0:
        raise HTTPException(500, (err or out).decode("utf-8", "replace")[-300:])
    return {"ok": True, "code": code, "action": action}
