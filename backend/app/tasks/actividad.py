"""Registro de actividad de las listas y las tareas (como en To Do, F4 30/10/2026).

Se lee de `task_activity`: lo que ya registraban las tareas (crear, completar, mover, borrar…) más lo nuevo de
compartir y asignar, que también guarda la lista (`list_id`). Cada evento sale con el nombre de quien lo hizo.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel

from app.tareas import avisos


class Evento(BaseModel):
    user_email: str
    nombre: str
    action: str
    details: str
    created_at: datetime


def _evento(row) -> Evento:
    return Evento(
        user_email=row["user_email"],
        nombre=avisos.nombre(row["user_email"]),
        action=row["action"],
        details=row["details"],
        created_at=row["created_at"],
    )


async def registrar(
    db, list_id, user: str, action: str, details: str, card_id=None
) -> None:
    await db.execute(
        """INSERT INTO task_activity (board_id, list_id, card_id, user_email, action, details)
           SELECT board_id, id, $2, $3, $4, $5 FROM task_lists WHERE id = $1""",
        list_id,
        card_id,
        user,
        action,
        details,
    )


async def de_tarea(db, card_id, limite: int = 50) -> list[Evento]:
    rows = await db.fetch(
        """SELECT user_email, action, details, created_at FROM task_activity
            WHERE card_id = $1 ORDER BY created_at DESC LIMIT $2""",
        card_id,
        limite,
    )
    return [_evento(r) for r in rows]


async def de_lista(db, list_id, limite: int = 100) -> list[Evento]:
    rows = await db.fetch(
        """SELECT user_email, action, details, created_at FROM task_activity
            WHERE list_id = $1 OR card_id IN (SELECT id FROM task_cards WHERE list_id = $1)
            ORDER BY created_at DESC LIMIT $2""",
        list_id,
        limite,
    )
    return [_evento(r) for r in rows]
