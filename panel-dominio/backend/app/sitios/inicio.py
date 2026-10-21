"""Tarjeta «Mi sitio web» del inicio: aplicación, versión, HTTPS y actualizaciones de cada sitio.

La pantalla de inicio la pide aparte del resumen del correo, para no hacerlo esperar. Revisar una
aplicación es lento (wp-cli y compañía), así que se revisan pocos sitios a la vez, con tiempo
corto, y el resultado se guarda unos minutos en memoria. Si los sitios no están instalados, la
tarjeta no aparece.
"""

import asyncio
import time

from fastapi import APIRouter, Depends, HTTPException, Request

from app.sesion import admin_actual
from app.sitios import cliente
from app.sitios.comun import ficha_de, listar

router = APIRouter(prefix="/api/sitios", tags=["sitios"])
MAX_REVISADOS = 5
SEGUNDOS_GUARDADO = 600
_revisiones: dict[str, tuple[float, dict | None]] = {}


def pendientes(revision: dict | None) -> int | None:
    """Número de actualizaciones pendientes (núcleo, complementos y temas), o None si no se sabe."""
    act = (revision or {}).get("actualizaciones")
    if not isinstance(act, dict):
        return None
    return sum(len(act.get(k) or []) for k in ("nucleo", "complementos", "temas"))


async def _revisar(request: Request, sitio: str) -> dict | None:
    guardada = _revisiones.get(sitio)
    if guardada and time.monotonic() - guardada[0] < SEGUNDOS_GUARDADO:
        return guardada[1]
    try:
        revision = await asyncio.wait_for(cliente.pedir(ficha_de(request), "revisar", sitio), timeout=45)
    except (HTTPException, asyncio.TimeoutError):
        revision = None
    _revisiones[sitio] = (time.monotonic(), revision if isinstance(revision, dict) else None)
    return _revisiones[sitio][1]


@router.get("/resumen")
async def resumen(request: Request, admin: dict = Depends(admin_actual)):
    try:
        datos = await listar(request, admin)
    except HTTPException as e:
        if e.status_code == 503:
            return {"instalado": False, "sitios": []}
        raise
    sitios = [s for s in datos.get("sitios") or [] if isinstance(s, dict)]
    con_app = [s for s in sitios if s.get("app") and s.get("app") != "paquete" and not s.get("app_pendiente")]
    revisiones = await asyncio.gather(*[_revisar(request, s["dominio"]) for s in con_app[:MAX_REVISADOS]])
    por_sitio = {s["dominio"]: r for s, r in zip(con_app, revisiones)}
    return {"instalado": True, "dominios": datos.get("dominios") or [], "sitios": [{
        "sitio": s.get("dominio"), "app": s.get("app"), "app_pendiente": bool(s.get("app_pendiente")),
        "https": bool(s.get("ssl")), "version": (por_sitio.get(s.get("dominio")) or {}).get("version"),
        "actualizaciones": pendientes(por_sitio.get(s.get("dominio"))),
        "revisado": s.get("dominio") in por_sitio,
    } for s in sitios]}
