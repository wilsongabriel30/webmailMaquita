"""Drive (Almacén) desde el panel: vincular un buzón a una persona del directorio y fijar su cuota.

El panel no tiene acceso a la base del Almacén (D-2): le pide las cosas por loopback con un
secreto compartido (`ALMACEN_SECRETO_PANEL`, cabecera `X-Almacen-Panel`). Ver
`almacen/servicio/api_panel.py`.
"""
import os

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request

from app.auth.dependencies import get_current_admin, require_role

router = APIRouter(prefix="/api/drive", tags=["drive"])

ALMACEN_URL = os.getenv("ALMACEN_URL", "http://127.0.0.1:8788").rstrip("/")
SECRETO = os.getenv("ALMACEN_SECRETO_PANEL", "")


def _db(r: Request):
    return r.app.state.db


async def _llamar(metodo: str, ruta: str, **kw) -> dict:
    if not SECRETO:
        raise HTTPException(503, "El canal con el Almacén no está configurado (ALMACEN_SECRETO_PANEL)")
    try:
        async with httpx.AsyncClient(timeout=15.0) as c:
            r = await c.request(metodo, f"{ALMACEN_URL}/api/almacen/panel{ruta}", headers={"X-Almacen-Panel": SECRETO}, **kw)
    except httpx.HTTPError as e:
        raise HTTPException(502, f"El Almacén no responde ({type(e).__name__})")
    try:
        datos = r.json()
    except ValueError:
        raise HTTPException(502, f"Respuesta inesperada del Almacén ({r.status_code})")
    if r.status_code >= 400 or not datos.get("success", True):
        raise HTTPException(r.status_code if r.status_code >= 400 else 400, datos.get("error", "Error del Almacén"))
    return datos


async def _audit(r, a, action, target=None):
    await _db(r).execute(
        "INSERT INTO admin_audit (admin_id, admin_username, action, target, ip_address) VALUES ($1,$2,$3,$4,$5)",
        a["id"], a["username"], action, target, r.headers.get("X-Real-IP", r.client.host if r.client else ""))


@router.get("/config")
async def config(admin: dict = Depends(get_current_admin)):
    return await _llamar("GET", "/config")


@router.get("/directorio")
async def directorio(q: str = "", admin: dict = Depends(get_current_admin)):
    return await _llamar("GET", "/directorio", params={"q": q})


@router.get("/estado")
async def estado(correo: str, admin: dict = Depends(get_current_admin)):
    return await _llamar("GET", "/estado", params={"correo": correo})


@router.post("/enlace")
async def enlace(request: Request, admin: dict = Depends(require_role("superadmin", "admin"))):
    datos = await request.json()
    r = await _llamar("POST", "/enlace", json={"correo": datos.get("correo"), "usuario_id": datos.get("usuario_id")})
    await _audit(request, admin, "drive_enlace", datos.get("correo"))
    return r


@router.post("/cuota")
async def cuota(request: Request, admin: dict = Depends(require_role("superadmin", "admin"))):
    datos = await request.json()
    r = await _llamar("POST", "/cuota", json={"correo": datos.get("correo"), "cuota_gb": datos.get("cuota_gb", 0)})
    await _audit(request, admin, "drive_cuota", datos.get("correo"))
    return r
