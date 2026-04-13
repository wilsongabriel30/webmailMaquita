"""task_calendar_sync.py — Sincronizacion tareas <-> calendario + notificaciones WebSocket.

Cuando se crea/actualiza una tarea con fecha (due_date) y/o asignado (assigned_to),
se crea automaticamente un evento en el calendario del responsable y se envia
notificacion via WebSocket (Redis pub/sub).

Autor: IA Code — 2026-04-13
"""
import json
import logging
import uuid
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


async def sync_task_to_calendar(db, redis, task_row: dict, created_by: str):
    """Crear/actualizar evento en calendario cuando una tarea tiene fecha.

    Se crea evento en el calendario del assigned_to (o del creador si no hay asignado).
    El evento tiene como titulo el nombre de la tarea y como descripcion los detalles.
    """
    due_date = task_row.get("due_date")
    if not due_date:
        return  # Sin fecha, no sincronizar

    assigned_to = task_row.get("assigned_to") or created_by
    task_id = str(task_row["id"])
    title = task_row.get("title", "Tarea")
    description = task_row.get("description", "")
    note = task_row.get("note", "")
    important = task_row.get("important", False)

    # Buscar calendario default del usuario asignado
    cal_row = await db.fetchrow(
        "SELECT id FROM calendars WHERE owner_email = $1 AND is_default = true",
        assigned_to,
    )
    if not cal_row:
        # Crear calendario default si no existe
        try:
            from app.calendar.service import calendar_service
            await calendar_service.ensure_default_calendar(db, assigned_to)
            cal_row = await db.fetchrow(
                "SELECT id FROM calendars WHERE owner_email = $1 AND is_default = true",
                assigned_to,
            )
        except Exception as e:
            logger.warning("No se pudo crear calendario para %s: %s", assigned_to, e)
            return

    if not cal_row:
        return

    calendar_id = cal_row["id"]

    # Verificar si ya existe un evento vinculado a esta tarea
    existing = await db.fetchrow(
        "SELECT id FROM events WHERE calendar_id = $1 AND summary LIKE $2",
        calendar_id, f"[Tarea] {title}%",
    )

    # Preparar datos del evento
    if isinstance(due_date, str):
        due_date = datetime.fromisoformat(due_date.replace("Z", "+00:00"))

    # Evento de todo el dia si no tiene hora especifica (hora = 00:00)
    all_day = due_date.hour == 0 and due_date.minute == 0
    dtstart = due_date
    dtend = due_date + timedelta(hours=1) if not all_day else due_date + timedelta(days=1)

    event_summary = "[Tarea] " + title
    if important:
        event_summary = "[!] " + event_summary

    event_description = ""
    if description:
        event_description += description + "\n"
    if note:
        event_description += "\nNotas: " + note
    event_description += "\n\n--- Creado por: " + created_by
    event_description += "\nTarea ID: " + task_id

    if existing:
        # Actualizar evento existente
        await db.execute(
            """UPDATE events SET summary=$2, description=$3, dtstart=$4, dtend=$5,
               all_day=$6, updated_at=NOW() WHERE id=$1""",
            existing["id"], event_summary, event_description.strip(),
            dtstart, dtend, all_day,
        )
        logger.info("Evento calendario actualizado para tarea %s -> %s", task_id, assigned_to)
    else:
        # Crear nuevo evento
        event_uid = "task-" + task_id + "-" + uuid.uuid4().hex[:8]
        await db.execute(
            """INSERT INTO events
               (calendar_id, uid, summary, description, location, dtstart, dtend,
                all_day, rrule, status, transparency, timezone, reminders, attendees)
               VALUES ($1, $2, $3, $4, '', $5, $6, $7, '', 'CONFIRMED', 'OPAQUE',
                       'America/Guayaquil', '[]'::jsonb, '[]'::jsonb)""",
            calendar_id, event_uid, event_summary, event_description.strip(),
            dtstart, dtend, all_day,
        )
        logger.info("Evento calendario creado para tarea %s -> %s", task_id, assigned_to)


async def remove_task_from_calendar(db, task_row: dict, assigned_to: str):
    """Eliminar evento del calendario cuando se completa o elimina una tarea."""
    title = task_row.get("title", "")
    cal_row = await db.fetchrow(
        "SELECT id FROM calendars WHERE owner_email = $1 AND is_default = true",
        assigned_to,
    )
    if not cal_row:
        return

    await db.execute(
        "DELETE FROM events WHERE calendar_id = $1 AND summary LIKE $2",
        cal_row["id"], f"[Tarea] {title}%",
    )
    logger.info("Evento calendario eliminado para tarea completada: %s", title)


async def notify_task_assignment(redis, task_row: dict, assigned_to: str, action: str, by_user: str):
    """Enviar notificacion WebSocket al usuario asignado via Redis pub/sub."""
    if not assigned_to or assigned_to == by_user:
        return  # No notificar al propio creador

    try:
        title = task_row.get("title", "Tarea")
        important = task_row.get("important", False)
        due_date = task_row.get("due_date")

        msg = {
            "type": "task_notification",
            "action": action,  # "assigned", "updated", "completed"
            "task_id": str(task_row["id"]),
            "task_title": title,
            "important": important,
            "due_date": str(due_date) if due_date else None,
            "by_user": by_user,
            "message": _build_notification_message(action, title, by_user),
        }

        await redis.publish(
            "ws:user:" + assigned_to,
            json.dumps(msg),
        )
        logger.info("Notificacion tarea enviada a %s: %s", assigned_to, action)
    except Exception as e:
        logger.warning("Error enviando notificacion tarea: %s", e)


def _build_notification_message(action: str, title: str, by_user: str) -> str:
    """Construir mensaje legible para la notificacion."""
    by_name = by_user.split("@")[0].replace(".", " ").title()
    if action == "assigned":
        return f"{by_name} te asigno la tarea: {title}"
    elif action == "updated":
        return f"{by_name} actualizo la tarea: {title}"
    elif action == "completed":
        return f"{by_name} completo la tarea: {title}"
    return f"Actualizacion de tarea: {title}"
