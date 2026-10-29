"""Listas propias y grupos de listas (como en To Do, F2 29/10/2026).

- Cada persona ve las listas en las que figura en `task_list_members`: las suyas y las compartidas.
- El grupo y la posición en la barra lateral son de cada persona (columnas de `task_list_members`),
  así cada una ordena su barra a su gusto aunque la lista sea compartida.
- Solo la propietaria cambia el nombre, el color o el ícono de una lista, o la elimina. El orden de
  las tareas (`sort_by`) lo puede cambiar cualquiera que vea la lista.
- Borrar un grupo no borra sus listas: quedan fuera de grupo (ON DELETE SET NULL).
"""

from __future__ import annotations

import re
import uuid
from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator

from app.core.sanitize import strip_html
from app.tasks import acceso, adjuntos
from app.tasks.service import task_service

ORDENES = ("manual", "date", "important", "alpha", "created")
_COLOR = re.compile(r"^#[0-9a-fA-F]{6}$")
MAX_NOMBRE = 120


def _nombre(v: Optional[str]) -> Optional[str]:
    if v is None:
        return None
    v = strip_html(v).strip()[:MAX_NOMBRE]
    if not v:
        raise ValueError("El nombre no puede quedar vacío")
    return v


class ListaNueva(BaseModel):
    name: str
    color: str = "#e0e0e0"
    icon: str = ""

    _n = field_validator("name")(_nombre)

    @field_validator("color")
    @classmethod
    def _c(cls, v):
        if not _COLOR.match(v):
            raise ValueError("Color no válido")
        return v.lower()


class ListaCambio(BaseModel):
    name: Optional[str] = None
    color: Optional[str] = None
    icon: Optional[str] = Field(default=None, max_length=16)
    sort_by: Optional[Literal["manual", "date", "important", "alpha", "created"]] = None

    _n = field_validator("name")(_nombre)

    @field_validator("color")
    @classmethod
    def _c(cls, v):
        if v is not None and not _COLOR.match(v):
            raise ValueError("Color no válido")
        return v.lower() if v else v


class Lista(BaseModel):
    id: uuid.UUID
    board_id: uuid.UUID
    name: str
    position: int
    color: str
    list_type: str = "custom"
    icon: str = ""
    task_count: int = 0
    sort_by: str = "manual"
    group_id: Optional[uuid.UUID] = None
    role: str = "owner"
    miembros: int = 1


class GrupoNuevo(BaseModel):
    name: str

    _n = field_validator("name")(_nombre)


class GrupoCambio(BaseModel):
    name: Optional[str] = None

    _n = field_validator("name")(_nombre)


class Grupo(BaseModel):
    id: uuid.UUID
    name: str
    position: int


class ElementoBarra(BaseModel):
    """Un elemento de primer nivel de la barra: un grupo (con sus listas en orden) o una lista suelta."""

    tipo: Literal["grupo", "lista"]
    id: uuid.UUID
    listas: list[uuid.UUID] = Field(default_factory=list)


class OrdenBarra(BaseModel):
    elementos: list[ElementoBarra] = Field(max_length=500)


class OrdenTareas(BaseModel):
    ids: list[uuid.UUID] = Field(max_length=2000)


class SinPermiso(Exception):
    pass


class NoEncontrada(Exception):
    pass


_SELECT_LISTAS = """SELECT tl.id, tl.board_id, tl.name, m.position, tl.color, tl.list_type, tl.icon,
       tl.sort_by, m.group_id, m.role,
       (SELECT count(*) FROM task_cards c WHERE c.list_id = tl.id AND NOT c.completed) AS task_count,
       (SELECT count(*) FROM task_list_members o WHERE o.list_id = tl.id) AS miembros
  FROM task_list_members m
  JOIN task_lists tl ON tl.id = m.list_id
 WHERE m.user_email = $1 AND tl.list_type <> 'flagged'"""


def _lista(row) -> Lista:
    return Lista(**dict(row))


async def listas(db, user: str) -> list[Lista]:
    board_id = await task_service.ensure_default_board(db, user)
    await acceso.completar_propietarias(db, board_id, user)
    rows = await db.fetch(
        _SELECT_LISTAS + " ORDER BY tl.list_type = 'default' DESC, m.position, tl.name",
        user,
    )
    return [_lista(r) for r in rows]


async def una_lista(db, user: str, list_id) -> Lista:
    row = await db.fetchrow(_SELECT_LISTAS + " AND tl.id = $2", user, list_id)
    if not row:
        raise NoEncontrada()
    return _lista(row)


async def _siguiente_posicion(db, user: str) -> int:
    """Al final de la barra: después de las listas sueltas y de los grupos."""
    return await db.fetchval(
        """SELECT GREATEST(
                (SELECT COALESCE(MAX(position), -1) FROM task_list_members WHERE user_email = $1 AND group_id IS NULL),
                (SELECT COALESCE(MAX(position), -1) FROM task_list_groups WHERE owner = $1)) + 1""",
        user,
    )


async def crear_lista(db, user: str, data: ListaNueva) -> Lista:
    board_id = await task_service.ensure_default_board(db, user)
    pos = await _siguiente_posicion(db, user)
    list_id = await db.fetchval(
        """INSERT INTO task_lists (board_id, name, position, color, list_type, icon, owner)
           VALUES ($1, $2, $3, $4, 'custom', $5, $6) RETURNING id""",
        board_id,
        data.name,
        pos,
        data.color,
        data.icon,
        user,
    )
    await acceso.registrar_propietaria(db, list_id, user, pos)
    await task_service._log_activity(
        db, board_id, user, "list_created", f"Lista '{data.name}' creada"
    )
    return await una_lista(db, user, list_id)


