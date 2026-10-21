"""Observación del sitio (v1.10): registros (errores y accesos de nginx, errores de PHP), estadísticas de visitas
y ancho de banda (GoAccess, 30 días) y disponibilidad (comprobación cada 5 minutos, con su historial).

Solo se consultan, salvo «Generar ahora» las estadísticas. El informe completo de GoAccess no es público: se
entrega con un enlace de un solo uso y aislado del portal (descargas.py, «Content-Security-Policy: sandbox»).
"""

import re

from fastapi import APIRouter, Depends, HTTPException, Request

from app.sesion import admin_actual
from app.sitios import descargas
from app.sitios.comun import exigir_sitio, llamar

router = APIRouter(prefix="/api/sitios", tags=["sitios"])
TIPOS = ("error", "acceso", "php")
_CONTROL = re.compile(r"[\x00-\x1f\x7f]")


@router.get("/{sitio}/registros/{tipo}")
async def registros(sitio: str, tipo: str, request: Request, lineas: int = 200, filtro: str = "",
                    admin: dict = Depends(admin_actual)):
    sitio, _ = exigir_sitio(admin, sitio)
    if tipo not in TIPOS:
        raise HTTPException(400, "Registro no válido")
    if not 1 <= lineas <= 1000:
        raise HTTPException(400, "Entre 1 y 1000 líneas")
    filtro = filtro.strip()
    if len(filtro) > 100 or len(filtro.encode()) > 140 or _CONTROL.search(filtro):
        raise HTTPException(400, "Filtro no válido (hasta 100 caracteres)")
    args = {"tipo": tipo, "lineas": lineas, **({"filtro": filtro} if filtro else {})}
    return await llamar(request, admin, "registros", sitio, args)


@router.get("/{sitio}/estadisticas")
async def estadisticas(sitio: str, request: Request, admin: dict = Depends(admin_actual)):
    sitio, _ = exigir_sitio(admin, sitio)
    return await llamar(request, admin, "estadisticas", sitio)


@router.post("/{sitio}/estadisticas/generar")
async def generar(sitio: str, request: Request, admin: dict = Depends(admin_actual)):
    sitio, _ = exigir_sitio(admin, sitio)
    return await llamar(request, admin, "estadisticas-generar", sitio, None, "sitio_estadisticas_generar")


@router.post("/{sitio}/estadisticas/informe")
async def informe(sitio: str, request: Request, admin: dict = Depends(admin_actual)):
    sitio, _ = exigir_sitio(admin, sitio)
    return descargas.enlace(await llamar(request, admin, "estadisticas-informe", sitio), ver=True)


@router.get("/{sitio}/disponibilidad")
async def disponibilidad(sitio: str, request: Request, admin: dict = Depends(admin_actual)):
    sitio, _ = exigir_sitio(admin, sitio)
    return await llamar(request, admin, "disponibilidad", sitio)
