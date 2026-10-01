"""Cuenta activa (multicuenta estilo Outlook): alcance de rutas, permisos y revocación."""

from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.mail.services import cuenta_activa as ca
from app.mail.services.cuentas_delegadas import cuenta_de_la_peticion


class _Db:
    def __init__(self, filas):
        self.filas = filas  # {(cuenta, persona): completo}
        self.auditoria = []

    async def fetchrow(self, _sql, cuenta, persona):
        clave = (cuenta.lower(), persona.lower())
        if clave in self.filas:
            return {"completo": self.filas[clave]}
        return None

    async def execute(self, _sql, *args):
        self.auditoria.append(args)


class _Redis:
    def __init__(self):
        self.claves = set()

    async def set(self, clave, _valor, ex=None, nx=False):
        if nx and clave in self.claves:
            return None
        self.claves.add(clave)
        return True


def _peticion(ruta, cuenta=None, metodo="GET", kind="normal", db=None):
    headers = {ca.CABECERA: cuenta} if cuenta else {}
    app = SimpleNamespace(state=SimpleNamespace(db_pool=db or _Db({}), redis=_Redis()))
    return SimpleNamespace(
        headers=headers,
        url=SimpleNamespace(path=ruta),
        method=metodo,
        state=SimpleNamespace(sid="s1", session_kind=kind),
        app=app,
        client=SimpleNamespace(host="10.0.0.5"),
        path_params={},
        cookies={},
    )


PERSONA = "ana@uno.example"
VENTAS = "ventas@dos.example"


def test_alcance_de_rutas():
    assert ca.aplica("/api/mail/messages/INBOX")
    assert ca.aplica("/api/firmas")
    assert ca.aplica("/api/sieve/scripts")
    assert not ca.aplica("/api/mail/cuentas")
    assert not ca.aplica("/api/mail/delegation/grant")
    assert not ca.aplica("/api/calendar/events")
    assert not ca.aplica("/api/contacts")


async def test_sin_cabecera_es_la_persona():
    r = _peticion("/api/mail/folders")
    assert await ca.resolver(r, PERSONA) == PERSONA
    assert r.state.persona == PERSONA


async def test_fuera_de_correo_se_ignora_la_cabecera():
    r = _peticion("/api/calendar/events", VENTAS)
    assert await ca.resolver(r, PERSONA) == PERSONA


async def test_cuenta_asignada_reemplaza_a_la_persona_y_se_audita_una_vez():
    db = _Db({(VENTAS, PERSONA): True})
    r = _peticion("/api/mail/messages/INBOX", VENTAS, db=db)
    assert await ca.resolver(r, PERSONA) == VENTAS
    assert r.state.cuenta_activa == VENTAS and r.state.persona == PERSONA
    await ca.resolver(r, PERSONA)
    assert [a[1] for a in db.auditoria] == ["cuenta_activa_acceso"]


async def test_credencial_imap_es_la_de_la_cuenta_activa():
    db = _Db({(VENTAS, PERSONA): True})
    r = _peticion("/api/mail/messages/INBOX", VENTAS, db=db)
    usuario = await ca.resolver(r, PERSONA)
    assert await cuenta_de_la_peticion(r, usuario) == VENTAS
    # La persona, en la misma petición, no se confunde con la cuenta activa.
    r2 = _peticion("/api/mail/messages/INBOX")
    await ca.resolver(r2, PERSONA)
    assert await cuenta_de_la_peticion(r2, PERSONA) is None


async def test_cuenta_no_asignada_o_revocada_se_rechaza():
    r = _peticion("/api/mail/messages/INBOX", VENTAS)
    with pytest.raises(HTTPException) as e:
        await ca.resolver(r, PERSONA)
    assert e.value.status_code == 403


async def test_solo_lectura():
    db = _Db({(VENTAS, PERSONA): False})
    assert await ca.resolver(_peticion("/api/mail/messages/INBOX", VENTAS, db=db), PERSONA) == VENTAS
    assert await ca.resolver(_peticion("/api/mail/search", VENTAS, "POST", db=db), PERSONA) == VENTAS
    with pytest.raises(HTTPException) as e:
        await ca.resolver(_peticion("/api/mail/send", VENTAS, "POST", db=db), PERSONA)
    assert e.value.status_code == 403


async def test_envio_se_audita_siempre():
    db = _Db({(VENTAS, PERSONA): True})
    await ca.resolver(_peticion("/api/mail/send", VENTAS, "POST", db=db), PERSONA)
    assert "cuenta_activa_envio" in [a[1] for a in db.auditoria]


@pytest.mark.parametrize("kind", ["impersonation", "delegada"])
async def test_sesiones_especiales_no_cambian_de_cuenta(kind):
    db = _Db({(VENTAS, PERSONA): True})
    with pytest.raises(HTTPException):
        await ca.resolver(_peticion("/api/mail/folders", VENTAS, kind=kind, db=db), PERSONA)


def _con_cookie(r, valor):
    r.cookies = {ca.COOKIE: valor}
    return r


async def test_cookie_solo_para_consultas():
    db = _Db({(VENTAS, PERSONA): True})
    r = _con_cookie(_peticion("/api/mail/attachments-zip/INBOX/5", db=db), VENTAS)
    assert await ca.resolver(r, PERSONA) == VENTAS
    # Enviar con solo la cookie (sin cabecera) sale de la propia cuenta, nunca de la otra.
    r = _con_cookie(_peticion("/api/mail/send", metodo="POST", db=db), VENTAS)
    assert await ca.resolver(r, PERSONA) == PERSONA


async def test_cabecera_propia_manda_sobre_la_cookie():
    db = _Db({(VENTAS, PERSONA): True})
    r = _con_cookie(_peticion("/api/mail/folders", "propia", db=db), VENTAS)
    assert await ca.resolver(r, PERSONA) == PERSONA


def test_firmas_por_cuenta_y_resto_de_ajustes_de_la_persona():
    assert ca.aplica("/api/settings/signature")
    assert ca.aplica("/api/settings/signatures/3")
    assert not ca.aplica("/api/settings/preferences")
