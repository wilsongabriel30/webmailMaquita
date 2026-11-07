"""Completar o reabrir desde su lista una tarea con seguimiento (fase 3 de la unificación, 05/11/2026).

Desde la fase 2, «Asignar tarea a:» convierte la tarea de la lista en una tarea con seguimiento, que se queda en su
lista. Si se marca o desmarca desde ahí (el círculo, «Marcar como completada»), el cambio debe pasar por Seguimiento:
estado «completada», aviso a quien la asignó, siguiente de la cadena y repetición. Por el camino de las listas solo
cambiaba `completed` y la tarea quedaba «pendiente» en Seguimiento.
"""

from __future__ import annotations

from app.tareas.servicio import servicio_tareas
from app.tasks import vistas
from app.tasks.schemas import CardOut


class NoParticipa(Exception):
    """Quien la marca no la recibió ni la asignó."""


async def es_seguimiento(db, card_id) -> bool:
    return bool(
        await db.fetchval("SELECT asignada FROM task_cards WHERE id = $1", card_id)
    )


async def puede_eliminar(db, user: str, card_id) -> None:
    """Una tarea con seguimiento solo la elimina quien la asignó (la lista no basta): lo demás, archivarla."""
    fila = await db.fetchrow(
        "SELECT asignada, created_by FROM task_cards WHERE id = $1", card_id
    )
    if fila and fila["asignada"] and (fila["created_by"] or "").lower() != user.lower():
        raise NoParticipa(
            "Esta tarea tiene seguimiento: solo quien la asignó puede eliminarla"
        )


async def marcar(db, redis, user: str, card_id, completada: bool) -> CardOut:
    """Completa (o reabre como pendiente) la tarea por Seguimiento y devuelve la tarjeta de la lista."""
    try:
        if completada:
            await servicio_tareas.completar(db, redis, user, card_id)
        else:
            await servicio_tareas.cambiar_estado(db, redis, user, card_id, "pendiente")
    except PermissionError as e:
        raise NoParticipa(
            "Esta tarea tiene seguimiento: la completan quienes la recibieron o quien la asignó"
        ) from e
    tarjeta = await vistas.una(db, user, card_id)
    if tarjeta is None:
        raise LookupError("Tarea no encontrada")
    return tarjeta
