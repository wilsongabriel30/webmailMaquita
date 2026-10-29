"""«Duplicar lista» del menú de la barra (como en To Do, F5 31/10/2026).

La copia es una lista nueva de quien duplica, sin compartir, en el mismo grupo y con el mismo color y orden. Lleva
todas las tareas (pendientes y completadas) con sus pasos, nota, importancia, fechas, repetición y categorías; no
lleva archivos, asignaciones, «Mi día» ni el enlace a un correo. Las de Seguimiento (T-34) no se copian.
"""

from __future__ import annotations

from app.tasks import listas
from app.tasks.listas import Lista, ListaNueva

_COPIAR_TAREAS = """
WITH origen AS (
    SELECT gen_random_uuid() AS nuevo, c.* FROM task_cards c WHERE c.list_id = $1 AND NOT c.asignada
), copia AS (
    INSERT INTO task_cards (id, list_id, title, description, due_date, priority, labels, position, created_by,
                            important, reminder, note, recurrence, completed, completed_by, completed_at)
    SELECT nuevo, $2, title, description, due_date, priority, labels, position, $3,
           important, reminder, note, recurrence, completed, completed_by, completed_at
      FROM origen
    RETURNING id
)
INSERT INTO task_steps (card_id, title, completed, position)
SELECT o.nuevo, s.title, s.completed, s.position
  FROM task_steps s JOIN origen o ON o.id = s.card_id
 WHERE EXISTS (SELECT 1 FROM copia WHERE copia.id = o.nuevo)
"""


def nombre_copia(nombre: str) -> str:
    sufijo = " (copia)"
    return nombre[: listas.MAX_NOMBRE - len(sufijo)] + sufijo


async def duplicar(db, user: str, list_id) -> Lista:
    """`db` debe ir dentro de una transacción: la lista y sus tareas se copian juntas."""
    original = await listas.una_lista(db, user, list_id)
    if original.list_type != "custom":
        raise ValueError("Solo se pueden duplicar las listas creadas por las personas")
    nueva = await listas.crear_lista(
        db,
        user,
        ListaNueva(
            name=nombre_copia(original.name),
            color=(
                original.color
                if listas._COLOR.match(original.color or "")
                else "#e0e0e0"
            ),
            icon=original.icon,
        ),
    )
    await db.execute(
        "UPDATE task_lists SET sort_by = $2 WHERE id = $1", nueva.id, original.sort_by
    )
    if original.group_id:
        await db.execute(
            """UPDATE task_list_members SET group_id = $3,
                      position = (SELECT COALESCE(MAX(position), -1) + 1 FROM task_list_members
                                   WHERE user_email = $2 AND group_id = $3)
                WHERE list_id = $1 AND user_email = $2""",
            nueva.id,
            user,
            original.group_id,
        )
    await db.execute(_COPIAR_TAREAS, list_id, nueva.id, user)
    return await listas.una_lista(db, user, nueva.id)
