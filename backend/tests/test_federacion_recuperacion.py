"""Recuperación entre servidores: protocolo, comprobaciones del correo y las dos puntas.

Sin red, sin BD y sin doveadm: todo lo externo se sustituye con dobles.
"""

import email
from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest

from app.federacion import recuperacion_cliente as cliente
from app.federacion import recuperacion_mensaje as mensaje
from app.federacion import recuperacion_protocolo as protocolo
from app.federacion import recuperacion_servidor as servidor
from app.federacion import red
from app.mail.routers import recall


class _Redis:
    def __init__(self):
        self.datos: dict[str, str] = {}
        self.publicadas = []

    async def setex(self, clave, _ttl, valor):
        self.datos[clave] = valor

    async def get(self, clave):
        return self.datos.get(clave)

    async def delete(self, *claves):
        for c in claves:
            self.datos.pop(c, None)

    async def smembers(self, _clave):
        return set()

    async def publish(self, canal, datos):
        self.publicadas.append(canal)


class _Db:
    def __init__(self):
        self.inserciones = []

    async def fetch(self, _sql):
        return [{"domain": "destino.test"}, {"domain": "ALL"}]

    async def execute(self, *args):
        self.inserciones.append(args)


def _solicitud(**cambios):
    datos = {
        "token": "t" * 43,
        "message_id": "<abc@origen.test>",
        "remitente": "ana@origen.test",
        "destinatario": "luis@destino.test",
    }
    datos.update(cambios)
    return protocolo.Solicitud(**datos)


def _correo(
    from_="Ana <ana@origen.test>",
    ar="mail.destino.test; dkim=pass header.d=origen.test header.s=mail",
):
    texto = f"From: {from_}\nMessage-ID: <abc@origen.test>\n"
    if ar:
        texto = f"Authentication-Results: {ar}\n" + texto
    return email.message_from_string(texto + "\n")


# ----------------------------------------------------------------------------- protocolo
async def test_solicitud_se_confirma_una_sola_vez():
    redis, s = _Redis(), _solicitud()
    await protocolo.guardar(redis, s)
    assert await protocolo.confirmar(redis, s) is True
    assert await protocolo.confirmar(redis, s) is False


async def test_solicitud_alterada_no_se_confirma():
    redis, s = _Redis(), _solicitud()
    await protocolo.guardar(redis, s)
    assert (
        await protocolo.confirmar(redis, _solicitud(destinatario="otro@destino.test"))
        is False
    )
    assert await protocolo.confirmar(redis, _solicitud(token="x" * 43)) is False


# ----------------------------------------------------------------------------- correo autenticado
def test_autenticado_por_dkim_o_dmarc_de_este_servidor():
    ids = {"mail.destino.test"}
    assert mensaje.autenticado(_correo(), "origen.test", ids)
    assert mensaje.autenticado(
        _correo(
            ar="mail.destino.test; dkim=fail; dmarc=pass (policy=none) header.from=origen.test"
        ),
        "origen.test",
        ids,
    )
    # Firmado por otro dominio: no vale.
    assert not mensaje.autenticado(
        _correo(ar="mail.destino.test; dkim=pass header.d=intruso.test"),
        "origen.test",
        ids,
    )
    # Cabecera de otro servidor (la pudo poner quien envía): no vale.
    assert not mensaje.autenticado(
        _correo(ar="mail.intruso.test; dkim=pass header.d=origen.test"),
        "origen.test",
        ids,
    )
    assert not mensaje.autenticado(_correo(ar=""), "origen.test", ids)
    assert not mensaje.autenticado(
        _correo(ar="mail.destino.test; dkim=fail"), "origen.test", ids
    )


def test_solo_cuenta_la_cabecera_mas_alta():
    msg = email.message_from_string(
        "Authentication-Results: mail.destino.test; dkim=fail\n"
        "Authentication-Results: mail.destino.test; dkim=pass header.d=origen.test\n"
        "From: ana@origen.test\n\n"
    )
    assert not mensaje.autenticado(msg, "origen.test", {"mail.destino.test"})


# ----------------------------------------------------------------------------- red
def test_solo_direcciones_publicas():
    assert red.ip_publica("8.8.8.8")
    for privada in (
        "10.0.0.5",
        "127.0.0.1",
        "192.168.1.1",
        "172.31.128.2",
        "169.254.1.1",
        "::1",
        "x",
    ):
        assert not red.ip_publica(privada)


async def test_host_interno_solo_si_esta_en_la_lista(monkeypatch):
    monkeypatch.setattr(red, "_ips", lambda host: ["172.31.128.2"])
    monkeypatch.setattr(red, "hosts_internos", lambda: set())
    assert await red.host_permitido("mail.hermano.test") is False
    monkeypatch.setattr(red, "hosts_internos", lambda: {"mail.hermano.test"})
    assert await red.host_permitido("mail.hermano.test") is True
    assert await red.host_permitido("no es un host") is False


