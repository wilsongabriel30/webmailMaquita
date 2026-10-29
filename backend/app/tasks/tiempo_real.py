"""Tiempo real de las listas compartidas (como en To Do, F4 30/10/2026).

Va como dependencia de todas las rutas de Tareas: en cada cambio (todo lo que no es GET) mira a qué listas toca la
petición, antes y después (al mover, la tarea cambia de lista; al borrar, ya no está), y a las demás personas de esas
listas les manda `tareas_cambio` para que su pantalla se ponga al día. Si la petición falla, no avisa.
Las listas sin compartir no generan ningún mensaje. Desde la F5 también se avisa a quienes tienen la tarea asignada
aunque no estén en su lista.
"""

from __future__ import annotations

import logging
import uuid

from fastapi import Depends, Request

from app.auth.dependencies import get_current_user
from app.tasks import avisos_listas

logger = logging.getLogger(__name__)

_POR_PARAMETRO = {
    "list_id": "SELECT $1::uuid",
    "card_id": "SELECT list_id FROM task_cards WHERE id = $1",
    "step_id": "SELECT c.list_id FROM task_steps s JOIN task_cards c ON c.id = s.card_id WHERE s.id = $1",
    "adjunto_id": "SELECT c.list_id FROM task_adjuntos a JOIN task_cards c ON c.id = a.card_id WHERE a.id = $1",
}


async def _listas(db, parametros: dict) -> set:
    listas = set()
    for nombre, sql in _POR_PARAMETRO.items():
        valor = parametros.get(nombre)
        if not valor:
            continue
        try:
            list_id = await db.fetchval(sql, uuid.UUID(str(valor)))
        except Exception:  # id mal formado o ya borrado
            continue
        if list_id:
            listas.add(list_id)
    return listas


_ASIGNADOS = {
    "card_id": "SELECT email AS user_email FROM task_asignados WHERE card_id = $1",
    "step_id": """SELECT a.email AS user_email FROM task_steps s
                   JOIN task_asignados a ON a.card_id = s.card_id WHERE s.id = $1""",
    "adjunto_id": """SELECT a.email AS user_email FROM task_adjuntos d
                      JOIN task_asignados a ON a.card_id = d.card_id WHERE d.id = $1""",
}


async def _asignados(db, parametros: dict) -> set:
    personas = set()
    for nombre, sql in _ASIGNADOS.items():
        valor = parametros.get(nombre)
        if not valor:
            continue
        try:
            rows = await db.fetch(sql, uuid.UUID(str(valor)))
        except Exception:
            continue
        personas |= {r["user_email"] for r in rows}
    return personas


async def _personas(db, listas: set) -> set:
    if not listas:
        return set()
    rows = await db.fetch(
        "SELECT DISTINCT user_email FROM task_list_members WHERE list_id = ANY($1::uuid[])",
        list(listas),
    )
    return {r["user_email"] for r in rows}


async def avisar_cambios(request: Request, user: str = Depends(get_current_user)):
    if request.method in ("GET", "HEAD", "OPTIONS"):
        yield
        return
    db = request.app.state.db_pool
    try:
        listas = await _listas(db, request.path_params)
        personas = await _personas(db, listas) | await _asignados(
            db, request.path_params
        )
    except Exception:
        logger.debug(
            "tiempo real: no se pudo ver la lista antes del cambio", exc_info=True
        )
        listas, personas = set(), set()
    yield
    try:
        despues = await _listas(db, request.path_params)
        personas |= await _personas(db, despues - listas)
        personas |= await _asignados(db, request.path_params)
        otras = personas - {user}
        if otras:
            await avisos_listas.cambio(
                request.app.state.redis, sorted(otras), listas | despues
            )
    except Exception:
        logger.debug("tiempo real: aviso no enviado", exc_info=True)
