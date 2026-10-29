"""Quién puede ver una lista de tareas y sus tareas.

Desde la F0 (29/10/2026) cada lista tiene a sus personas en `task_list_members`: la propietaria y, si la
comparte, los miembros. El tablero sigue existiendo por compatibilidad: su dueño y los miembros del
tablero conservan el acceso que ya tenían.
Desde la F5 (31/10/2026) a quien se le asigna una tarea la ve aunque no esté en su lista («Asignar tarea a»): puede
abrirla, completarla y editarla, pero no borrarla ni moverla de lista.
"""

from __future__ import annotations

# Listas que ve una persona ($1): las suyas y las que le compartieron.
LISTAS_VISIBLES = "SELECT list_id FROM task_list_members WHERE user_email = $1"

_PUEDE_VER = """SELECT 1 FROM task_lists tl JOIN task_boards tb ON tb.id = tl.board_id
 WHERE tl.id = $1 AND (tb."user" = $2
    OR EXISTS (SELECT 1 FROM task_list_members m WHERE m.list_id = tl.id AND m.user_email = $2)
    OR EXISTS (SELECT 1 FROM task_board_members b WHERE b.board_id = tl.board_id AND b.user_email = $2))"""


async def puede_ver_lista(db, list_id, user: str) -> bool:
    return bool(await db.fetchval(_PUEDE_VER, list_id, user))


# La tarea tc está asignada a la persona $1. Seguimiento (T-34) también llena task_asignados, pero sus tareas
# (`asignada`) tienen su propia vista y su propio acceso: no entran aquí.
ASIGNADA_A = "(NOT tc.asignada AND EXISTS (SELECT 1 FROM task_asignados a WHERE a.card_id = tc.id AND a.email = $1))"


async def tarea_en_sus_listas(db, card_id, user: str) -> bool:
    """La tarea está en una lista que la persona ve (para borrarla hace falta esto)."""
    list_id = await db.fetchval("SELECT list_id FROM task_cards WHERE id = $1", card_id)
    return list_id is not None and await puede_ver_lista(db, list_id, user)


async def puede_ver_tarea(db, card_id, user: str) -> bool:
    if await db.fetchval(
        """SELECT 1 FROM task_asignados a JOIN task_cards c ON c.id = a.card_id
            WHERE a.card_id = $1 AND a.email = $2 AND NOT c.asignada""",
        card_id,
        user,
    ):
        return True
    return await tarea_en_sus_listas(db, card_id, user)


async def registrar_propietaria(db, list_id, user: str, position: int = 0) -> None:
    await db.execute(
        """INSERT INTO task_list_members (list_id, user_email, role, added_by, position)
           VALUES ($1, $2, 'owner', $2, $3) ON CONFLICT DO NOTHING""",
        list_id,
        user,
        position,
    )


async def completar_propietarias(db, board_id, user: str) -> None:
    """Listas del tablero propio sin su fila de propietaria (creadas por código anterior a la F0)."""
    await db.execute(
        """INSERT INTO task_list_members (list_id, user_email, role, added_by, position)
           SELECT tl.id, $2, 'owner', $2, tl.position FROM task_lists tl
            WHERE tl.board_id = $1
              AND NOT EXISTS (SELECT 1 FROM task_list_members m WHERE m.list_id = tl.id AND m.user_email = $2)
           ON CONFLICT DO NOTHING""",
        board_id,
        user,
    )
