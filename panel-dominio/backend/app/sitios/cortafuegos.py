"""Cortafuegos de aplicaciones web del sitio (v1.11): ModSecurity con las reglas OWASP CRS completas.

Modo (apagado, solo detectar o bloquear), nivel de paranoia (1 o 2), exclusiones por número de regla (en todo el
sitio o solo en una ruta) y visor de los últimos bloqueos. maquita-sitios lo aplica con copia previa y `nginx -t`.
"""

import re

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from app.sesion import admin_actual
from app.sitios.comun import cuerpo, exigir_sitio, llamar

router = APIRouter(prefix="/api/sitios", tags=["sitios"])
RE_RUTA = re.compile(r"/[A-Za-z0-9._~/-]{0,200}")
MODOS = ("apagado", "detectar", "bloquear")


def _ajustes(datos: dict) -> dict:
    modo, paranoia = datos.get("modo", "bloquear"), datos.get("paranoia", 1)
    if modo not in MODOS:
        raise HTTPException(400, "Modo no válido: apagado, solo detectar o bloquear")
    if paranoia not in (1, 2) or isinstance(paranoia, bool):
        raise HTTPException(400, "El nivel de paranoia es 1 o 2")
    lista = datos.get("exclusiones", [])
    if not isinstance(lista, list) or len(lista) > 50:
        raise HTTPException(400, "Se admiten hasta 50 exclusiones")
    exclusiones = []
    for e in lista:
        regla = e.get("regla") if isinstance(e, dict) else None
        ruta = (e.get("ruta") or "").strip() if isinstance(e, dict) and isinstance(e.get("ruta"), str) else None
        if isinstance(regla, bool) or not isinstance(regla, int) or not 900000 <= regla <= 999999:
            raise HTTPException(400, "Regla no válida: el número de una regla de OWASP CRS (9xxxxx)")
        if ruta and not RE_RUTA.fullmatch(ruta):
            raise HTTPException(400, "Ruta no válida: empieza por «/» y solo lleva letras sin tilde, números y . _ ~ / -")
        exclusiones.append({"regla": regla, "ruta": ruta or None})
    return {"modo": modo, "paranoia": paranoia, "exclusiones": exclusiones}


@router.get("/{sitio}/cortafuegos")
async def ver(sitio: str, request: Request, admin: dict = Depends(admin_actual)):
    sitio, _ = exigir_sitio(admin, sitio)
    return await llamar(request, admin, "waf", sitio)


@router.put("/{sitio}/cortafuegos")
async def guardar(sitio: str, request: Request, admin: dict = Depends(admin_actual)):
    sitio, _ = exigir_sitio(admin, sitio)
    ajustes = _ajustes(await cuerpo(request))
    return await llamar(request, admin, "waf-guardar", sitio, {"waf": ajustes}, "sitio_waf_guardar", ajustes)


@router.get("/{sitio}/cortafuegos/bloqueos")
async def bloqueos(sitio: str, request: Request, cuantos: int = Query(50, ge=1, le=200),
                   admin: dict = Depends(admin_actual)):
    sitio, _ = exigir_sitio(admin, sitio)
    return await llamar(request, admin, "waf-bloqueos", sitio, {"cuantos": cuantos})
