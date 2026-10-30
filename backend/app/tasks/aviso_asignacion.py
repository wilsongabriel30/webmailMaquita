"""Avisos de «Asignar tarea a:» con plazo e indicaciones, y aviso de tarea realizada (30/10/2026).

- Al asignar: el aviso y el correo dicen quién la asignó, el plazo para realizarla y las indicaciones.
- Al completarla (botón «Marcar como realizada», el círculo o la edición): a quien la asignó le llegan un aviso en
  pantalla y un correo de que ya está realizada. A quien la completa no se le avisa de lo suyo.

Un aviso que no sale no rompe la operación (avisos_listas ya lo protege).
"""

from __future__ import annotations

import logging
from datetime import datetime

from app.tareas import avisos
from app.tasks import avisos_listas

logger = logging.getLogger(__name__)

_DIAS = ("lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo")
_MESES = (
    "enero",
    "febrero",
    "marzo",
    "abril",
    "mayo",
    "junio",
    "julio",
    "agosto",
    "septiembre",
    "octubre",
    "noviembre",
    "diciembre",
)


def fecha_larga(fecha: datetime) -> str:
    """«viernes 31 de octubre de 2026». La fecha de vencimiento se guarda como día (medianoche), sin hora."""
    return f"{_DIAS[fecha.weekday()]} {fecha.day} de {_MESES[fecha.month - 1]} de {fecha.year}"


def texto_asignada(
    por: str, titulo: str, lista: str, plazo: datetime | None, indicaciones: str
) -> str:
    texto = f"{avisos.nombre(por)} te asignó la tarea «{titulo}» (lista «{lista}»)."
    if plazo is not None:
        texto += f" Plazo para realizarla: {fecha_larga(plazo)}."
    if indicaciones.strip():
        texto += f" Indicaciones: «{indicaciones.strip()}»"
    return texto


async def avisar_realizada(db, redis, user: str, card_id) -> None:
    """La tarea quedó completada: avisar por pantalla y por correo a quien la asignó."""
    try:
        fila = await db.fetchrow("SELECT title FROM task_cards WHERE id = $1", card_id)
        if fila is None:
            return
        quienes = [
            r["asignado_por"]
            for r in await db.fetch(
                "SELECT DISTINCT asignado_por FROM task_asignados WHERE card_id = $1 AND asignado_por <> ''",
                card_id,
            )
        ]
    except Exception:
        logger.warning("No se pudo preparar el aviso de tarea realizada", exc_info=True)
        return
    if not quienes:
        return
    texto = f"{avisos.nombre(user)} marcó como realizada la tarea «{fila['title']}» que asignaste."
    await avisos_listas.avisar(
        redis,
        db,
        quienes,
        user,
        "completed",
        "Tarea realizada",
        texto,
        card_id,
        correo=True,
    )
