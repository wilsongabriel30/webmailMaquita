"""Rutas de Tareas de la F5 (To Do, 31/10/2026): duplicar una lista desde el menú de la barra."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Request

from app.auth.dependencies import get_current_user
from app.tasks import duplicar
from app.tasks.listas import Lista
from app.tasks.rutas_listas import _con_errores

router = APIRouter()


@router.post("/lists/{list_id}/duplicar", response_model=Lista, status_code=201)
async def duplicar_lista(
    list_id: uuid.UUID, request: Request, user: str = Depends(get_current_user)
):
    async with request.app.state.db_pool.acquire() as con:
        async with con.transaction():
            return await _con_errores(duplicar.duplicar(con, user, list_id))
