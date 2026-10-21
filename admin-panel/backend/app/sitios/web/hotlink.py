"""Protección contra hotlinking: que otras páginas no muestren los archivos del sitio gastando su tráfico."""

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from app.auth.dependencies import require_superadmin
from app.sitios.web.comun import guardar

router = APIRouter(prefix="/api/sitios", tags=["sitios"])


class Hotlink(BaseModel):
    activo: bool
    extensiones: list[str] = []
    permitidos: list[str] = []
    buscadores: bool = True


@router.put("/{dominio}/web/hotlink")
async def guardar_hotlink(dominio: str, body: Hotlink, r: Request, admin: dict = Depends(require_superadmin)):
    if len(body.extensiones) > 30 or len(body.permitidos) > 50:
        raise HTTPException(400, "Hasta 30 extensiones y 50 dominios permitidos")
    return await guardar(r, admin, dominio, "web-hotlink", body.model_dump(), "sitio_web_hotlink")
