"""Estadísticas de visitas y ancho de banda del sitio (GoAccess): resumen de 30 días e informe completo.

El informe HTML no es público: el ayudante lo deja en subidas/ y el panel lo entrega por un enlace de un solo uso,
aislado del panel (entrega.py). Se genera cada noche; «Generar ahora» lo rehace al momento.
"""

from fastapi import APIRouter, Depends, Request

from app.auth.dependencies import get_current_admin, require_superadmin
from app.sitios.entrega import enlace
from app.sitios.router import _auditar, _ayudante, _dominio

router = APIRouter(prefix="/api/sitios", tags=["sitios"])


@router.get("/{dominio}/estadisticas")
async def ver(dominio: str, admin: dict = Depends(get_current_admin)):
    return await _ayudante("estadisticas", _dominio(dominio))


@router.post("/{dominio}/estadisticas/generar")
async def generar(dominio: str, r: Request, admin: dict = Depends(require_superadmin)):
    dominio = _dominio(dominio)
    res = await _ayudante("estadisticas-generar", dominio, tiempo=1800)
    await _auditar(r, admin, "sitio_estadisticas_generar", dominio)
    return res


@router.post("/{dominio}/estadisticas/informe")
async def informe(dominio: str, admin: dict = Depends(get_current_admin)):
    dominio = _dominio(dominio)
    res = await _ayudante("estadisticas-informe", dominio)
    return {"enlace": enlace(res.get("archivo", ""), f"estadisticas-{dominio}.html", ver=True)}
