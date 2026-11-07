"""Rutas de la F3 de Tareas (To Do, 30/10/2026): buscar, mover a otra lista y archivos adjuntos."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel

from app.auth.dependencies import get_current_user
from app.tasks import acceso, adjuntos, mover, vistas
from app.tasks.adjuntos import Adjunto
from app.tasks.schemas import CardOut

router = APIRouter()


def _db(request: Request):
    return request.app.state.db_pool


async def _tarea_visible(db, card_id, user: str) -> None:
    if not await acceso.puede_ver_tarea(db, card_id, user):
        raise HTTPException(status_code=404, detail="Tarea no encontrada")


@router.get("/buscar", response_model=list[CardOut])
async def buscar_tareas(
    request: Request,
    q: str = Query(..., min_length=1, max_length=200),
    user: str = Depends(get_current_user),
):
    texto = q.strip()
    if not texto:
        return []
    return await vistas.buscar(_db(request), user, texto)


class Destino(BaseModel):
    list_id: uuid.UUID


@router.patch("/tasks/{card_id}/lista", response_model=CardOut)
async def mover_tarea(
    card_id: uuid.UUID,
    data: Destino,
    request: Request,
    user: str = Depends(get_current_user),
):
    db = _db(request)
    try:
        async with db.acquire() as con:
            async with con.transaction():
                await mover.mover(con, user, card_id, data.list_id)
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except mover.NoSeMueve as e:
        raise HTTPException(status_code=400, detail=str(e))
    tarjeta = await vistas.una(db, user, card_id)
    if tarjeta is None:
        raise HTTPException(status_code=404, detail="Tarea no encontrada")
    return tarjeta


@router.get("/tasks/{card_id}/adjuntos", response_model=list[Adjunto])
async def ver_adjuntos(
    card_id: uuid.UUID, request: Request, user: str = Depends(get_current_user)
):
    db = _db(request)
    await _tarea_visible(db, card_id, user)
    return await adjuntos.de_tarea(db, card_id)


@router.post("/tasks/{card_id}/adjuntos", response_model=Adjunto, status_code=201)
async def subir_adjunto(
    card_id: uuid.UUID,
    request: Request,
    archivo: UploadFile = File(...),
    user: str = Depends(get_current_user),
):
    db = _db(request)
    await _tarea_visible(db, card_id, user)
    contenido = await archivo.read(adjuntos.MAX_TAMANO + 1)
    try:
        return await adjuntos.guardar(
            db, user, card_id, archivo.filename, archivo.content_type, contenido
        )
    except adjuntos.Rechazado as e:
        raise HTTPException(status_code=e.status, detail=e.detalle)


async def _adjunto_visible(db, adjunto_id, user: str):
    row = await adjuntos.uno(db, adjunto_id)
    if row is None or not await acceso.puede_ver_tarea(db, row["card_id"], user):
        raise HTTPException(status_code=404, detail="Archivo no encontrado")
    return row


@router.get("/adjuntos/{adjunto_id}")
async def descargar_adjunto(
    adjunto_id: uuid.UUID, request: Request, user: str = Depends(get_current_user)
):
    row = await _adjunto_visible(_db(request), adjunto_id, user)
    ruta = adjuntos.ruta_de(row)
    if not ruta.is_file():
        raise HTTPException(status_code=404, detail="Archivo no encontrado")
    # Siempre como descarga: un HTML o SVG subido no se abre dentro del webmail.
    return FileResponse(
        path=str(ruta),
        filename=row["nombre"],
        media_type="application/octet-stream",
        headers={"X-Content-Type-Options": "nosniff"},
    )


@router.delete("/adjuntos/{adjunto_id}", status_code=204)
async def borrar_adjunto(
    adjunto_id: uuid.UUID, request: Request, user: str = Depends(get_current_user)
):
    db = _db(request)
    row = await _adjunto_visible(db, adjunto_id, user)
    await adjuntos.borrar(db, row)
