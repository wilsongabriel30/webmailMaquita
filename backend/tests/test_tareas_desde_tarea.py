"""«Asignar tarea a:» de una tarea de lista la pasa a Seguimiento (fase 2 de la unificación, 05/11/2026)."""

from __future__ import annotations

import asyncio
import uuid

import pytest

from app.tareas import desde_tarea
from app.tareas.esquemas import TareaAsignar
from app.tasks import acceso, compartir

ID = uuid.uuid4()


class _DB:
    def __init__(self, tarea):
        self.tarea, self.sql = tarea, []

    async def fetchrow(self, sql, *a):
        return self.tarea

    async def fetchval(self, sql, *a):
        return 0

    async def execute(self, sql, *a):
        self.sql.append((sql, a))


class _Svc:
    def __init__(self):
        self.anuncios = []

    async def obtener(self, db, card_id, user):
        return {"id": card_id}

    async def anunciar(self, db, redis, user, row, asignados):
        self.anuncios.append((user, asignados))


@pytest.fixture(autouse=True)
def _organizacion(monkeypatch):
    monkeypatch.setattr(compartir, "de_la_casa", lambda e: e.endswith("@example.org"))

    async def _ve(db, card_id, user):
        return user != "intruso@example.org"

    monkeypatch.setattr(acceso, "puede_ver_tarea", _ve)


def _convertir(tarea, d, user="ana@example.org", svc=None):
    db = _DB(tarea)
    svc = svc or _Svc()
    asyncio.run(desde_tarea.convertir(svc, db, None, user, ID, d))
    return db, svc


LISTA = {"id": ID, "asignada": False, "list_type": "custom"}


def test_la_misma_tarea_pasa_a_seguimiento_y_se_avisa():
    d = TareaAsignar(
        titulo="Llamar",
        asignados=["Eva@example.org", "eva@example.org"],
        subtareas=["Proforma"],
    )
    db, svc = _convertir(LISTA, d)
    update = next(a for s, a in db.sql if s.lstrip().startswith("UPDATE task_cards"))
    assert "asignada = TRUE" in next(
        s for s, _ in db.sql if s.lstrip().startswith("UPDATE")
    )
    assert (
        update[1] == "pendiente" and update[-1] == "ana@example.org"
    )  # quien asigna le da seguimiento
    assert not any(
        "INSERT INTO task_cards" in s for s, _ in db.sql
    )  # no se copia: es la misma
    assert any("INSERT INTO task_steps" in s for s, _ in db.sql)
    assert svc.anuncios == [("ana@example.org", ["eva@example.org"])]


def test_en_cadena_no_avisa_todavia():
    d = TareaAsignar(
        titulo="Luego",
        asignados=["eva@example.org"],
        en_espera=True,
        activa_tarea_id=uuid.uuid4(),
    )
    db, svc = _convertir(LISTA, d)
    assert next(a for s, a in db.sql if s.lstrip().startswith("UPDATE"))[1] == "espera"
    assert svc.anuncios == []


@pytest.mark.parametrize(
    "tarea, d, user, error",
    [
        (
            None,
            TareaAsignar(titulo="x", asignados=["eva@example.org"]),
            "ana@example.org",
            LookupError,
        ),
        (
            LISTA,
            TareaAsignar(titulo="x", asignados=["eva@example.org"]),
            "intruso@example.org",
            LookupError,
        ),
        (
            {**LISTA, "asignada": True},
            TareaAsignar(titulo="x", asignados=["eva@example.org"]),
            "ana@example.org",
            ValueError,
        ),
        (
            {**LISTA, "list_type": "flagged"},
            TareaAsignar(titulo="x", asignados=["eva@example.org"]),
            "ana@example.org",
            ValueError,
        ),
        (LISTA, TareaAsignar(titulo="x"), "ana@example.org", ValueError),
        (
            LISTA,
            TareaAsignar(titulo="x", asignados=["x@gmail.com"]),
            "ana@example.org",
            ValueError,
        ),
        (
            LISTA,
            TareaAsignar(
                titulo="x", asignados=["eva@example.org"], recurrencia="cada-rato"
            ),
            "ana@example.org",
            ValueError,
        ),
    ],
)
def test_lo_que_no_se_convierte(tarea, d, user, error):
    with pytest.raises(error):
        _convertir(tarea, d, user)


def test_la_ruta_esta_publicada():
    from app.tareas import router

    assert "/desde-tarea/{card_id}" in [r.path for r in router.router.routes]