async def cambiar_lista(db, user: str, list_id, data: ListaCambio) -> Lista:
    actual = await una_lista(db, user, list_id)
    cambios = data.model_dump(exclude_unset=True, exclude_none=True)
    if not cambios:
        raise ValueError("Nada que cambiar")
    solo_dueña = {"name", "color", "icon"} & cambios.keys()
    if solo_dueña and actual.role != "owner":
        raise SinPermiso()
    if "name" in cambios and actual.list_type == "default":
        raise ValueError("La lista «Tareas» no se puede renombrar")
    columnas = list(cambios)
    sets = ", ".join(f"{c} = ${i + 2}" for i, c in enumerate(columnas))
    await db.execute(
        f"UPDATE task_lists SET {sets} WHERE id = $1",
        list_id,
        *[cambios[c] for c in columnas],
    )
    return await una_lista(db, user, list_id)


async def eliminar_lista(db, user: str, list_id) -> None:
    actual = await una_lista(db, user, list_id)
    if actual.role != "owner":
        raise SinPermiso()
    if actual.list_type != "custom":
        raise ValueError("Esta lista no se puede eliminar")
    carpetas = await adjuntos.con_adjuntos(db, list_id=list_id)
    await db.execute("DELETE FROM task_lists WHERE id = $1", list_id)
    await adjuntos.borrar_carpetas(carpetas)
    await task_service._log_activity(
        db, actual.board_id, user, "list_deleted", f"Lista '{actual.name}' eliminada"
    )


# ── Grupos ──


async def grupos(db, user: str) -> list[Grupo]:
    rows = await db.fetch(
        "SELECT id, name, position FROM task_list_groups WHERE owner = $1 ORDER BY position, name",
        user,
    )
    return [Grupo(**dict(r)) for r in rows]


async def crear_grupo(db, user: str, data: GrupoNuevo) -> Grupo:
    pos = await _siguiente_posicion(db, user)
    row = await db.fetchrow(
        "INSERT INTO task_list_groups (owner, name, position) VALUES ($1, $2, $3) RETURNING id, name, position",
        user,
        data.name,
        pos,
    )
    return Grupo(**dict(row))


async def cambiar_grupo(db, user: str, group_id, data: GrupoCambio) -> Grupo:
    if data.name is None:
        raise ValueError("Nada que cambiar")
    row = await db.fetchrow(
        "UPDATE task_list_groups SET name = $3 WHERE id = $1 AND owner = $2 RETURNING id, name, position",
        group_id,
        user,
        data.name,
    )
    if not row:
        raise NoEncontrada()
    return Grupo(**dict(row))


async def eliminar_grupo(db, user: str, group_id) -> None:
    """Sus listas quedan sueltas, en el lugar que ocupaba el grupo."""
    pos = await db.fetchval(
        "SELECT position FROM task_list_groups WHERE id = $1 AND owner = $2",
        group_id,
        user,
    )
    if pos is None:
        raise NoEncontrada()
    await db.execute(
        "UPDATE task_list_members SET group_id = NULL, position = $3 WHERE group_id = $1 AND user_email = $2",
        group_id,
        user,
        pos,
    )
    await db.execute(
        "DELETE FROM task_list_groups WHERE id = $1 AND owner = $2", group_id, user
    )


# ── Orden ──


async def guardar_orden_barra(db, user: str, orden: OrdenBarra) -> None:
    """Guarda el orden de la barra tal como queda tras arrastrar: grupos, listas sueltas y listas de cada grupo.

    Solo se tocan las listas y grupos de esta persona; los ids ajenos se ignoran.
    """
    mis_grupos = {
        r["id"]
        for r in await db.fetch(
            "SELECT id FROM task_list_groups WHERE owner = $1", user
        )
    }
    mis_listas = {
        r["list_id"]
        for r in await db.fetch(
            "SELECT list_id FROM task_list_members WHERE user_email = $1", user
        )
    }
    for pos, el in enumerate(orden.elementos):
        if el.tipo == "grupo" and el.id in mis_grupos:
            await db.execute(
                "UPDATE task_list_groups SET position = $2 WHERE id = $1", el.id, pos
            )
            for i, lid in enumerate(el.listas):
                if lid in mis_listas:
                    await db.execute(
                        "UPDATE task_list_members SET group_id = $3, position = $4 WHERE list_id = $1 AND user_email = $2",
                        lid,
                        user,
                        el.id,
                        i,
                    )
        elif el.tipo == "lista" and el.id in mis_listas:
            await db.execute(
                "UPDATE task_list_members SET group_id = NULL, position = $3 WHERE list_id = $1 AND user_email = $2",
                el.id,
                user,
                pos,
            )


async def guardar_orden_tareas(db, user: str, list_id, orden: OrdenTareas) -> None:
    """Orden manual (arrastrando): la posición de cada tarea es su lugar en la lista recibida."""
    if not await acceso.puede_ver_lista(db, list_id, user):
        raise NoEncontrada()
    await db.execute(
        """UPDATE task_cards c SET position = o.pos - 1
             FROM unnest($2::uuid[]) WITH ORDINALITY AS o(id, pos)
            WHERE c.id = o.id AND c.list_id = $1""",
        list_id,
        orden.ids,
    )
