"""Reacciones entre servidores: solo de participantes del correo y confirmadas por su servidor."""

import email
from types import SimpleNamespace

import pytest

from app.federacion import reacciones_cliente as cliente
from app.federacion import reacciones_protocolo as protocolo
from app.federacion import reacciones_servidor as servidor
from app.federacion import recuperacion_mensaje as mensaje
from app.federacion import red
from app.mail.services import reacciones


class _Redis:
    def __init__(self):
        self.datos, self.publicadas = {}, []

    async def setex(self, k, _ttl, v):
        self.datos[k] = v

    async def get(self, k):
        return self.datos.get(k)

    async def delete(self, *ks):
        for k in ks:
            self.datos.pop(k, None)

    async def publish(self, canal, _datos):
        self.publicadas.append(canal)


class _Db:
    def __init__(self):
        self.reacciones = {}

    async def fetch(self, sql, *a):
        if "FROM domain" in sql:
            return [{"domain": "destino.test"}]
        return [{"username": d} for d in a[0] if d.endswith("@destino.test")]

    async def fetchval(self, _sql, *a):
        return self.reacciones.get((a[0], a[1]))

    async def execute(self, sql, *a):
        if sql.lstrip().startswith("DELETE"):
            self.reacciones.pop((a[0], a[1]), None)
        else:
            self.reacciones[(a[0], a[1])] = a[2]


def _aviso(**cambios):
    datos = {
        "token": "t" * 43,
        "message_id": "<m1@origen.test>",
        "usuario": "ana@origen.test",
        "nombre": "Ana Pérez",
        "emoji": "👍",
        "destinatarios": ["luis@destino.test"],
    }
    datos.update(cambios)
    return protocolo.Aviso(**datos)


def _correo():
    return email.message_from_string(
        "From: Luis <luis@destino.test>\nTo: ana@origen.test, eva@destino.test\nSubject: Hola\n\n"
    )


@pytest.fixture
def destino(monkeypatch):
    redis, db = _Redis(), _Db()
    monkeypatch.setattr(mensaje, "cabeceras", lambda cuenta, mid: _correo())

    async def _mx(dominio):
        return ["mail." + dominio]

    async def _llamar(host, metodo, ruta, cuerpo=None, tiempo_s=8.0):
        return {"confirmado": True}

    monkeypatch.setattr(red, "servidores_de", _mx)
    monkeypatch.setattr(red, "llamar", _llamar)
    peticion = SimpleNamespace(
        app=SimpleNamespace(state=SimpleNamespace(redis=redis, db_pool=db))
    )
    return SimpleNamespace(peticion=peticion, db=db, redis=redis)


async def test_reaccion_de_un_participante_confirmada_se_guarda_y_avisa(destino):
    assert await servidor.atender(destino.peticion, _aviso()) == {"estado": "recibida"}
    assert destino.db.reacciones == {("<m1@origen.test>", "ana@origen.test"): "👍"}
    assert sorted(destino.redis.publicadas) == [
        "ws:user:eva@destino.test",
        "ws:user:luis@destino.test",
    ]
    # Quitarla (emoji = None) la borra.
    assert await servidor.atender(destino.peticion, _aviso(emoji=None)) == {
        "estado": "recibida"
    }
    assert destino.db.reacciones == {}


async def test_no_se_acepta_de_quien_no_esta_en_el_correo(destino):
    r = await servidor.atender(destino.peticion, _aviso(usuario="intruso@origen.test"))
    assert r == servidor.NO and destino.db.reacciones == {}


async def test_no_se_acepta_sin_confirmacion_ni_emoji_raro_ni_dominio_propio(
    destino, monkeypatch
):
    assert await servidor.atender(destino.peticion, _aviso(emoji="💩")) == servidor.NO
    assert (
        await servidor.atender(destino.peticion, _aviso(usuario="eva@destino.test"))
        == servidor.NO
    )
    assert (
        await servidor.atender(destino.peticion, _aviso(destinatarios=["x@otro.test"]))
        == servidor.NO
    )

    async def _no(host, metodo, ruta, cuerpo=None, tiempo_s=8.0):
        return {"confirmado": False}

    monkeypatch.setattr(red, "llamar", _no)
    assert await servidor.atender(destino.peticion, _aviso()) == servidor.NO
    assert destino.db.reacciones == {}


async def test_aviso_se_confirma_una_sola_vez_y_no_si_cambia():
    redis, a = _Redis(), _aviso()
    await protocolo.guardar(redis, a)
    assert await protocolo.confirmar(redis, _aviso(emoji="🎉")) is False
    assert await protocolo.confirmar(redis, a) is True
    assert await protocolo.confirmar(redis, a) is False


async def test_cliente_agrupa_por_servidor_y_no_deja_avisos_colgados(monkeypatch):
    enviados = []

    async def _mx(dominio):
        return ["mail." + dominio] if dominio != "gmail.test" else ["mx.gmail.test"]

    async def _llamar(host, metodo, ruta, cuerpo=None, tiempo_s=8.0):
        if metodo == "GET":
            return (
                {"version": 1, "activo": True} if host == "mail.destino.test" else None
            )
        enviados.append((host, cuerpo["destinatarios"], cuerpo["emoji"]))
        return {"estado": "recibida"}

    monkeypatch.setattr(red, "servidores_de", _mx)
    monkeypatch.setattr(red, "llamar", _llamar)
    redis = _Redis()
    n = await cliente.avisar_otros_servidores(
        redis,
        "<m1>",
        "ana@origen.test",
        "Ana",
        "👍",
        {"luis@destino.test", "eva@destino.test", "x@gmail.test"},
    )
    assert n == 1
    assert enviados == [
        ("mail.destino.test", ["eva@destino.test", "luis@destino.test"], "👍")
    ]
    assert not [k for k in redis.datos if k.startswith("fed:reac:")]


async def test_fijar_pone_cambia_y_quita():
    db = _Db()
    assert await reacciones.fijar(db, "<m>", "a@x.test", "👍", "A") == "puesta"
    assert await reacciones.fijar(db, "<m>", "a@x.test", "🎉", "A") == "cambiada"
    assert await reacciones.fijar(db, "<m>", "a@x.test", None, "A") == "quitada"
    assert db.reacciones == {}