# ----------------------------------------------------------------------------- servidor del destinatario
@pytest.fixture
def destino(monkeypatch):
    redis, db = _Redis(), _Db()
    expunges = []
    monkeypatch.setattr(mensaje, "cabeceras", lambda dest, mid: _correo())
    monkeypatch.setattr(
        mensaje, "identidades_del_servidor", lambda: {"mail.destino.test"}
    )
    monkeypatch.setattr(
        recall,
        "_doveadm_fetch_info",
        lambda dest, mid: {
            "folders": ["INBOX"],
            "was_read": True,
            "received": datetime.now(),
        },
    )
    monkeypatch.setattr(
        recall,
        "_doveadm_expunge",
        lambda dest, mid, c=None: expunges.append((dest, c)) or True,
    )

    async def _mx(dominio):
        return ["mail." + dominio]

    llamadas = []

    async def _llamar(host, metodo, ruta, cuerpo=None, tiempo_s=8.0):
        llamadas.append((host, ruta))
        return {"confirmado": True}

    monkeypatch.setattr(red, "servidores_de", _mx)
    monkeypatch.setattr(red, "llamar", _llamar)
    peticion = SimpleNamespace(
        app=SimpleNamespace(state=SimpleNamespace(redis=redis, db_pool=db))
    )
    return SimpleNamespace(
        peticion=peticion, db=db, expunges=expunges, llamadas=llamadas
    )


async def test_destino_retira_si_todo_cuadra(destino):
    r = await servidor.atender(destino.peticion, _solicitud(), "203.0.113.9")
    assert r == {"estado": "recalled", "leido": True}
    assert destino.expunges == [("luis@destino.test", ["INBOX"])]
    # La confirmación se pide al servidor del dominio del From.
    assert destino.llamadas == [("mail.origen.test", protocolo.RUTA_CONFIRMAR)]
    assert destino.db.inserciones


async def test_destino_no_retira_si_el_origen_no_confirma(destino, monkeypatch):
    async def _no(host, metodo, ruta, cuerpo=None, tiempo_s=8.0):
        return {"confirmado": False}

    monkeypatch.setattr(red, "llamar", _no)
    assert await servidor.atender(destino.peticion, _solicitud(), None) == servidor.NO
    assert destino.expunges == []


async def test_destino_no_retira_correo_no_autenticado(destino, monkeypatch):
    monkeypatch.setattr(
        mensaje,
        "cabeceras",
        lambda dest, mid: _correo(ar="mail.destino.test; dkim=fail"),
    )
    assert await servidor.atender(destino.peticion, _solicitud(), None) == servidor.NO
    assert destino.expunges == [] and destino.llamadas == []


async def test_destino_ignora_buzones_ajenos_y_dominios_propios(destino, monkeypatch):
    assert (
        await servidor.atender(
            destino.peticion, _solicitud(destinatario="x@otro.test"), None
        )
        == servidor.NO
    )
    # Un From de un dominio de este mismo servidor no entra por esta puerta.
    monkeypatch.setattr(
        mensaje, "cabeceras", lambda dest, mid: _correo(from_="jefe@destino.test")
    )
    assert await servidor.atender(destino.peticion, _solicitud(), None) == servidor.NO
    monkeypatch.setattr(mensaje, "cabeceras", lambda dest, mid: None)
    assert await servidor.atender(destino.peticion, _solicitud(), None) == servidor.NO
    assert destino.expunges == []


async def test_destino_respeta_su_plazo(destino, monkeypatch):
    monkeypatch.setattr(
        recall,
        "_doveadm_fetch_info",
        lambda dest, mid: {
            "folders": ["INBOX"],
            "received": datetime.now() - timedelta(hours=5),
        },
    )
    r = await servidor.atender(destino.peticion, _solicitud(), None)
    assert r["estado"] == "fuera_de_plazo"
    assert destino.expunges == []
    assert destino.db.inserciones  # el intento queda anotado


# ----------------------------------------------------------------------------- servidor del remitente
async def test_cliente_sin_servidor_compatible_devuelve_none(monkeypatch):
    async def _mx(dominio):
        return ["mail." + dominio]

    async def _llamar(host, metodo, ruta, cuerpo=None, tiempo_s=8.0):
        return None

    monkeypatch.setattr(red, "servidores_de", _mx)
    monkeypatch.setattr(red, "llamar", _llamar)
    redis = _Redis()
    assert (
        await cliente.recuperar_en_otro_servidor(
            redis, "a@origen.test", "b@gmail.test", "<x@y>"
        )
        is None
    )
    # Se recuerda que ese dominio no es compatible.
    assert redis.datos["fed:cap:gmail.test"] == ""


async def test_cliente_pide_y_no_deja_solicitudes_colgadas(monkeypatch):
    vistas = []

    async def _mx(dominio):
        return ["mail." + dominio]

    async def _llamar(host, metodo, ruta, cuerpo=None, tiempo_s=8.0):
        vistas.append((metodo, ruta))
        if metodo == "GET":
            return {"version": 1, "activo": True}
        return {"estado": "recalled", "leido": False}

    monkeypatch.setattr(red, "servidores_de", _mx)
    monkeypatch.setattr(red, "llamar", _llamar)
    redis = _Redis()
    r = await cliente.recuperar_en_otro_servidor(
        redis, "a@origen.test", "b@destino.test", "<x@y>"
    )
    assert r == {"estado": "recalled", "leido": False, "servidor": "mail.destino.test"}
    assert vistas == [("GET", protocolo.RUTA_BASE), ("POST", protocolo.RUTA_SOLICITAR)]
    assert not [k for k in redis.datos if k.startswith("fed:recall:")]
