"""Borrar una lista o un tablero no se lleva las tareas con seguimiento (05/11/2026)."""

from __future__ import annotations

import asyncio
import uuid

from app.tareas import servicio
from app.tasks import rescate_seguimiento as rs

L1, L2, DESTINO = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()


class _DB:
    def __init__(self, filas):
        self.filas, self.movidas = filas, []

    async def fetch(self, sql, *a):
        assert "asignada" in sql
        return self.filas

    async def execute(self, sql, *a):
        self.movidas.append(a)


def test_pasan_a_la_lista_tareas_de_quien_asigno(monkeypatch):
    async def destino(db, user):
        return {"ana@example.org": DESTINO, "luis@example.org": L1}[user]

    monkeypatch.setattr(rs.task_service, "_get_default_list_id", destino)
    db = _DB(
        [
            {"id": "t1", "created_by": "ana@example.org"},
            {"id": "t2", "created_by": "luis@example.org"},  # borra su propio tablero
        ]
    )
    assert asyncio.run(rs.rescatar(db, [L1, L2])) == 1
    assert db.movidas == [("t1", DESTINO)]


def test_creada_por_solo_si_es_otra_persona():
    base = {"created_by": "ana@example.org"}
    assert servicio._creada_por({**base, "creada_por": "luis@example.org"}) == (
        "luis@example.org"
    )
    assert servicio._creada_por({**base, "creada_por": "ana@example.org"}) is None
    assert servicio._creada_por(base) is None
