"""Ruta para crear tareas soltando correos en el ícono Tareas (06/11/2026). Lógica en desde_correo.py."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel

from app.auth.dependencies import get_current_user
from app.tasks import desde_correo, vistas
from app.tasks.schemas import CardOut

router = APIRouter()


class RespuestaDesdeCorreo(BaseModel):
    creadas: list[CardOut]
    repetidas: int


@router.post("/desde-correo", response_model=RespuestaDesdeCorreo, status_code=201)
async def tareas_desde_correo(
    data: desde_correo.PedidoDesdeCorreo,
    request: Request,
    user: str = Depends(get_current_user),
):
    """Una tarea por correo soltado, con el enlace al mensaje. No repite un correo con tarea abierta."""
    pool = request.app.state.db_pool
    async with pool.acquire() as con:
        async with con.transaction():
            r = await desde_correo.crear(con, user, data.correos)
        tarjetas = [await vistas.una(con, user, card_id) for card_id in r["creadas"]]
    return RespuestaDesdeCorreo(
        creadas=[t for t in tarjetas if t], repetidas=r["repetidas"]
    )
