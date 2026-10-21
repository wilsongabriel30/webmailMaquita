"""Disponibilidad del sitio: estado, porcentaje e historial de las comprobaciones de cada 5 minutos (HTTPS,
tiempo de respuesta y días que le quedan al certificado) y los avisos enviados. Las comprueba el temporizador
sitios-disponibilidad del servidor; aquí solo se consultan.
"""

from fastapi import APIRouter, Depends

from app.auth.dependencies import get_current_admin
from app.sitios.router import _ayudante, _dominio

router = APIRouter(prefix="/api/sitios", tags=["sitios"])


@router.get("/{dominio}/disponibilidad")
async def ver(dominio: str, admin: dict = Depends(get_current_admin)):
    return await _ayudante("disponibilidad", _dominio(dominio))
