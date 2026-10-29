"""Rutas de las listas propias, los grupos y el orden (To Do, F2 29/10/2026). Salieron de router.py."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Request

from app.auth.dependencies import get_current_user
from app.tasks import listas
from app.tasks.listas import (
    Grupo,
    GrupoCambio,
    GrupoNuevo,
    Lista,
    ListaCambio,
    ListaNueva,
    OrdenBarra,
    OrdenTareas,
)

router = APIRouter()


def _db(request: Request):
    return request.app.state.db_pool


async def _con_errores(coro):
    try:
        return await coro
    except listas.NoEncontrada:
        raise HTTPException(status_code=404, detail="No encontrada")
    except listas.SinPermiso:
        raise HTTPException(
            status_code=403, detail="Solo la propietaria de la lista puede hacerlo"
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/lists", response_model=list[Lista])
async def ver_listas(request: Request, user: str = Depends(get_current_user)):
    return await listas.listas(_db(request), user)


@router.post("/lists", response_model=Lista, status_code=201)
async def crear_lista(
    data: ListaNueva, request: Request, user: str = Depends(get_current_user)
):
    return await listas.crear_lista(_db(request), user, data)


@router.patch("/lists/{list_id}", response_model=Lista)
async def cambiar_lista(
    list_id: uuid.UUID,
    data: ListaCambio,
    request: Request,
    user: str = Depends(get_current_user),
):
    return await _con_errores(listas.cambiar_lista(_db(request), user, list_id, data))


@router.delete("/lists/{list_id}", status_code=204)
async def eliminar_lista(
    list_id: uuid.UUID, request: Request, user: str = Depends(get_current_user)
):
    await _con_errores(listas.eliminar_lista(_db(request), user, list_id))


@router.put("/lists/{list_id}/orden", status_code=204)
async def ordenar_tareas(
    list_id: uuid.UUID,
    data: OrdenTareas,
    request: Request,
    user: str = Depends(get_current_user),
):
    await _con_errores(listas.guardar_orden_tareas(_db(request), user, list_id, data))


@router.get("/groups", response_model=list[Grupo])
async def ver_grupos(request: Request, user: str = Depends(get_current_user)):
    return await listas.grupos(_db(request), user)


@router.post("/groups", response_model=Grupo, status_code=201)
async def crear_grupo(
    data: GrupoNuevo, request: Request, user: str = Depends(get_current_user)
):
    return await listas.crear_grupo(_db(request), user, data)


@router.patch("/groups/{group_id}", response_model=Grupo)
async def cambiar_grupo(
    group_id: uuid.UUID,
    data: GrupoCambio,
    request: Request,
    user: str = Depends(get_current_user),
):
    return await _con_errores(listas.cambiar_grupo(_db(request), user, group_id, data))


@router.delete("/groups/{group_id}", status_code=204)
async def eliminar_grupo(
    group_id: uuid.UUID, request: Request, user: str = Depends(get_current_user)
):
    await _con_errores(listas.eliminar_grupo(_db(request), user, group_id))


@router.put("/sidebar/orden", status_code=204)
async def ordenar_barra(
    data: OrdenBarra, request: Request, user: str = Depends(get_current_user)
):
    async with _db(request).acquire() as con:
        async with con.transaction():
            await listas.guardar_orden_barra(con, user, data)
