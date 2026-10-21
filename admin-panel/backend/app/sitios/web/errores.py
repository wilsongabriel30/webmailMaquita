"""Páginas de error propias del sitio (403, 404, 500, 502, 503): un .html de la carpeta pública por código."""

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from app.auth.dependencies import require_superadmin
from app.sitios.web.comun import guardar

router = APIRouter(prefix="/api/sitios", tags=["sitios"])
CODIGOS = {"403", "404", "500", "502", "503"}


class Paginas(BaseModel):
    paginas: dict[str, str]


@router.put("/{dominio}/web/errores")
async def guardar_errores(dominio: str, body: Paginas, r: Request, admin: dict = Depends(require_superadmin)):
    if set(body.paginas) - CODIGOS:
        raise HTTPException(400, "Solo se admiten los códigos 403, 404, 500, 502 y 503")
    return await guardar(r, admin, dominio, "web-errores", body.paginas, "sitio_web_errores")
