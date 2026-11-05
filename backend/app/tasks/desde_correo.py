"""Tareas creadas al soltar correos en el ícono Tareas (06/11/2026).

Una tarea por correo soltado, en la lista «Tareas» de quien los suelta. Cada una guarda a qué mensaje
apunta (`task_correo_origen`) para abrirlo desde Tareas, como las de «Correo marcado». A diferencia de
aquellas, no toca la bandera del correo ni se completa sola.

Si un correo ya tiene una tarea abierta creada así, no se repite (soltarlo dos veces no duplica).
"""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator

from app.core.sanitize import strip_html
from app.tasks.service import task_service

MAX_CORREOS = 50


class CorreoSoltado(BaseModel):
    carpeta: str = Field(min_length=1, max_length=500)
    uid: int = Field(gt=0)
    asunto: str = Field(default="", max_length=2000)
    remitente: str = Field(default="", max_length=1000)
    message_id: str = Field(default="", max_length=998)

    @field_validator("asunto", "remitente", "message_id")
    @classmethod
    def _texto(cls, v: str) -> str:
        return (strip_html(v or "") or "").strip()


class PedidoDesdeCorreo(BaseModel):
    correos: list[CorreoSoltado] = Field(min_length=1, max_length=MAX_CORREOS)


def _remitente_visible(remitente: str) -> str:
    """«Ana Pérez <ana@x.org>» → «Ana Pérez»; sin nombre, la dirección."""
    nombre = remitente.split("<", 1)[0].strip().strip('"').strip()
    return nombre or remitente.strip("<> ") or "remitente desconocido"


async def crear(con, user: str, correos: list[CorreoSoltado]) -> dict:
    """Crea las tareas. `con` va dentro de una transacción. Devuelve los ids creados y los repetidos."""
    await con.execute(
        "SELECT pg_advisory_xact_lock(hashtext($1))", "tareas-soltar:" + user
    )
    list_id = await task_service._get_default_list_id(con, user)
    board_id = await task_service._get_board_id_for_list(con, list_id)
    creadas, repetidas = [], 0
    vistos: set[tuple[str, int]] = set()
    for c in correos:
        clave = (c.carpeta, c.uid)
        if clave in vistos:
            continue
        vistos.add(clave)
        ya = await con.fetchval(
            """SELECT 1 FROM task_correo_origen o JOIN task_cards tc ON tc.id = o.card_id
                WHERE o.user_email = $1 AND o.carpeta = $2 AND o.uid = $3 AND NOT tc.completed""",
            user,
            c.carpeta,
            c.uid,
        )
        if ya:
            repetidas += 1
            continue
        titulo = c.asunto[:500] or "(sin asunto)"
        posicion = await con.fetchval(
            "SELECT COALESCE(MAX(position), -1) + 1 FROM task_cards WHERE list_id = $1",
            list_id,
        )
        card_id = await con.fetchval(
            """INSERT INTO task_cards (list_id, title, description, note, created_by, position)
               VALUES ($1, $2, '', $3, $4, $5) RETURNING id""",
            list_id,
            titulo,
            f"Creada desde el correo de {_remitente_visible(c.remitente)}",
            user,
            posicion,
        )
        await con.execute(
            """INSERT INTO task_correo_origen (card_id, user_email, carpeta, uid, message_id, asunto, remitente)
               VALUES ($1, $2, $3, $4, $5, $6, $7)""",
            card_id,
            user,
            c.carpeta,
            c.uid,
            c.message_id,
            titulo,
            c.remitente[:300],
        )
        if board_id:
            await task_service._log_activity(
                con,
                board_id,
                user,
                "card_created",
                f"Tarea '{titulo}' creada desde un correo",
                card_id,
            )
        creadas.append(card_id)
    return {"creadas": creadas, "repetidas": repetidas}
