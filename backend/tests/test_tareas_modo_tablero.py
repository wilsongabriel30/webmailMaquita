"""Modo Tablero de Tareas (09/11/2026): mover una tarea de lista a Pendiente, En curso o Completada."""

from __future__ import annotations

import asyncio
import uuid

import pytest

from app.tasks import estado_tarea as et

ID = uuid.uuid4()
EVA = "eva@example.org"


class _DB:
    def __init__(self, completada=False):
        self.completada, self.ejecutadas = completada, []

    async def fetchval(self, sql, *a):
        return self.completada

    async def execute(self, sql, *a):
        self.ejecutadas.append(a)


class _Svc:
    def __init__(self, permitido=True):
        self.llamadas, self.permitido = [], permitido

    async def cambiar_estado(self, db, redis, user, card_id, estado):
        if not self.permitido:
            raise PermissionError("No participas en esta tarea")
        self.llamadas.append(estado)


@pytest.fixture
def entorno(monkeypatch):
    estado = {"visible": True, "seguimiento": False, "svc": _Svc()}

    async def puede_ver(db, card_id, user):
        return estado["visible"]

    async def es_seguimiento(db, card_id):
        return estado["seguimiento"]

    async def una(db, user, card_id):
        return {"id": card_id}

    monkeypatch.setattr(et.acceso, "puede_ver_tarea", puede_ver)
    monkeypatch.setattr(et.seguimiento_en_lista, "es_seguimiento", es_seguimiento)
    monkeypatch.setattr(et.vistas, "una", una)
    monkeypatch.setattr(et, "servicio_tareas", estado["svc"])
    return estado


def _cambiar(db, estado, alternadas):
    async def alternar():
        alternadas.append(1)

    return asyncio.run(et.cambiar(db, None, EVA, ID, estado, alternar))


def test_personal_en_curso_guarda_el_estado_sin_completar(entorno):
    db, alt = _DB(completada=False), []
    assert _cambiar(db, "en_curso", alt) == {"id": ID}
    assert alt == [] and db.ejecutadas == [(ID, "en_curso")]


def test_personal_completada_usa_el_circulo_de_la_lista(entorno):
    db, alt = _DB(completada=False), []
    _cambiar(db, "completada", alt)
    assert alt == [1] and db.ejecutadas == []


def test_personal_completada_desde_completada_no_hace_nada(entorno):
    db, alt = _DB(completada=True), []
    _cambiar(db, "completada", alt)
    assert alt == [] and db.ejecutadas == []


def test_reabrir_a_en_curso_reabre_y_guarda(entorno):
    db, alt = _DB(completada=True), []
    _cambiar(db, "en_curso", alt)
    assert alt == [1] and db.ejecutadas == [(ID, "en_curso")]


def test_con_seguimiento_va_por_seguimiento(entorno):
    entorno["seguimiento"] = True
    db, alt = _DB(), []
    _cambiar(db, "en_curso", alt)
    assert entorno["svc"].llamadas == ["en_curso"] and alt == [] and db.ejecutadas == []


def test_con_seguimiento_sin_participar_da_no_participa(entorno):
    entorno["seguimiento"], entorno["svc"].permitido = True, False
    with pytest.raises(et.NoParticipa):
        _cambiar(_DB(), "completada", [])


def test_tarea_ajena_no_se_encuentra(entorno):
    entorno["visible"] = False
    with pytest.raises(LookupError):
        _cambiar(_DB(), "en_curso", [])


def test_estado_no_valido(entorno):
    with pytest.raises(ValueError):
        _cambiar(_DB(), "vencida", [])


def test_la_ruta_existe_y_la_tarjeta_lleva_estado():
    from app.tasks import router
    from app.tasks.schemas import CardOut

    rutas = {
        (r.path, m) for r in router.router.routes for m in getattr(r, "methods", ())
    }
    assert ("/tasks/{card_id}/estado", "PATCH") in rutas
    assert CardOut.model_fields["estado"].default == "pendiente"
