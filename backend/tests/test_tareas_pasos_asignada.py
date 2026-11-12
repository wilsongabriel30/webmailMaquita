"""Subtareas de una tarea asignada: quien la recibe las ve y las marca; se avisa cuando se añaden."""

from __future__ import annotations

import asyncio
import uuid

import pytest
from fastapi import HTTPException

from app.tasks import acceso, pasos_asignada

ID = uuid.uuid4()
JEFA, PERSONA, AJENA = "jefa@example.org", "persona@example.org", "ajena@example.org"


class _DB:
    def __init__(self, asignada=True, en_listas=()):
        self.asignada, self.en_listas = asignada, en_listas

    async def fetchrow(self, sql, *a):
        return {
            "created_by": JEFA,
            "asignada": self.asignada,
            "title": "Plan anual",
            "asignados": [PERSONA],
        }

    async def fetchval(self, sql, *a):
        return ID


class _Redis:
    def __init__(self):
        self.claves = set()

    async def set(self, clave, valor, nx=False, ex=None):
        if clave in self.claves:
            return None
        self.claves.add(clave)
        return True


@pytest.fixture(autouse=True)
def _sin_listas(monkeypatch):
    async def puede(db, card_id, user):
        return user in db.en_listas

    monkeypatch.setattr(acceso, "puede_ver_tarea", puede)


def _papel(db, user):
    return asyncio.run(pasos_asignada.papel(db, ID, user))


def test_quien_recibe_la_tarea_participa_aunque_no_este_en_sus_listas():
    assert _papel(_DB(), PERSONA) == "asignado"


def test_quien_la_asigno_es_duena():
    assert _papel(_DB(), JEFA) == "dueno"


def test_una_persona_ajena_no_participa():
    assert _papel(_DB(), AJENA) == ""


def test_en_una_tarea_de_lista_sin_asignar_solo_cuenta_la_lista():
    assert _papel(_DB(asignada=False), PERSONA) == ""
    assert _papel(_DB(asignada=False, en_listas=(PERSONA,)), PERSONA) == "dueno"


@pytest.mark.parametrize("accion", ["ver", "crear", "marcar"])
def test_la_persona_asignada_ve_anade_y_marca(accion):
    assert asyncio.run(pasos_asignada.exigir(_DB(), ID, PERSONA, accion)) == "asignado"


@pytest.mark.parametrize("accion", ["editar", "borrar"])
def test_la_persona_asignada_no_renombra_ni_borra(accion):
    with pytest.raises(HTTPException) as e:
        asyncio.run(pasos_asignada.exigir(_DB(), ID, PERSONA, accion))
    assert e.value.status_code == 403


def test_la_ajena_recibe_403_al_ver():
    with pytest.raises(HTTPException) as e:
        asyncio.run(pasos_asignada.exigir(_DB(), ID, AJENA, "ver"))
    assert e.value.status_code == 403


def test_se_avisa_a_la_persona_asignada_una_vez_por_tanda(monkeypatch):
    from app.tareas import avisos

    enviados = []

    async def emitir(
        correos,
        titulo,
        texto,
        url,
        en_nombre_de,
        extra=None,
        db=None,
        card_id=None,
        **k,
    ):
        enviados.append((list(correos), titulo, texto, extra))
        return len(correos)

    monkeypatch.setattr(avisos, "emitir", emitir)
    monkeypatch.setattr(avisos, "nombre", lambda c: "La jefa")
    redis = _Redis()
    for _ in range(4):  # cuatro subtareas seguidas
        asyncio.run(pasos_asignada.avisar_subtareas(_DB(), redis, ID, JEFA))
    assert len(enviados) == 1
    correos, titulo, texto, extra = enviados[0]
    assert (
        correos == [PERSONA] and "añadió subtareas" in titulo and texto == "Plan anual"
    )
    assert extra["accion"] == "subtareas"


def test_si_anade_la_persona_asignada_se_avisa_a_quien_asigno(monkeypatch):
    from app.tareas import avisos

    enviados = []

    async def emitir(correos, *a, **k):
        enviados.append(list(correos))
        return 1

    monkeypatch.setattr(avisos, "emitir", emitir)
    asyncio.run(pasos_asignada.avisar_subtareas(_DB(), _Redis(), ID, PERSONA))
    assert enviados == [[JEFA]]


def test_en_tarea_sin_asignar_no_se_avisa(monkeypatch):
    from app.tareas import avisos

    async def emitir(*a, **k):
        raise AssertionError("no debía avisar")

    monkeypatch.setattr(avisos, "emitir", emitir)
    assert (
        asyncio.run(
            pasos_asignada.avisar_subtareas(_DB(asignada=False), _Redis(), ID, JEFA)
        )
        == 0
    )


def test_un_fallo_del_aviso_no_rompe_la_operacion(monkeypatch):
    from app.tareas import avisos

    async def emitir(*a, **k):
        raise RuntimeError("sin servicio de avisos")

    monkeypatch.setattr(avisos, "emitir", emitir)
    assert asyncio.run(pasos_asignada.avisar_subtareas(_DB(), _Redis(), ID, JEFA)) == 0
