"""Quitar del tablero de Seguimiento las completadas, sin borrarlas (05/11/2026)."""

from __future__ import annotations

import asyncio
import uuid

from app.tareas import archivo, servicio


class _DB:
    def __init__(self, devuelve=()):
        self.devuelve, self.sql = list(devuelve), []

    async def fetch(self, sql, *a):
        self.sql.append((sql, a))
        return self.devuelve


def test_tablero_ve_las_completadas_no_archivadas():
    cond, _ = servicio._filtro_tablero(True, False)
    assert cond.startswith(" AND NOT ") and "task_archivadas" in cond
    assert f"{archivo.DIAS_AUTO} days" in cond


def test_sin_completadas_como_antes():
    assert servicio._filtro_tablero(False, False)[0] == " AND NOT c.completed"


def test_archivadas_de_la_mas_reciente():
    cond, orden = servicio._filtro_tablero(False, True)
    assert cond.startswith(" AND (c.completed") and orden.startswith(
        "c.completed_at DESC"
    )


def test_archivar_solo_completadas_en_las_que_participa():
    ids = [uuid.uuid4(), uuid.uuid4()]
    db = _DB([{"card_id": ids[0]}])
    assert asyncio.run(archivo.archivar(db, "eva@example.org", ids)) == 1
    sql, args = db.sql[0]
    assert (
        "c.completed" in sql and "c.created_by = $1" in sql and "task_asignados" in sql
    )
    assert args == ("eva@example.org", ids, True)


def test_restaurar_lo_que_no_es_suyo_es_404():
    try:
        asyncio.run(archivo.restaurar(_DB([]), "intruso@example.org", uuid.uuid4()))
    except LookupError:
        return
    raise AssertionError("debió fallar")


def test_rutas_publicadas():
    from app.tareas import router

    rutas = {r.path for r in router.router.routes}
    assert "/archivar" in rutas and "/{tarea_id}/restaurar" in rutas
