"""Quitar del tablero de Seguimiento las tareas completadas, sin borrarlas (05/11/2026).

El tablero guarda la trazabilidad: una tarea completada se queda en «Completada» hasta que la persona la quita
(«Quitar del tablero» o «Quitar todas») o hasta que pasan DIAS_AUTO días desde que se completó. Quitarla no borra
nada: pasa a «Archivadas», con su historial y comentarios, y se puede devolver al tablero.

Cada persona limpia SU tablero: si quien la recibió la archiva, quien la asignó la sigue viendo, y al revés
(una fila por persona en `task_archivadas`). Una tarea reabierta vuelve al tablero de todos.
"""

from __future__ import annotations

DIAS_AUTO = 30
MAX_IDS = 500

DDL = """
CREATE TABLE IF NOT EXISTS task_archivadas (
    card_id    UUID NOT NULL REFERENCES task_cards(id) ON DELETE CASCADE,
    user_email TEXT NOT NULL,
    archivada  BOOLEAN NOT NULL,  -- FALSE = la devolvió al tablero (no se archiva sola hasta pasados DIAS_AUTO)
    en         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (card_id, user_email)
);
"""


def archivada(persona: str = "$1") -> str:
    """Condición SQL: la tarea `c` está fuera del tablero de `persona` (a mano o por antigüedad)."""
    return f"""(c.completed AND (
        EXISTS (SELECT 1 FROM task_archivadas x
                 WHERE x.card_id = c.id AND x.user_email = {persona} AND x.archivada)
        OR (c.completed_at < NOW() - INTERVAL '{DIAS_AUTO} days'
            AND NOT EXISTS (SELECT 1 FROM task_archivadas x
                             WHERE x.card_id = c.id AND x.user_email = {persona} AND NOT x.archivada
                               AND x.en > NOW() - INTERVAL '{DIAS_AUTO} days'))))"""


_PARTICIPA = """c.asignada AND (c.created_by = $1
    OR EXISTS (SELECT 1 FROM task_asignados a WHERE a.card_id = c.id AND a.email = $1))"""


async def _marcar(db, user: str, ids: list, archivar: bool) -> int:
    filas = await db.fetch(
        f"""INSERT INTO task_archivadas (card_id, user_email, archivada, en)
            SELECT c.id, $1, $3, NOW() FROM task_cards c
             WHERE c.id = ANY($2::uuid[]) AND c.completed AND {_PARTICIPA}
            ON CONFLICT (card_id, user_email) DO UPDATE SET archivada = EXCLUDED.archivada, en = NOW()
            RETURNING card_id""",
        user,
        list(ids)[:MAX_IDS],
        archivar,
    )
    return len(filas)


async def archivar(db, user: str, ids: list) -> int:
    """Quita del tablero de `user` las completadas de `ids` en las que participa. Devuelve cuántas."""
    return await _marcar(db, user, ids, True)


async def restaurar(db, user: str, card_id) -> None:
    """Devuelve la tarea al tablero de `user` (y no se vuelve a archivar sola hasta dentro de DIAS_AUTO días)."""
    if not await _marcar(db, user, [card_id], False):
        raise LookupError("Tarea no encontrada")


async def olvidar(db, card_id) -> None:
    """La tarea se reabrió: vuelve al tablero de todos."""
    await db.execute("DELETE FROM task_archivadas WHERE card_id = $1", card_id)
