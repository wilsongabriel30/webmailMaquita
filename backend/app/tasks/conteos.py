"""Números de la barra lateral de Tareas (como en Outlook): tareas pendientes de cada vista.

Las vistas «inteligentes» (Mi día, Importante, Planeado, Asignado a mí, Tareas) no son listas guardadas,
así que `/tasks/lists` no traía su total y la barra lateral salía sin números. Se cuentan aquí en una
sola consulta. El correo marcado vive en el buzón: se cuenta aparte con una búsqueda IMAP (sin
descargar los mensajes), para no hacer esa conexión en cada cambio de una tarea.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, Request

from app.auth.dependencies import get_current_user
from app.tasks.service import task_service

logger = logging.getLogger(__name__)

router = APIRouter()


async def contar_vistas(db, user: str) -> dict[str, int]:
    board_id = await task_service.ensure_default_board(db, user)
    fila = await db.fetchrow(
        """SELECT count(*) FILTER (WHERE tc.my_day)                    AS mi_dia,
                  count(*) FILTER (WHERE tc.important)                 AS importante,
                  count(*) FILTER (WHERE tc.due_date IS NOT NULL)      AS planeado,
                  count(*) FILTER (WHERE tc.assigned_to = $2)          AS asignado,
                  count(*) FILTER (WHERE tl.list_type = 'default')     AS tareas
             FROM task_cards tc
             JOIN task_lists tl ON tl.id = tc.list_id
            WHERE tl.board_id = $1 AND tc.completed = FALSE""",
        board_id,
        user,
    )
    return {
        "my-day": fila["mi_dia"],
        "important": fila["importante"],
        "planned": fila["planeado"],
        "assigned": fila["asignado"],
        "tasks": fila["tareas"],
    }


@router.get("/views/counts")
async def conteo_de_vistas(request: Request, user: str = Depends(get_current_user)):
    """Tareas pendientes de cada vista, con las mismas claves que usa el frontend."""
    return await contar_vistas(request.app.state.db_pool, user)


@router.get("/views/flagged/count")
async def conteo_correo_marcado(
    request: Request, user: str = Depends(get_current_user)
):
    """Correos marcados de la Bandeja de entrada (lo mismo que lista la vista «Correo electrónico marcado»)."""
    from app.core.session import get_imap_login_user, get_user_password
    from app.mail.clients.imap_client import get_imap_connection
    from app.mail.services.message_service import list_messages

    try:
        password = await get_user_password(request, user)
        login_user = await get_imap_login_user(request, user)
        imap = await get_imap_connection(login_user, password)
    except Exception:
        logger.warning("No se pudo contar el correo marcado de %s", user, exc_info=True)
        return {"flagged": 0}
    try:
        resultado = await list_messages(imap, "INBOX", 1, 1, "is:flagged")
        return {"flagged": int((resultado or {}).get("total") or 0)}
    except Exception:
        logger.warning("No se pudo contar el correo marcado de %s", user, exc_info=True)
        return {"flagged": 0}
    finally:
        try:
            await imap.logout()
        except Exception:
            pass
