"""Panel «Sugerencias» de Mi día (como en To Do, F6 29/10/2026).

Tareas pendientes que la persona ve (sus listas, las compartidas y las que le asignaron) y que hoy no están en su
Mi día, en cuatro grupos: vencidas, vencen hoy, próximas (siete días) y agregadas en los últimos siete días sin
fecha. Las de Seguimiento (T-34) no salen: tienen su propia vista.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from pydantic import BaseModel

from app.tasks import mi_dia, vistas
from app.tasks.schemas import CardOut

POR_GRUPO = 20

# $3 = medianoche UTC de hoy (así se guardan los vencimientos), $4 = dentro de siete días.
_GRUPOS = {
    "vencidas": ("tc.due_date < $3::timestamptz", "tc.due_date DESC"),
    "hoy": (
        "tc.due_date >= $3::timestamptz AND tc.due_date < $3::timestamptz + interval '1 day'",
        "tc.position",
    ),
    "proximas": (
        "tc.due_date >= $3::timestamptz + interval '1 day' AND tc.due_date < $4::timestamptz",
        "tc.due_date",
    ),
    "recientes": (
        "tc.due_date IS NULL AND tc.created_at >= now() - interval '7 days'",
        "tc.created_at DESC",
    ),
}


class Sugerencias(BaseModel):
    vencidas: list[CardOut] = []
    hoy: list[CardOut] = []
    proximas: list[CardOut] = []
    recientes: list[CardOut] = []


async def sugerencias(db, user: str) -> Sugerencias:
    hoy = mi_dia.hoy()
    medianoche = datetime(hoy.year, hoy.month, hoy.day, tzinfo=timezone.utc)
    grupos = {}
    valores = (user, hoy, medianoche, medianoche + timedelta(days=7))
    for nombre, (filtro, orden) in _GRUPOS.items():
        # Cada grupo usa $1…$n: se pasan solo los que usa (asyncpg no acepta de más).
        n = max(i for i in range(1, 5) if f"${i}" in filtro or i <= 2)
        filas = await db.fetch(
            f"""{vistas._SELECT} AND NOT tc.completed AND NOT tc.asignada AND NOT {vistas._EN_MI_DIA}
                  AND {filtro} ORDER BY {orden} LIMIT {POR_GRUPO}""",
            *valores[:n],
        )
        grupos[nombre] = [vistas.a_tarjeta(f) for f in filas]
    return Sugerencias(**grupos)
