"""Mover una tarea a otra lista (como en To Do, F3 30/10/2026): arrastrándola a la barra o con «Mover a…».

- Hay que ver la tarea y la lista de destino (propia, compartida o «Tareas»).
- Las tareas de un correo marcado y las de Seguimiento (T-34) no se mueven: dependen de su lista.
- La tarea queda al final de las pendientes de la lista nueva y conserva todo lo demás.
"""

from __future__ import annotations

from app.tasks import acceso
from app.tasks.service import task_service


class NoSeMueve(Exception):
    pass


async def mover(db, user: str, card_id, list_id) -> None:
    """`db` debe ir dentro de una transacción. Lanza LookupError si no ve la tarea o la lista."""
    tarea = await db.fetchrow(
        """SELECT tc.title, tc.list_id, tc.asignada, tl.list_type, tl.board_id, tl.name
             FROM task_cards tc JOIN task_lists tl ON tl.id = tc.list_id WHERE tc.id = $1""",
        card_id,
    )
    if tarea is None or not await acceso.puede_ver_lista(db, tarea["list_id"], user):
        raise LookupError("Tarea no encontrada")
    destino = await db.fetchrow(
        "SELECT list_type, board_id, name FROM task_lists WHERE id = $1", list_id
    )
    if destino is None or not await acceso.puede_ver_lista(db, list_id, user):
        raise LookupError("Lista no encontrada")
    if tarea["asignada"] or tarea["list_type"] == "flagged":
        raise NoSeMueve("Esta tarea no se puede mover a otra lista")
    if destino["list_type"] not in ("custom", "default"):
        raise NoSeMueve("No se pueden mover tareas a esa lista")
    if tarea["list_id"] == list_id:
        return
    await db.execute(
        """UPDATE task_cards SET list_id = $2, updated_at = NOW(),
                  position = (SELECT COALESCE(MAX(position), -1) + 1 FROM task_cards WHERE list_id = $2)
            WHERE id = $1""",
        card_id,
        list_id,
    )
    detalle = f"'{tarea['title']}' movida de '{tarea['name']}' a '{destino['name']}'"
    await task_service._log_activity(
        db, tarea["board_id"], user, "card_moved", detalle, card_id
    )
    if destino["board_id"] != tarea["board_id"]:
        await task_service._log_activity(
            db, destino["board_id"], user, "card_moved", detalle, card_id
        )
