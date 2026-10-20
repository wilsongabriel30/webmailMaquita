"""Primeros pasos tras instalar un servidor desde la plantilla (panel → «Primeros pasos»).

El asistente de primer arranque deja la clave «primeros_pasos» en branding_settings con {"estado": "pendiente"};
mientras siga pendiente, el panel lleva a la persona administradora a esta pantalla (logo e información de la
institución, clave inicial, dominio, certificado), con la opción de omitir cada paso y volver luego. Una
instalación que no viene de la plantilla no tiene la clave y nunca la ve.
"""

import json

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from app.auth.dependencies import get_current_admin, require_superadmin

router = APIRouter(prefix="/api/primeros-pasos", tags=["primeros-pasos"])
PASOS = ("identidad", "clave", "dominio", "certificado")


async def _leer(db) -> dict | None:
    fila = await db.fetchval("SELECT value FROM branding_settings WHERE key = 'primeros_pasos'")
    if fila is None:
        return None
    try:
        datos = json.loads(fila)
    except ValueError:
        datos = {}
    return datos if isinstance(datos, dict) else {}


@router.get("")
async def estado(request: Request, admin: dict = Depends(get_current_admin)):
    try:
        datos = await _leer(request.app.state.db)
    except Exception:  # sin tabla de marca todavía: no hay nada pendiente
        datos = None
    if datos is None:
        return {"pendiente": False, "pasos": {}}
    return {"pendiente": datos.get("estado") != "terminado", "pasos": datos.get("pasos", {})}


class Cambio(BaseModel):
    paso: str | None = None  # identidad | clave | dominio | certificado
    estado: str | None = None  # hecho | omitido | pendiente
    terminar: bool = False


@router.put("")
async def cambiar(body: Cambio, request: Request, admin: dict = Depends(require_superadmin)):
    db = request.app.state.db
    datos = await _leer(db) or {}
    pasos = datos.get("pasos", {})
    if body.paso is not None:
        if body.paso not in PASOS or body.estado not in ("hecho", "omitido", "pendiente"):
            raise HTTPException(400, "Paso o estado no válido")
        pasos[body.paso] = body.estado
    datos = {"estado": "terminado" if body.terminar else datos.get("estado", "pendiente"), "pasos": pasos}
    await db.execute(
        "INSERT INTO branding_settings (key, value, updated_at) VALUES ('primeros_pasos', $1, NOW()) "
        "ON CONFLICT (key) DO UPDATE SET value = $1, updated_at = NOW()",
        json.dumps(datos),
    )
    return {"pendiente": datos["estado"] != "terminado", "pasos": pasos}
