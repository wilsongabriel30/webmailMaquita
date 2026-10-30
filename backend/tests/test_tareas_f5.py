"""Tareas al estilo To Do, F5 (31/10/2026): avisos de vencimiento, a quién le llega cada aviso y asignar a cualquiera.

- El recordatorio va a las personas asignadas; si no hay, a quien creó la tarea (si sigue en la lista) y, si no, a
  la propietaria. Las de Seguimiento (T-34) siguen yendo solo a la propietaria.
- «Vence hoy» sale desde las 08:00 de Guayaquil, una vez por tarea.
- Asignar acepta un mensaje opcional y solo personas de la organización fuera de la lista.
- La copia de una lista lleva « (copia)» sin pasarse del largo máximo.
"""

import asyncio
import uuid
from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from app.tasks import asignar, avisos_tiempo, duplicar, listas, tiempo_real


class _DB:
    def __init__(self, asignados=(), en_lista=False, filas=()):
        self.asignados, self.en_lista, self.filas = (
            list(asignados),
            en_lista,
            list(filas),
        )
        self.sql = []

    async def fetch(self, sql, *a):
        self.sql.append(sql)
        if "task_asignados" in sql:
            return [{"email": e, "user_email": e} for e in self.asignados]
        return self.filas

    async def fetchval(self, sql, *a):
        return 1 if self.en_lista else None


def _fila(**kw):
    base = {
        "id": uuid.uuid4(),
        "list_id": uuid.uuid4(),
        "created_by": "caro@x.org",
        "asignada": False,
        "owner": "ana@x.org",
        "title": "Informe",
    }
    base.update(kw)
    return base


def _correr(coro):
    return asyncio.run(coro)


def test_recordatorio_a_las_personas_asignadas():
    db = _DB(asignados=["beto@x.org", "dani@x.org"])
    assert _correr(avisos_tiempo.destinatarios(db, _fila())) == [
        "beto@x.org",
        "dani@x.org",
    ]


def test_sin_asignar_le_llega_a_quien_la_creo():
    assert _correr(avisos_tiempo.destinatarios(_DB(en_lista=True), _fila())) == [
        "caro@x.org"
    ]


def test_creadora_fuera_de_la_lista_le_llega_a_la_propietaria():
    assert _correr(avisos_tiempo.destinatarios(_DB(), _fila())) == ["ana@x.org"]


def test_seguimiento_sigue_yendo_a_la_propietaria():
    db = _DB(asignados=["beto@x.org"])
    assert _correr(avisos_tiempo.destinatarios(db, _fila(asignada=True))) == [
        "ana@x.org"
    ]
    assert db.sql == []


class _Redis:
    def __init__(self):
        self.enviados = []

    async def publish(self, canal, msg):
        self.enviados.append((canal, msg))


def test_vence_hoy_no_sale_antes_de_las_ocho():
    db, redis = _DB(filas=[_fila()]), _Redis()
    temprano = datetime(2026, 11, 3, 12, 59, tzinfo=timezone.utc)  # 07:59 en Guayaquil
    assert _correr(avisos_tiempo.avisar_vencimientos(db, redis, temprano)) == 0
    assert db.sql == [] and redis.enviados == []


def test_vence_hoy_avisa_desde_las_ocho():
    db, redis = _DB(filas=[_fila()], en_lista=True), _Redis()
    ocho = datetime(2026, 11, 3, 13, 0, tzinfo=timezone.utc)
    assert _correr(avisos_tiempo.avisar_vencimientos(db, redis, ocho)) == 1
    assert [c for c, _ in redis.enviados] == ["ws:user:caro@x.org"]
    assert "Vence hoy: Informe" in redis.enviados[0][1]


def test_asignacion_con_mensaje():
    a = asignar.Asignacion(emails=["Ana@x.org"], mensaje="Antes del viernes")
    assert a.emails == ["ana@x.org"] and a.mensaje == "Antes del viernes"
    assert asignar.Asignacion(emails=[]).mensaje == ""
    with pytest.raises(ValidationError):
        asignar.Asignacion(emails=[], mensaje="x" * 2001)


def test_nombre_de_la_copia():
    assert duplicar.nombre_copia("Compras") == "Compras (copia)"
    largo = duplicar.nombre_copia("a" * listas.MAX_NOMBRE)
    assert len(largo) == listas.MAX_NOMBRE and largo.endswith(" (copia)")


class _App:
    def __init__(self, db, redis):
        self.state = type("E", (), {})()
        self.state.db_pool, self.state.redis = db, redis


class _Req:
    def __init__(self, parametros, db, redis):
        self.method = "PATCH"
        self.path_params = parametros
        self.app = _App(db, redis)


class _DBLista(_DB):
    async def fetchval(self, sql, *a):
        return uuid.uuid4()

    async def fetch(self, sql, *a):
        if "task_asignados" in sql:
            return [{"user_email": "eva@otra.x.org"}]
        return [{"user_email": "ana@x.org"}]


def test_tiempo_real_avisa_a_quien_tiene_la_tarea_asignada():
    db, redis = _DBLista(), _Redis()

    async def go():
        gen = tiempo_real.avisar_cambios(
            _Req({"card_id": str(uuid.uuid4())}, db, redis), "ana@x.org"
        )
        await gen.__anext__()
        with pytest.raises(StopAsyncIteration):
            await gen.__anext__()

    _correr(go())
    assert [c for c, _ in redis.enviados] == ["ws:user:eva@otra.x.org"]
