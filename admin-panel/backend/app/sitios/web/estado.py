"""Estado de las funciones web de un sitio: redirecciones, carpetas con contraseña, páginas de error,
hotlinking, IP bloqueadas y optimización (una sola llamada para la ventana «Web» del panel)."""

from fastapi import APIRouter, Depends

from app.auth.dependencies import get_current_admin
from app.sitios.router import _ayudante, _dominio

router = APIRouter(prefix="/api/sitios", tags=["sitios"])


@router.get("/{dominio}/web")
async def ver(dominio: str, admin: dict = Depends(get_current_admin)):
    return await _ayudante("web", _dominio(dominio))
