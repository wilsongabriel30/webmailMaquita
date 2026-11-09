"""Ruta del modo Tablero de Tareas (09/11/2026): mover una tarea de lista a Pendiente, En curso o Completada."""

from __future__ import annotations

import uuid
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from app.auth.dependencies import get_current_user
from app.tasks import estado_tarea
from app.tasks.schemas import CardOut

router = APIRouter()


class CambioEstado(BaseModel):
    estado: Literal["pendiente", "en_curso", "completada"]


@router.patch("/tasks/{card_id}/estado", response_model=CardOut)
async def cambiar_estado(
    card_id: uuid.UUID,
    data: CambioEstado,
    request: Request,
    user: str = Depends(get_current_user),
):
    # Completar o reabrir una tarea personal usa la misma ruta que el círculo de la lista.
    from app.tasks.router import todo_toggle_task

    try:
        return await estado_tarea.cambiar(
            request.app.state.db_pool,
            request.app.state.redis,
            user,
            card_id,
            data.estado,
            lambda: todo_toggle_task(card_id, request, user),
        )
    except estado_tarea.NoParticipa as e:
        raise HTTPException(status_code=403, detail=str(e))
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e))
