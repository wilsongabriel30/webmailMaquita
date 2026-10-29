"""Recordatorios y avisos de vencimiento de Tareas (como en To Do, F5 31/10/2026).

Los usa el programador de recordatorios (`app/reminders_scheduler.py`, cada 60 s):
- A quién le llega el recordatorio de una tarea: a sus personas asignadas; si no tiene, a quien la creó (si sigue en
  la lista) y, si no, a la propietaria de la lista. Las de Seguimiento (T-34) siguen yendo solo a la propietaria.
- «Vence hoy»: desde las 08:00 (Guayaquil) del día de vencimiento, un aviso por tarea pendiente, reclamado de forma
  atómica con `vence_avisado` (una sola vez por fecha aunque haya varios procesos). Este aviso solo sale en pantalla
  (y como notificación del navegador): no manda correo.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, time, timezone

from app.tasks import mi_dia

logger = logging.getLogger("reminders")

HORA_AVISO = time(8, 0)

_ASIGNADOS = "SELECT email FROM task_asignados WHERE card_id = $1 ORDER BY asignado_en"
_EN_LISTA = "SELECT 1 FROM task_list_members WHERE list_id = $1 AND user_email = $2"

# $1 = medianoche UTC de hoy (así se guardan los vencimientos), $2 = fecha de hoy.
CLAIM_VENCE = """
UPDATE task_cards c SET vence_avisado = $2
FROM task_lists l
WHERE l.id = c.list_id
  AND c.due_date >= $1 AND c.due_date < $1 + interval '1 day'
  AND c.completed = FALSE
  AND NOT c.asignada
  AND c.vence_avisado IS DISTINCT FROM $2
RETURNING c.id, c.title, c.list_id, c.created_by, c.asignada, l.owner
"""


async def destinatarios(db, fila) -> list[str]:
    """Personas a las que avisar de una tarea (fila con id, list_id, created_by, asignada y owner)."""
    if fila["asignada"]:
        return [fila["owner"]]
    asignados = [r["email"] for r in await db.fetch(_ASIGNADOS, fila["id"])]
    if asignados:
        return asignados
    creadora = fila["created_by"]
    if creadora and await db.fetchval(_EN_LISTA, fila["list_id"], creadora):
        return [creadora]
    return [fila["owner"]]


def toca_avisar(ahora_local: datetime) -> bool:
    return ahora_local.time() >= HORA_AVISO


async def avisar_vencimientos(db, redis, ahora: datetime | None = None) -> int:
    """Reclama y publica los «Vence hoy» pendientes. Devuelve cuántas tareas avisó."""
    ahora = ahora or datetime.now(timezone.utc)
    if not toca_avisar(ahora.astimezone(mi_dia.ZONA)):
        return 0
    hoy = ahora.astimezone(mi_dia.ZONA).date()
    medianoche = datetime(hoy.year, hoy.month, hoy.day, tzinfo=timezone.utc)
    filas = await db.fetch(CLAIM_VENCE, medianoche, hoy)
    for f in filas:
        for persona in await destinatarios(db, f):
            try:
                await redis.publish(
                    f"ws:user:{persona}",
                    json.dumps(
                        {
                            "type": "reminder",
                            "message": f"📅 Vence hoy: {f['title']}",
                            "tag": f"task-due-{f['id']}-{hoy.isoformat()}",
                            "kind": "task",
                            "entity_id": str(f["id"]),
                            "link": "",
                        }
                    ),
                )
            except Exception:
                logger.warning("Aviso de vencimiento no enviado a %s", persona)
    return len(filas)
