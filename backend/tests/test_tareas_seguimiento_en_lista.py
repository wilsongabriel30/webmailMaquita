"""Completar desde su lista una tarea con seguimiento va por Seguimiento (fase 3 de la unificación, 05/11/2026)."""

from __future__ import annotations

import asyncio
import uuid

import pytest

from app.tasks import seguimiento_en_lista as sel

ID = uuid.uuid4()


class _Svc:
    def __init__(self, permitido=True):
        self.llamadas, self.permitido = [], permitido

    async def completar(self, db, redis, user, card_id):
        if not self.permitido:
            raise PermissionError("No participas en esta tarea")
        self.llamadas.append(("completar", user))

    async def cambiar_estado(self, db, redis, user, card_id, estado):
        self.llamadas.append((estado, user))


@pytest.fixture
def svc(monkeypatch):
    s = _Svc()
    monkeypatch.setattr(sel, "servicio_tareas", s)

    async def una(db, user, card_id):
        return {"id": card_id}

    monkeypatch.setattr(sel.vistas, "una", una)
    return s


def test_completar_pasa_por_seguimiento(svc):
    assert asyncio.run(sel.marcar(None, None, "eva@example.org", ID, True)) == {
        "id": ID
    }
    assert svc.llamadas == [("completar", "eva@example.org")]


def test_reabrir_la_deja_pendiente(svc):
    asyncio.run(sel.marcar(None, None, "eva@example.org", ID, False))
    assert svc.llamadas == [("pendiente", "eva@example.org")]


def test_quien_no_participa_no_la_completa(svc):
    svc.permitido = False
    with pytest.raises(sel.NoParticipa):
        asyncio.run(sel.marcar(None, None, "otro@example.org", ID, True))


def test_es_seguimiento():
    class _DB:
        def __init__(self, v):
            self.v = v

        async def fetchval(self, sql, *a):
            return self.v

    assert asyncio.run(sel.es_seguimiento(_DB(True), ID)) is True
    assert asyncio.run(sel.es_seguimiento(_DB(None), ID)) is False


def test_la_ruta_vieja_de_asignar_ya_no_existe():
    from app.tasks import router

    rutas = {
        (r.path, m) for r in router.router.routes for m in getattr(r, "methods", ())
    }
    assert not any(p.endswith("/asignados") and m == "PUT" for p, m in rutas)
