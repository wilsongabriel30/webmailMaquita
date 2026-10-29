"""Compartir listas (como en To Do, F4 30/10/2026).

- Solo la propietaria comparte una lista propia (no «Tareas» ni la del correo marcado) con personas de la casa
  (dominios de `organizacion.dominios_propios`), quita miembros o deja de compartirla.
- Un miembro ve la lista en su barra (al final, en su propio orden) y puede salirse cuando quiera.
- Al salir o quedar fuera, la persona deja de estar asignada a las tareas de esa lista y se le quitan de su «Mi día».
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, field_validator

from app import organizacion
from app.tareas import avisos
from app.tasks import acceso, actividad
from app.tasks.listas import NoEncontrada, SinPermiso, _siguiente_posicion

_CORREO = re.compile(r"^[a-z0-9._%+'-]+@([a-z0-9-]+\.)+[a-z]{2,}$")
MAX_MIEMBROS = 100


class Miembro(BaseModel):
    email: str
    nombre: str
    role: str
    added_by: str
    joined_at: Optional[datetime] = None


class NuevoMiembro(BaseModel):
    email: str

    @field_validator("email")
    @classmethod
    def _correo(cls, v: str) -> str:
        v = (v or "").strip().lower()
        if not _CORREO.match(v):
            raise ValueError("Correo no válido")
        return v


def de_la_casa(email: str) -> bool:
    return email.rsplit("@", 1)[-1] in organizacion.dominios_propios()


async def _lista(db, list_id):
    row = await db.fetchrow(
        "SELECT id, name, list_type, board_id FROM task_lists WHERE id = $1", list_id
    )
    if row is None:
        raise NoEncontrada()
    return row


async def rol(db, list_id, user: str) -> Optional[str]:
    return await db.fetchval(
        "SELECT role FROM task_list_members WHERE list_id = $1 AND user_email = $2",
        list_id,
        user,
    )


async def emails(db, list_id) -> list[str]:
    rows = await db.fetch(
        "SELECT user_email FROM task_list_members WHERE list_id = $1", list_id
    )
    return [r["user_email"] for r in rows]


async def miembros(db, user: str, list_id) -> list[Miembro]:
    if not await acceso.puede_ver_lista(db, list_id, user):
        raise NoEncontrada()
    rows = await db.fetch(
        """SELECT user_email, role, added_by, joined_at FROM task_list_members
            WHERE list_id = $1 ORDER BY role = 'owner' DESC, joined_at""",
        list_id,
    )
    return [
        Miembro(
            email=r["user_email"],
            nombre=avisos.nombre(r["user_email"]),
            role=r["role"],
            added_by=r["added_by"],
            joined_at=r["joined_at"],
        )
        for r in rows
    ]


async def agregar(db, user: str, list_id, email: str) -> Miembro:
    """La propietaria suma a una persona. Lanza ValueError con el motivo si no se puede."""
    lista = await _lista(db, list_id)
    if await rol(db, list_id, user) != "owner":
        raise SinPermiso()
    if lista["list_type"] != "custom":
        raise ValueError("Esta lista no se puede compartir")
    if not de_la_casa(email):
        raise ValueError("Solo se puede compartir con cuentas de la organización")
    if await rol(db, list_id, email):
        raise ValueError("Esa persona ya está en la lista")
    if len(await emails(db, list_id)) >= MAX_MIEMBROS:
        raise ValueError(f"Una lista admite hasta {MAX_MIEMBROS} personas")
    await db.execute(
        """INSERT INTO task_list_members (list_id, user_email, role, added_by, position)
           VALUES ($1, $2, 'member', $3, $4)""",
        list_id,
        email,
        user,
        await _siguiente_posicion(db, email),
    )
    await actividad.registrar(
        db,
        list_id,
        user,
        "member_added",
        f"Compartió la lista con {avisos.nombre(email)}",
    )
    return Miembro(
        email=email, nombre=avisos.nombre(email), role="member", added_by=user
    )


async def _limpiar(db, list_id, fuera: list[str]) -> None:
    """Quien ya no está en la lista deja de estar asignado a sus tareas y las pierde de su «Mi día»."""
    await db.execute(
        """DELETE FROM task_asignados WHERE email = ANY($2::text[])
              AND card_id IN (SELECT id FROM task_cards WHERE list_id = $1 AND NOT asignada)""",
        list_id,
        fuera,
    )
    await db.execute(
        """DELETE FROM task_mi_dia WHERE user_email = ANY($2::text[])
              AND card_id IN (SELECT id FROM task_cards WHERE list_id = $1)""",
        list_id,
        fuera,
    )
    await db.execute(
        """UPDATE task_cards SET assigned_to = NULL, updated_at = NOW()
            WHERE list_id = $1 AND NOT asignada AND assigned_to = ANY($2::text[])""",
        list_id,
        fuera,
    )


async def quitar(db, user: str, list_id, email: str) -> str:
    """La propietaria quita a un miembro, o un miembro se sale. Devuelve el nombre de la lista."""
    lista = await _lista(db, list_id)
    mio = await rol(db, list_id, user)
    suyo = await rol(db, list_id, email)
    if mio is None:
        raise NoEncontrada()
    if suyo is None:
        raise NoEncontrada()
    if suyo == "owner":
        raise ValueError(
            "La propietaria no puede salir de su lista: puede dejar de compartirla o eliminarla"
        )
    if email != user and mio != "owner":
        raise SinPermiso()
    await db.execute(
        "DELETE FROM task_list_members WHERE list_id = $1 AND user_email = $2",
        list_id,
        email,
    )
    await _limpiar(db, list_id, [email])
    texto = (
        "Salió de la lista"
        if email == user
        else f"Quitó a {avisos.nombre(email)} de la lista"
    )
    await actividad.registrar(db, list_id, user, "member_removed", texto)
    return lista["name"]


async def dejar_de_compartir(db, user: str, list_id) -> list[str]:
    """La propietaria saca a todos los miembros. Devuelve a quiénes sacó."""
    await _lista(db, list_id)
    if await rol(db, list_id, user) != "owner":
        raise SinPermiso()
    rows = await db.fetch(
        "DELETE FROM task_list_members WHERE list_id = $1 AND role = 'member' RETURNING user_email",
        list_id,
    )
    fuera = [r["user_email"] for r in rows]
    if fuera:
        await _limpiar(db, list_id, fuera)
        await actividad.registrar(
            db, list_id, user, "unshared", "Dejó de compartir la lista"
        )
    return fuera
