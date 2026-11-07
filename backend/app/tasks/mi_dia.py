"""«Mi día» de cada persona (como en To Do): se arma para hoy y se vacía solo a medianoche de Guayaquil.

Se guarda por persona y fecha en `task_mi_dia`. A medianoche no se borra nada: la vista solo mira la
fecha de hoy, así que el día siguiente empieza vacío y la tarea sigue en su lista. Antes era una
columna de la tarea (`my_day`), común a todas las personas de la lista y que nunca se vaciaba.
"""

from __future__ import annotations

from datetime import date, datetime
from zoneinfo import ZoneInfo

ZONA = ZoneInfo("America/Guayaquil")


def hoy() -> date:
    return datetime.now(ZONA).date()


def medianoche(dia: date) -> datetime:
    """Comienzo del día en Guayaquil: así se guarda una fecha de vencimiento sin hora (04/11/2026)."""
    return datetime(dia.year, dia.month, dia.day, tzinfo=ZONA)


def en_guayaquil(valor: datetime | None) -> datetime | None:
    """Una fecha u hora sin zona («AAAA-MM-DD» del formulario) se entiende en hora de Guayaquil.

    Sin esto, asyncpg la guardaba en la zona del proceso: medianoche de Guayaquil en este servidor, pero medianoche
    UTC en uno configurado en UTC, y entonces «Vence hoy», Sugerencias y el Calendario la ponían el día anterior.
    """
    if valor is not None and valor.tzinfo is None:
        return valor.replace(tzinfo=ZONA)
    return valor


async def poner(db, user: str, card_id, en_mi_dia: bool) -> None:
    if en_mi_dia:
        await db.execute(
            "INSERT INTO task_mi_dia (card_id, user_email, fecha) VALUES ($1, $2, $3) ON CONFLICT DO NOTHING",
            card_id,
            user,
            hoy(),
        )
    else:
        await db.execute(
            "DELETE FROM task_mi_dia WHERE card_id = $1 AND user_email = $2 AND fecha = $3",
            card_id,
            user,
            hoy(),
        )


async def alternar(db, user: str, card_id) -> bool:
    """Quita la tarea de «Mi día» si estaba; si no, la agrega. Devuelve si quedó en «Mi día»."""
    borradas = await db.execute(
        "DELETE FROM task_mi_dia WHERE card_id = $1 AND user_email = $2 AND fecha = $3",
        card_id,
        user,
        hoy(),
    )
    if borradas != "DELETE 0":
        return False
    await poner(db, user, card_id, True)
    return True
