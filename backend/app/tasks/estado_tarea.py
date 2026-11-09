"""Estado de una tarea de lista para el modo Tablero de Tareas (09/11/2026).

Las tareas personales también se organizan en columnas: Pendiente, En curso y Completada (como el tablero de
Seguimiento). `task_cards.estado` ya existía para todas las tareas (default «pendiente»), pero solo lo usaban las
tareas con seguimiento. Aquí:

- Una tarea con seguimiento cambia de estado por Seguimiento (avisos, cadena, repetición, aceptación implícita).
- Una tarea personal guarda «pendiente» o «en curso» en `estado`. «Completada» se decide por `completed`, como
  siempre: completar o reabrir pasa por el mismo camino que el círculo de la lista (repetición, bandera del correo
  marcado y calendario), que recibe la ruta como `alternar`.
"""

from __future__ import annotations

from typing import Awaitable, Callable

from app.tareas.servicio import servicio_tareas
from app.tasks import acceso, seguimiento_en_lista, vistas
from app.tasks.schemas import CardOut

ESTADOS = ("pendiente", "en_curso", "completada")


class NoParticipa(Exception):
    """Tarea con seguimiento en la que quien la mueve no participa."""


async def cambiar(
    db,
    redis,
    user: str,
    card_id,
    estado: str,
    alternar: Callable[[], Awaitable[object]],
) -> CardOut:
    """Pone la tarea en `estado` y devuelve la tarjeta como la ve la lista."""
    if estado not in ESTADOS:
        raise ValueError("Estado no válido")
    if not await acceso.puede_ver_tarea(db, card_id, user):
        raise LookupError("Tarea no encontrada")
    if await seguimiento_en_lista.es_seguimiento(db, card_id):
        try:
            await servicio_tareas.cambiar_estado(db, redis, user, card_id, estado)
        except PermissionError as e:
            raise NoParticipa(
                "Esta tarea tiene seguimiento: solo la mueven quienes la recibieron o quien la asignó"
            ) from e
    else:
        hecha = bool(
            await db.fetchval("SELECT completed FROM task_cards WHERE id = $1", card_id)
        )
        if (estado == "completada") != hecha:
            await alternar()  # completar o reabrir, con todo lo que eso hace en la lista
        if estado != "completada":
            await db.execute(
                "UPDATE task_cards SET estado = $2, updated_at = NOW() WHERE id = $1",
                card_id,
                estado,
            )
    tarjeta = await vistas.una(db, user, card_id)
    if tarjeta is None:
        raise LookupError("Tarea no encontrada")
    return tarjeta
