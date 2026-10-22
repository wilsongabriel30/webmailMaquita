"""Comprobaciones de salud del panel para balanceadores y para el despliegue sin corte.

- GET /api/salud → 200 si el proceso responde (no toca la base).
- GET /api/listo → 200 si PostgreSQL contesta; 503 si no o si el nodo está en drenaje.

Públicas y sin detalle (ni versiones ni errores). El estado completo del sistema sigue
en /api/health, solo para administradores.
"""

import asyncio
import os

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

router = APIRouter(tags=["salud"])

ARCHIVO_DRENAJE = os.getenv("ESCALA_ARCHIVO_DRENAJE_PANEL", "/run/maquita-admin/drenar")
ESPERA_S = float(os.getenv("ESCALA_LISTO_ESPERA_S", "2"))
_SIN_CACHE = {"Cache-Control": "no-store"}


@router.get("/api/salud")
async def salud():
    return JSONResponse({"estado": "vivo"}, headers=_SIN_CACHE)


@router.get("/api/listo")
async def listo(request: Request):
    if os.path.exists(ARCHIVO_DRENAJE):
        return JSONResponse({"estado": "drenando"}, status_code=503, headers=_SIN_CACHE)
    pool = getattr(request.app.state, "db", None)
    ok = False
    if pool is not None:
        try:
            ok = await asyncio.wait_for(pool.fetchval("SELECT 1"), ESPERA_S) == 1
        except Exception:
            ok = False
    return JSONResponse(
        {"estado": "listo" if ok else "no_listo"},
        status_code=200 if ok else 503,
        headers=_SIN_CACHE,
    )
