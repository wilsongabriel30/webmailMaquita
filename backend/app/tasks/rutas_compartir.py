"""Rutas de la F4 de Tareas (To Do, 30/10/2026): compartir listas, asignar tareas, actividad y avisos por correo."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from app.auth.dependencies import get_current_user
from app.tareas import avisos
from app.tasks import acceso, actividad, asignar, avisos_listas, compartir, vistas
from app.tasks.actividad import Evento
from app.tasks.compartir import Miembro, NuevoMiembro
from app.tasks.listas import NoEncontrada, SinPermiso
from app.tasks.schemas import CardOut

router = APIRouter()


def _db(request: Request):
    return request.app.state.db_pool


def _redis(request: Request):
    return request.app.state.redis


async def _transaccion(request: Request, funcion, *args):
    try:
        async with _db(request).acquire() as con:
            async with con.transaction():
                return await funcion(con, *args)
    except NoEncontrada:
        raise HTTPException(status_code=404, detail="Lista no encontrada")
    except SinPermiso:
        raise HTTPException(
            status_code=403, detail="Solo la propietaria de la lista puede hacerlo"
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/lists/{list_id}/miembros", response_model=list[Miembro])
async def ver_miembros(
    list_id: uuid.UUID, request: Request, user: str = Depends(get_current_user)
):
    try:
        return await compartir.miembros(_db(request), user, list_id)
    except NoEncontrada:
        raise HTTPException(status_code=404, detail="Lista no encontrada")


@router.post("/lists/{list_id}/miembros", response_model=Miembro, status_code=201)
async def compartir_lista(
    list_id: uuid.UUID,
    data: NuevoMiembro,
    request: Request,
    user: str = Depends(get_current_user),
):
    miembro = await _transaccion(request, compartir.agregar, user, list_id, data.email)
    nombre = await _db(request).fetchval(
        "SELECT name FROM task_lists WHERE id = $1", list_id
    )
    await avisos_listas.avisar(
        _redis(request),
        _db(request),
        [data.email],
        user,
        "shared",
        f"{avisos.nombre(user)} compartió una lista contigo",
        f"{avisos.nombre(user)} compartió contigo la lista «{nombre}».",
    )
    return miembro


@router.delete("/lists/{list_id}/miembros/{email}", status_code=204)
async def quitar_miembro(
    list_id: uuid.UUID,
    email: str,
    request: Request,
    user: str = Depends(get_current_user),
):
    """La propietaria quita a alguien; con el propio correo, un miembro se sale de la lista."""
    email = email.strip().lower()
    duena = await compartir.rol(_db(request), list_id, user) == "owner"
    nombre = await _transaccion(request, compartir.quitar, user, list_id, email)
    if email == user:
        propietarias = [
            r["user_email"]
            for r in await _db(request).fetch(
                "SELECT user_email FROM task_list_members WHERE list_id = $1 AND role = 'owner'",
                list_id,
            )
        ]
        texto = f"{avisos.nombre(user)} salió de la lista «{nombre}»."
        await avisos_listas.avisar(
            _redis(request), _db(request), propietarias, user, "left", texto, texto
        )
    elif duena:
        texto = f"{avisos.nombre(user)} te quitó de la lista «{nombre}»."
        await avisos_listas.avisar(
            _redis(request), _db(request), [email], user, "removed", texto, texto
        )


@router.delete("/lists/{list_id}/miembros", status_code=204)
async def dejar_de_compartir(
    list_id: uuid.UUID, request: Request, user: str = Depends(get_current_user)
):
    # Las pantallas de quienes quedan fuera se ponen al día por tiempo_real (estaban en la lista antes del cambio).
    await _transaccion(request, compartir.dejar_de_compartir, user, list_id)


@router.get("/lists/{list_id}/actividad", response_model=list[Evento])
async def actividad_de_lista(
    list_id: uuid.UUID, request: Request, user: str = Depends(get_current_user)
):
    if not await acceso.puede_ver_lista(_db(request), list_id, user):
        raise HTTPException(status_code=404, detail="Lista no encontrada")
    return await actividad.de_lista(_db(request), list_id)


@router.get("/tasks/{card_id}/actividad", response_model=list[Evento])
async def actividad_de_tarea(
    card_id: uuid.UUID, request: Request, user: str = Depends(get_current_user)
):
    if not await acceso.puede_ver_tarea(_db(request), card_id, user):
        raise HTTPException(status_code=404, detail="Tarea no encontrada")
    return await actividad.de_tarea(_db(request), card_id)


@router.put("/tasks/{card_id}/asignados", response_model=CardOut)
async def asignar_tarea(
    card_id: uuid.UUID,
    data: asignar.Asignacion,
    request: Request,
    user: str = Depends(get_current_user),
):
    try:
        async with _db(request).acquire() as con:
            async with con.transaction():
                nuevos, tarea = await asignar.asignar(con, user, card_id, data.emails)
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except asignar.NoSeAsigna as e:
        raise HTTPException(status_code=400, detail=str(e))
    if nuevos:
        texto = f"{avisos.nombre(user)} te asignó la tarea «{tarea['title']}» (lista «{tarea['lista']}»)."
        if data.mensaje.strip():
            texto += f" Mensaje: «{data.mensaje.strip()}»"
        await avisos_listas.avisar(
            _redis(request),
            _db(request),
            nuevos,
            user,
            "assigned",
            "Te asignaron una tarea",
            texto,
            card_id,
            correo=True,  # asignar es directo a la persona: el correo sale siempre
        )
    tarjeta = await vistas.una(_db(request), user, card_id)
    if tarjeta is None:
        raise HTTPException(status_code=404, detail="Tarea no encontrada")
    return tarjeta


class Preferencias(BaseModel):
    avisos_correo: bool


@router.get("/preferencias", response_model=Preferencias)
async def ver_preferencias(request: Request, user: str = Depends(get_current_user)):
    return Preferencias(
        avisos_correo=await avisos_listas.quiere_correo(_db(request), user)
    )


@router.put("/preferencias", response_model=Preferencias)
async def guardar_preferencias(
    data: Preferencias, request: Request, user: str = Depends(get_current_user)
):
    await avisos_listas.guardar_preferencia(_db(request), user, data.avisos_correo)
    return data
