"""Rutas de las listas inteligentes, de las tareas de una lista y de «Mi día» (To Do, F1 29/10/2026).

Salieron de router.py: las vistas ahora miran también las listas compartidas y dan «Mi día» de quien mira.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Request

from app.auth.dependencies import get_current_user
from app.tasks import acceso, correo_marcado, mi_dia, vistas
from app.tasks.schemas import CardOut
from app.tasks.service import task_service

router = APIRouter()


def _db(request: Request):
    return request.app.state.db_pool


async def _vista(request: Request, user: str, nombre: str) -> list[CardOut]:
    return await vistas.vista(_db(request), user, nombre)


@router.get("/views/my-day", response_model=list[CardOut])
async def vista_mi_dia(request: Request, user: str = Depends(get_current_user)):
    return await _vista(request, user, "my_day")


@router.get("/views/important", response_model=list[CardOut])
async def vista_importante(request: Request, user: str = Depends(get_current_user)):
    return await _vista(request, user, "important")


@router.get("/views/planned", response_model=list[CardOut])
async def vista_planeado(request: Request, user: str = Depends(get_current_user)):
    return await _vista(request, user, "planned")


@router.get("/views/assigned", response_model=list[CardOut])
async def vista_asignado(request: Request, user: str = Depends(get_current_user)):
    return await _vista(request, user, "assigned")


@router.get("/views/tasks", response_model=list[CardOut])
async def vista_tareas(request: Request, user: str = Depends(get_current_user)):
    """Bandeja «Tareas»: la lista por defecto, donde caen las tareas creadas sin lista."""
    await task_service.ensure_default_board(_db(request), user)
    return await _vista(request, user, "tasks")


@router.get("/views/flagged", response_model=list[CardOut])
async def vista_correo_marcado(request: Request, user: str = Depends(get_current_user)):
    await correo_marcado.sincronizar(request, user)
    return await _vista(request, user, "flagged")


@router.get("/views/flagged/count")
async def conteo_correo_marcado(
    request: Request, user: str = Depends(get_current_user)
):
    """Tareas pendientes del correo marcado, tras comparar con el buzón."""
    await correo_marcado.sincronizar(request, user)
    conteos = await vistas.contar(_db(request), user)
    return {"flagged": conteos["flagged"]}


@router.get("/views/counts")
async def conteo_de_vistas(request: Request, user: str = Depends(get_current_user)):
    """Pendientes de cada lista inteligente (los números de la barra lateral)."""
    return await vistas.contar(_db(request), user)


@router.get("/lists/{list_id}/tasks", response_model=list[CardOut])
async def tareas_de_lista(
    list_id: uuid.UUID, request: Request, user: str = Depends(get_current_user)
):
    if not await acceso.puede_ver_lista(_db(request), list_id, user):
        raise HTTPException(status_code=404, detail="List not found")
    return await vistas.de_lista(_db(request), user, list_id)


@router.patch("/tasks/{card_id}/my-day", response_model=CardOut)
async def alternar_mi_dia(
    card_id: uuid.UUID, request: Request, user: str = Depends(get_current_user)
):
    db = _db(request)
    if not await acceso.puede_ver_tarea(db, card_id, user):
        raise HTTPException(status_code=404, detail="Card not found")
    await mi_dia.alternar(db, user, card_id)
    tarjeta = await vistas.una(db, user, card_id)
    if (
        tarjeta is None
    ):  # tablero compartido a la antigua: la lista no está entre las visibles
        raise HTTPException(status_code=404, detail="Card not found")
    return tarjeta
