"""Las invitaciones a reuniones leen la credencial de la sesión (`imap_pass:{u}:{sid}`).

Antecedente (21/10/2026): `_send_invitations` seguía leyendo `imap_pass:{u}`, que ya no
existe desde que la credencial va por sesión (12/10/2026). Como el envío es best-effort,
las invitaciones dejaron de salir sin ningún aviso.
"""

import asyncio
from types import SimpleNamespace

from app.core.session import encrypt_password
from app.meetings import router as reuniones


class _Redis:
    def __init__(self, datos):
        self.datos, self.pedidas = dict(datos), []

    async def get(self, clave):
        self.pedidas.append(clave)
        return self.datos.get(clave)

    async def delete(self, *claves):
        for c in claves:
            self.datos.pop(c, None)


class _SMTP:
    enviados = []

    def __init__(self, host, puerto):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def starttls(self):
        pass

    def login(self, usuario, clave):
        _SMTP.enviados.append(("login", usuario, clave))

    def sendmail(self, de, para, mensaje):
        _SMTP.enviados.append(("sendmail", de, tuple(para)))


def _peticion(redis, sid="SID1"):
    return SimpleNamespace(
        state=SimpleNamespace(sid=sid),
        path_params={},
        query_params={},
        app=SimpleNamespace(state=SimpleNamespace(redis=redis)),
    )


def _enviar(monkeypatch, redis, sid="SID1"):
    import smtplib

    from app.mail.services import cuentas_delegadas

    async def _sin_delegada(_peticion, _usuario):
        return None

    monkeypatch.setattr(cuentas_delegadas, "cuenta_de_la_peticion", _sin_delegada)
    monkeypatch.setattr(smtplib, "SMTP", _SMTP)
    _SMTP.enviados = []
    asyncio.run(
        reuniones._send_invitations(
            _peticion(redis, sid),
            "ana@example.com",
            "Comité",
            "https://meet.example.com/abc",
            None,
            ["luis@example.com"],
        )
    )
    return _SMTP.enviados


def test_invitacion_usa_la_credencial_de_la_sesion(monkeypatch):
    redis = _Redis(
        {"imap_pass:ana@example.com:SID1": encrypt_password("clave-de-prueba")}
    )
    enviados = _enviar(monkeypatch, redis)
    assert ("login", "ana@example.com", "clave-de-prueba") in enviados
    assert ("sendmail", "ana@example.com", ("luis@example.com",)) in enviados
    assert "imap_pass:ana@example.com" not in redis.pedidas


def test_sin_sesion_no_envia_ni_falla(monkeypatch):
    redis = _Redis({"imap_pass:ana@example.com": encrypt_password("clave-vieja")})
    assert _enviar(monkeypatch, redis) == []


def test_el_router_no_lee_la_clave_antigua():
    import inspect

    fuente = inspect.getsource(reuniones)
    assert 'f"imap_pass:{creator}"' not in fuente
