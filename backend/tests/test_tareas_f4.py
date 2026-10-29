"""Tareas al estilo To Do, F4 (30/10/2026): compartir listas, asignar y tiempo real.

- Solo se comparte con correos válidos de la organización.
- La lista de asignados se limpia (minúsculas, sin repetidos ni vacíos).
- La dependencia de tiempo real no consulta nada en las lecturas y, en un cambio, avisa solo a las demás personas.
"""

import asyncio
import uuid

import pytest
from pydantic import ValidationError

from app.tasks import asignar, compartir, tiempo_real


def test_correo_valido_y_normalizado():
    assert (
        compartir.NuevoMiembro(email="  Ana.Perez@Example.ORG ").email
        == "ana.perez@example.org"
    )
    for malo in ("ana", "ana@", "@example.org", "ana perez@example.org"):
        with pytest.raises(ValidationError):
            compartir.NuevoMiembro(email=malo)


def test_solo_cuentas_de_la_casa(monkeypatch):
    monkeypatch.setattr(
        compartir.organizacion, "dominios_propios", lambda: frozenset({"example.org"})
    )
    assert compartir.de_la_casa("ana@example.org")
    assert not compartir.de_la_casa("ana@gmail.com")
    assert not compartir.de_la_casa("ana@example.org.evil.com")


def test_asignados_limpios():
    a = asignar.Asignacion(emails=[" Ana@x.org", "ana@x.org", "", "beto@x.org"])
    assert a.emails == ["ana@x.org", "beto@x.org"]
    with pytest.raises(ValidationError):
        asignar.Asignacion(emails=[f"p{i}@x.org" for i in range(51)])


class _Estado:
    pass


class _App:
    def __init__(self, db, redis):
        self.state = _Estado()
        self.state.db_pool = db
        self.state.redis = redis


class _Req:
    def __init__(self, metodo, parametros, db, redis):
        self.method = metodo
        self.path_params = parametros
        self.app = _App(db, redis)


class _DB:
    def __init__(self, lista, personas):
        self.lista, self.personas, self.consultas = lista, personas, 0

    async def fetchval(self, sql, *a):
        self.consultas += 1
        return self.lista

    async def fetch(self, sql, *a):
        self.consultas += 1
        return [{"user_email": p} for p in self.personas]


class _Redis:
    def __init__(self):
        self.enviados = []

    async def publish(self, canal, msg):
        self.enviados.append(canal)


def _correr(req, user="ana@x.org"):
    async def go():
        gen = tiempo_real.avisar_cambios(req, user)
        await gen.__anext__()
        with pytest.raises(StopAsyncIteration):
            await gen.__anext__()

    asyncio.run(go())


def test_lectura_no_consulta_ni_avisa():
    db, redis = _DB(uuid.uuid4(), ["ana@x.org", "beto@x.org"]), _Redis()
    _correr(_Req("GET", {"card_id": str(uuid.uuid4())}, db, redis))
    assert db.consultas == 0 and redis.enviados == []


def test_cambio_avisa_a_las_demas_personas():
    db, redis = _DB(uuid.uuid4(), ["ana@x.org", "beto@x.org", "caro@x.org"]), _Redis()
    _correr(_Req("PATCH", {"card_id": str(uuid.uuid4())}, db, redis))
    assert redis.enviados == ["ws:user:beto@x.org", "ws:user:caro@x.org"]


def test_lista_sin_compartir_no_avisa():
    db, redis = _DB(uuid.uuid4(), ["ana@x.org"]), _Redis()
    _correr(_Req("DELETE", {"step_id": str(uuid.uuid4())}, db, redis))
    assert redis.enviados == []
