"""Optimización por sitio para conexiones lentas (ADSL rural, satélite): compresión, caché del navegador y caché
de página (solo sitios PHP; nunca con sesión iniciada ni en la administración) con purga manual."""

from typing import Literal

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field

from app.auth.dependencies import require_superadmin
from app.sitios.router import _auditar, _ayudante, _dominio
from app.sitios.web.comun import guardar

router = APIRouter(prefix="/api/sitios", tags=["sitios"])


class Optimizacion(BaseModel):
    compresion: bool = True
    estaticos: Literal["off", "1h", "1d", "7d", "30d", "180d", "365d"] = "30d"
    cache_pagina: bool = False
    cache_minutos: int = Field(10, ge=1, le=1440)


@router.put("/{dominio}/web/optimizacion")
async def guardar_optimizacion(dominio: str, body: Optimizacion, r: Request, admin: dict = Depends(require_superadmin)):
    return await guardar(r, admin, dominio, "web-optimizacion", body.model_dump(), "sitio_web_optimizacion")


@router.post("/{dominio}/web/purgar")
async def purgar(dominio: str, r: Request, admin: dict = Depends(require_superadmin)):
    dominio = _dominio(dominio)
    res = await _ayudante("web-purgar", dominio)
    await _auditar(r, admin, "sitio_web_purgar", dominio)
    return res
