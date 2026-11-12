"""Subtareas (pasos) de una tarea asignada: quién las ve y a quién se avisa (12/11/2026).

Las rutas de pasos solo dejaban entrar a quien tenía la tarea en una de sus listas. En una tarea
asignada (Seguimiento) la persona que la RECIBE no la tiene en sus listas: el servidor le negaba
las subtareas (403) y no las veía, aunque quien asignó las hubiera escrito. Aquí se añade el
acceso propio de la tarea asignada:

  - quien la asignó: ve, añade, marca, renombra y borra subtareas;
  - quien la recibió: las ve, las marca como hechas y puede añadir las suyas; no renombra ni borra.

Y cuando alguien añade subtareas a una tarea asignada, se avisa a las demás personas de la tarea
(una vez por tanda, no un aviso por cada subtarea).
"""

from __future__ import annotations

import logging

from fastapi import HTTPException

from app.tasks import acceso

log = logging.getLogger(__name__)

VENTANA_AVISO_SEG = 180
SOLO_QUIEN_ASIGNO = ("editar", "borrar")

_PARTES = """SELECT c.created_by, c.asignada, c.title,
       COALESCE((SELECT array_agg(a.email) FROM task_asignados a WHERE a.card_id = c.id), '{}') AS asignados
  FROM task_cards c WHERE c.id = $1"""


async def papel(db, card_id, user: str) -> str:
    """«dueno» (la tiene en sus listas o la asignó), «asignado» (la recibió) o «» (no participa)."""
    if await acceso.puede_ver_tarea(db, card_id, user):
        return "dueno"
    fila = await db.fetchrow(_PARTES, card_id)
    if not fila or not fila["asignada"]:
        return ""
    if fila["created_by"] == user:
        return "dueno"
    return "asignado" if user in (fila["asignados"] or []) else ""


async def exigir(db, card_id, user: str, accion: str) -> str:
    """accion: ver | crear | marcar | editar | borrar. Devuelve el papel o responde 403."""
    quien = await papel(db, card_id, user)
    if not quien:
        raise HTTPException(403, "No tiene acceso a esta tarea")
    if quien == "asignado" and accion in SOLO_QUIEN_ASIGNO:
        raise HTTPException(
            403, "Solo quien asignó la tarea puede cambiar o borrar sus subtareas"
        )
    return quien


async def exigir_paso(db, step_id, user: str, accion: str):
    """Lo mismo a partir del identificador del paso. Devuelve el identificador de la tarea."""
    card_id = await db.fetchval("SELECT card_id FROM task_steps WHERE id = $1", step_id)
    if card_id is None:
        raise HTTPException(404, "Paso no encontrado")
    await exigir(db, card_id, user, accion)
    return card_id


async def avisar_subtareas(db, redis, card_id, user: str) -> int:
    """Avisa a las demás personas de una tarea asignada de que hay subtareas nuevas. Nunca rompe la operación."""
    try:
        fila = await db.fetchrow(_PARTES, card_id)
        if not fila or not fila["asignada"]:
            return 0
        otras = sorted(
            {fila["created_by"], *(fila["asignados"] or [])} - {user, None, ""}
        )
        if not otras:
            return 0
        if redis is not None:
            clave = f"tareas:aviso-subtareas:{card_id}:{user}"
            if not await redis.set(clave, "1", nx=True, ex=VENTANA_AVISO_SEG):
                return 0  # ya se avisó de esta tanda
        from app.tareas import avisos

        return await avisos.emitir(
            otras,
            f"{avisos.nombre(user)} añadió subtareas",
            fila["title"],
            avisos.url_tarea(card_id),
            user,
            {"tarea_id": str(card_id), "accion": "subtareas"},
            db,
            card_id,
        )
    except Exception as error:  # el aviso es un extra: la subtarea ya quedó guardada
        log.warning(
            "No se pudo avisar de las subtareas nuevas: %s", type(error).__name__
        )
        return 0
