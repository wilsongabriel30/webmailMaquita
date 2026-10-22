"""Fichas de API del panel general: crearlas (con alcance y caducidad), verlas y revocarlas.

- Se muestra UNA vez al crearla; se guarda su hash (SHA-256) y sus primeros caracteres para reconocerla.
- Solo la crea una sesión abierta con segundo factor y con un código nuevo de él (quien robe una sesión no saca una
  llave de un año), de un superadministrador o administrador. Con una ficha no se llega aquí (alcance.py).
- La revoca su dueño o un superadministrador. Todo queda en la auditoría.
"""

import json
import re
import secrets
from datetime import datetime, timedelta, timezone

import pyotp
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from app.auth.dependencies import _hash, get_current_admin
from app.fichas_api import alcance

router = APIRouter(prefix="/api/fichas-api", tags=["fichas-api"])
_CONTROL = re.compile(r"[\x00-\x1f\x7f<>]")


class NuevaFicha(BaseModel):
    nombre: str
    alcances: list[str]
    dias: int
    codigo: str = ""


async def _auditar(r: Request, admin: dict, accion: str, objetivo: str, detalles: str | None = None):
    await r.app.state.db.execute(
        "INSERT INTO admin_audit (admin_id, admin_username, action, target, details, ip_address) "
        "VALUES ($1, $2, $3, $4, $5::jsonb, $6)",
        admin["id"], admin["username"], accion, objetivo[:255], detalles,
        r.headers.get("X-Real-IP", r.client.host if r.client else "")[:45])


def _fila(f) -> dict:
    return {"id": f["id"], "nombre": f["nombre"], "prefijo": f["prefijo"], "alcances": list(f["alcances"] or []),
            "usuario": f["username"], "creada": f["created_at"].isoformat() if f["created_at"] else None,
            "vence": f["expires_at"].isoformat() if f["expires_at"] else None,
            "ultimo_uso": f["last_used_at"].isoformat() if f["last_used_at"] else None,
            "revocada": f["revoked_at"] is not None}


@router.get("")
async def listar(request: Request, admin: dict = Depends(get_current_admin)):
    """Las propias; el superadministrador ve también las de los demás (para revocarlas)."""
    todas = admin["role"] == "superadmin"
    filas = await request.app.state.db.fetch(
        """SELECT f.id, f.nombre, f.prefijo, f.alcances, f.created_at, f.expires_at, f.last_used_at, f.revoked_at,
                  u.username
             FROM admin_fichas_api f JOIN admin_users u ON u.id = f.user_id
            WHERE $2 OR f.user_id = $1 ORDER BY f.created_at DESC LIMIT 200""", admin["id"], todas)
    return {"fichas": [_fila(f) for f in filas], "areas": {k: v[0] for k, v in alcance.AREAS.items()},
            "dias_maximos": alcance.DIAS_MAXIMOS, "maximo": alcance.MAXIMO_POR_CUENTA}


@router.post("", status_code=201)
async def crear(body: NuevaFicha, request: Request, admin: dict = Depends(get_current_admin)):
    if admin.get("ficha_api"):
        raise HTTPException(403, "Una ficha de API no puede crear otras")
    if admin["role"] not in ("superadmin", "admin"):
        raise HTTPException(403, "Tu rol no puede crear fichas de API")
    if not admin.get("totp"):
        raise HTTPException(403, "Para crear fichas de API, entra con el segundo factor activado")
    nombre = (body.nombre or "").strip()
    if not 1 <= len(nombre) <= 80 or _CONTROL.search(nombre):
        raise HTTPException(400, "Ponle un nombre de 1 a 80 caracteres (sin < ni >) para reconocerla")
    alcances = alcance.validar_alcances(body.alcances)
    if alcances is None:
        raise HTTPException(400, "Elige el alcance: lectura y, si hace falta, las áreas donde podrá hacer cambios")
    if not 1 <= body.dias <= alcance.DIAS_MAXIMOS:
        raise HTTPException(400, f"La caducidad va de 1 a {alcance.DIAS_MAXIMOS} días")
    db = request.app.state.db
    secreto = await db.fetchval("SELECT totp_secret FROM admin_users WHERE id = $1 AND totp_enabled", admin["id"])
    if not secreto or not pyotp.TOTP(secreto).verify(str(body.codigo or "").strip(), valid_window=1):
        await _auditar(request, admin, "ficha_api_codigo_fallido", nombre)
        raise HTTPException(400, "Escribe un código nuevo de tu aplicación de segundo factor")
    activas = await db.fetchval(
        "SELECT count(*) FROM admin_fichas_api WHERE user_id = $1 AND revoked_at IS NULL AND expires_at > NOW()", admin["id"])
    if (activas or 0) >= alcance.MAXIMO_POR_CUENTA:
        raise HTTPException(409, f"Como máximo {alcance.MAXIMO_POR_CUENTA} fichas activas: revoca alguna antes")
    ficha = alcance.PREFIJO + secrets.token_urlsafe(32)
    vence = datetime.now(timezone.utc) + timedelta(days=body.dias)
    ident = await db.fetchval(
        """INSERT INTO admin_fichas_api (user_id, nombre, prefijo, token_hash, alcances, expires_at)
           VALUES ($1, $2, $3, $4, $5, $6) RETURNING id""",
        admin["id"], nombre, ficha[:12], _hash(ficha), alcances, vence)
    await _auditar(request, admin, "ficha_api_crear", nombre, json.dumps({"id": ident, "alcances": alcances, "dias": body.dias}))
    return {"id": ident, "ficha": ficha, "nombre": nombre, "alcances": alcances, "vence": vence.isoformat(),
            "aviso": "Cópiala ahora: no se vuelve a mostrar. Úsala en la cabecera «Authorization: Bearer …»."}


@router.delete("/{ident}")
async def revocar(ident: int, request: Request, admin: dict = Depends(get_current_admin)):
    if admin.get("ficha_api"):
        raise HTTPException(403, "Una ficha de API no puede revocar fichas")
    hecho = await request.app.state.db.fetchval(
        """UPDATE admin_fichas_api SET revoked_at = NOW()
            WHERE id = $1 AND revoked_at IS NULL AND (user_id = $2 OR $3) RETURNING id""",
        ident, admin["id"], admin["role"] == "superadmin")
    if not hecho:
        raise HTTPException(404, "No encontrada")
    await _auditar(request, admin, "ficha_api_revocar", str(ident))
    return {"ok": True}
