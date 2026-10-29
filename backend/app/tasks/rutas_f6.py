"""Rutas de Tareas de la F6 (To Do, 29/10/2026): configuración personal y panel «Sugerencias»."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from app.auth.dependencies import get_current_user
from app.tasks import ajustes, sugerencias

router = APIRouter()


def _db(request: Request):
    return request.app.state.db_pool


@router.get("/ajustes", response_model=ajustes.Ajustes)
async def ver_ajustes(request: Request, user: str = Depends(get_current_user)):
    return await ajustes.leer(_db(request), user)


@router.put("/ajustes", response_model=ajustes.Ajustes)
async def guardar_ajustes(
    data: ajustes.Ajustes, request: Request, user: str = Depends(get_current_user)
):
    return await ajustes.guardar(_db(request), user, data)


@router.get("/sugerencias", response_model=sugerencias.Sugerencias)
async def ver_sugerencias(request: Request, user: str = Depends(get_current_user)):
    return await sugerencias.sugerencias(_db(request), user)
