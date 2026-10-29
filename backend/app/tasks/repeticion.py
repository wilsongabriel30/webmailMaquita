"""Repetición de tareas (como en To Do, F3 30/10/2026): al completar una tarea que se repite, se crea la siguiente.

La regla va en `task_cards.recurrence`:
- Las de siempre: daily, weekdays, weekly, monthly, yearly.
- Personalizada: `cada:N:unidad` o `cada:N:semana:dias`, con unidad dia, semana, mes o anio y los días de la
  semana como números (0 = lunes … 6 = domingo). Ej.: `cada:2:semana:0,3` = cada 2 semanas, lunes y jueves.

La siguiente tarea copia título, nota, importancia, pasos (sin completar), personas asignadas y la regla; su
vencimiento es el siguiente que toca y el recordatorio se corre lo mismo. La completada pierde la regla en
la misma operación, así que reabrirla y volver a completarla no crea otra.

Seguimiento (T-34, `asignada`) tiene su propia repetición y aquí no se toca. Las fechas de vencimiento
se guardan como medianoche UTC del día elegido, así que los cálculos se hacen sobre ese día.
"""

from __future__ import annotations

import calendar
import re
from datetime import datetime, timedelta, timezone
from typing import Optional

from app.tasks import mi_dia

SIMPLES = ("daily", "weekdays", "weekly", "monthly", "yearly")
UNIDADES = ("dia", "semana", "mes", "anio")
MAX_INTERVALO = 999
_PERSONALIZADA = re.compile(
    r"^cada:(\d{1,3}):(dia|semana|mes|anio)(?::([0-6](?:,[0-6]){0,6}))?$"
)


def normalizar(regla: Optional[str]) -> Optional[str]:
    """Regla válida y en su forma canónica, o ValueError. Vacía = sin repetición."""
    if regla is None:
        return None
    regla = regla.strip()
    if not regla:
        return None
    if regla in SIMPLES:
        return regla
    m = _PERSONALIZADA.match(regla)
    if not m:
        raise ValueError("Repetición no válida")
    n, unidad, dias = int(m.group(1)), m.group(2), m.group(3)
    if not 1 <= n <= MAX_INTERVALO:
        raise ValueError("El intervalo de la repetición va de 1 a 999")
    if dias and unidad != "semana":
        raise ValueError("Los días de la semana solo valen para «semana»")
    texto = f"cada:{n}:{unidad}"
    if dias:
        texto += ":" + ",".join(
            str(d) for d in sorted({int(d) for d in dias.split(",")})
        )
    return texto


def _sumar_meses(base: datetime, meses: int) -> datetime:
    total = base.month - 1 + meses
    anio, mes = base.year + total // 12, total % 12 + 1
    return base.replace(
        year=anio, month=mes, day=min(base.day, calendar.monthrange(anio, mes)[1])
    )


def _semanal_con_dias(base: datetime, cada: int, dias: list[int]) -> datetime:
    """El siguiente día marcado de esta semana; si no queda ninguno, el primero de la semana que toca."""
    for d in dias:
        if d > base.weekday():
            return base + timedelta(days=d - base.weekday())
    lunes = base - timedelta(days=base.weekday())
    return lunes + timedelta(weeks=cada, days=dias[0])


def siguiente(regla: str, base: datetime) -> datetime:
    """Siguiente vencimiento después de `base` según la regla (ya normalizada)."""
    if regla == "daily":
        return base + timedelta(days=1)
    if regla == "weekdays":
        nuevo = base + timedelta(days=1)
        while nuevo.weekday() >= 5:
            nuevo += timedelta(days=1)
        return nuevo
    if regla == "weekly":
        return base + timedelta(weeks=1)
    if regla == "monthly":
        return _sumar_meses(base, 1)
    if regla == "yearly":
        return _sumar_meses(base, 12)
    _, n, unidad, *resto = regla.split(":")
    cada = int(n)
    if unidad == "dia":
        return base + timedelta(days=cada)
    if unidad == "semana":
        if resto:
            return _semanal_con_dias(base, cada, [int(d) for d in resto[0].split(",")])
        return base + timedelta(weeks=cada)
    if unidad == "mes":
        return _sumar_meses(base, cada)
    return _sumar_meses(base, 12 * cada)


def _hoy_utc() -> datetime:
    """Hoy (Guayaquil) como medianoche UTC, igual que se guardan los vencimientos."""
    h = mi_dia.hoy()
    return datetime(h.year, h.month, h.day, tzinfo=timezone.utc)


async def al_completar(db, user: str, card_id):
    """Si la tarea recién completada se repite, crea la siguiente y devuelve su id (si no, None).

    `db` debe ir dentro de una transacción: quitar la regla y crear la siguiente van juntos.
    """
    fila = await db.fetchrow(
        """UPDATE task_cards t SET recurrence = NULL
             FROM (SELECT id, recurrence FROM task_cards WHERE id = $1 FOR UPDATE) antes
            WHERE t.id = antes.id AND t.completed AND NOT t.asignada AND t.recurrence IS NOT NULL
              AND NOT EXISTS (SELECT 1 FROM task_correo co WHERE co.card_id = t.id)
        RETURNING t.*, antes.recurrence AS regla""",
        card_id,
    )
    if fila is None:
        return None
    try:
        regla = normalizar(fila["regla"])
    except ValueError:
        return None
    if regla is None:
        return None
    base = fila["due_date"] or _hoy_utc()
    vence = siguiente(regla, base)
    recordatorio = fila["reminder"] + (vence - base) if fila["reminder"] else None
    nueva = await db.fetchval(
        """INSERT INTO task_cards (list_id, title, description, due_date, priority, labels, position,
                                   created_by, important, reminder, note, recurrence)
           VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12) RETURNING id""",
        fila["list_id"],
        fila["title"],
        fila["description"],
        vence,
        fila["priority"],
        fila["labels"],
        fila["position"],
        user,
        fila["important"],
        recordatorio,
        fila["note"],
        regla,
    )
    await db.execute(
        """INSERT INTO task_steps (card_id, title, completed, position)
           SELECT $2, title, FALSE, position FROM task_steps WHERE card_id = $1""",
        card_id,
        nueva,
    )
    await db.execute(
        """INSERT INTO task_asignados (card_id, email, asignado_por)
           SELECT $2, email, asignado_por FROM task_asignados WHERE card_id = $1""",
        card_id,
        nueva,
    )
    return nueva


async def tras_completar(pool, user: str, card_id):
    """Para las rutas: crea la siguiente repetición en su propia transacción (None si no toca)."""
    async with pool.acquire() as con:
        async with con.transaction():
            return await al_completar(con, user, card_id)
