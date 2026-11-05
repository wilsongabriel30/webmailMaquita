"""Las tareas con seguimiento no se pierden al borrar la lista o el tablero donde están (05/11/2026).

Desde la fase 2, asignar una tarea de lista la convierte en tarea con seguimiento y se queda en su lista. Si la dueña
de la lista la elimina (o el tablero entero), la tarea con seguimiento se borraría en cascada, y con ella el trabajo y
la trazabilidad de quien la recibió. Antes de borrar, se pasan a la lista «Tareas» de quien las asignó.
"""

from __future__ import annotations

from app.tasks.service import task_service


async def rescatar(db, list_ids: list) -> int:
    """Mueve las tareas con seguimiento de `list_ids` a la lista «Tareas» de quien las asignó. Devuelve cuántas."""
    filas = await db.fetch(
        "SELECT id, created_by FROM task_cards WHERE list_id = ANY($1::uuid[]) AND asignada",
        list(list_ids),
    )
    movidas = 0
    for f in filas:
        destino = await task_service._get_default_list_id(db, f["created_by"])
        if destino is None or destino in list_ids:
            continue  # quien asignó borra su propio tablero: no hay adónde llevarla
        await db.execute(
            """UPDATE task_cards SET list_id = $2, updated_at = NOW(),
                      position = (SELECT COALESCE(MAX(position), -1) + 1 FROM task_cards WHERE list_id = $2)
                WHERE id = $1""",
            f["id"],
            destino,
        )
        movidas += 1
    return movidas
