"""Asignar una tarea a varias personas de su lista (como en To Do, F4 30/10/2026).

Se asigna a personas que están en la lista (la propietaria o sus miembros), así que en una lista sin compartir solo
cabe asignársela a una misma. La lista completa de asignados reemplaza a la anterior. `assigned_to` (heredado, una
sola persona) queda con la primera, para lo que todavía lo lee. Seguimiento (T-34) asigna por su cuenta.
"""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator

from app.tareas import avisos
from app.tasks import acceso, actividad


class Asignacion(BaseModel):
    emails: list[str] = Field(default_factory=list, max_length=50)

    @field_validator("emails")
    @classmethod
    def _limpios(cls, v: list[str]) -> list[str]:
        vistos: list[str] = []
        for e in v:
            e = (e or "").strip().lower()
            if e and e not in vistos:
                vistos.append(e)
        return vistos


class NoSeAsigna(Exception):
    pass


async def asignar(db, user: str, card_id, emails: list[str]) -> tuple[list[str], dict]:
    """Deja la tarea asignada a `emails`. Devuelve (personas recién asignadas, fila de la tarea)."""
    tarea = await db.fetchrow(
        """SELECT tc.id, tc.title, tc.list_id, tc.asignada, tl.name AS lista
             FROM task_cards tc JOIN task_lists tl ON tl.id = tc.list_id WHERE tc.id = $1""",
        card_id,
    )
    if tarea is None or not await acceso.puede_ver_tarea(db, card_id, user):
        raise LookupError("Tarea no encontrada")
    if tarea["asignada"]:
        raise NoSeAsigna("Esta tarea se gestiona desde Seguimiento")
    en_lista = {
        r["user_email"]
        for r in await db.fetch(
            "SELECT user_email FROM task_list_members WHERE list_id = $1",
            tarea["list_id"],
        )
    }
    ajenos = [e for e in emails if e not in en_lista]
    if ajenos:
        raise NoSeAsigna(
            "Solo se puede asignar a personas de la lista: comparte la lista primero"
        )
    antes = {
        r["email"]
        for r in await db.fetch(
            "SELECT email FROM task_asignados WHERE card_id = $1", card_id
        )
    }
    nuevos = [e for e in emails if e not in antes]
    quitados = [e for e in antes if e not in emails]
    if quitados:
        await db.execute(
            "DELETE FROM task_asignados WHERE card_id = $1 AND email = ANY($2::text[])",
            card_id,
            quitados,
        )
    for e in nuevos:
        await db.execute(
            "INSERT INTO task_asignados (card_id, email, asignado_por) VALUES ($1, $2, $3) ON CONFLICT DO NOTHING",
            card_id,
            e,
            user,
        )
    await db.execute(
        "UPDATE task_cards SET assigned_to = $2, updated_at = NOW() WHERE id = $1",
        card_id,
        emails[0] if emails else None,
    )
    if nuevos or quitados:
        partes = []
        if nuevos:
            partes.append("asignó a " + ", ".join(avisos.nombre(e) for e in nuevos))
        if quitados:
            partes.append("quitó a " + ", ".join(avisos.nombre(e) for e in quitados))
        texto = f"'{tarea['title']}': " + "; ".join(partes)
        await actividad.registrar(
            db, tarea["list_id"], user, "card_assigned", texto, card_id
        )
    return nuevos, dict(tarea)
