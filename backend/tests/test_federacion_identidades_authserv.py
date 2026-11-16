"""Nombres de `Authentication-Results` que el servidor reconoce como propios (Andes, 16/11/2026)."""

from __future__ import annotations

import subprocess
from types import SimpleNamespace

from app.federacion import recuperacion_mensaje as m


def _ajustes(monkeypatch, authserv=""):
    monkeypatch.setattr(
        m,
        "get_settings",
        lambda: SimpleNamespace(
            recall_federado_authserv=authserv, public_base_url="https://mail.example.org"
        ),
    )
    monkeypatch.setattr(m.socket, "getfqdn", lambda: "maquina.interna.example.net")
    m.nombre_de_postfix.cache_clear()


def _postconf(monkeypatch, salida="", codigo=0, falla=False):
    def correr(orden, **_):
        assert orden == ["postconf", "-h", "myhostname"]
        if falla:
            raise FileNotFoundError("postconf")
        return subprocess.CompletedProcess(orden, codigo, stdout=salida, stderr="")

    monkeypatch.setattr(m.subprocess, "run", correr)


def test_sin_configurar_incluye_el_myhostname_de_postfix(monkeypatch):
    _ajustes(monkeypatch)
    _postconf(monkeypatch, "MAIL2.example.org\n")
    assert m.identidades_del_servidor() == {
        "mail.example.org",
        "maquina.interna.example.net",
        "mail2.example.org",
    }


def test_sin_postfix_o_con_salida_rara_sigue_funcionando(monkeypatch):
    _ajustes(monkeypatch)
    _postconf(monkeypatch, falla=True)
    assert m.identidades_del_servidor() == {"mail.example.org", "maquina.interna.example.net"}
    for salida, codigo in (("", 1), ("no es; un nombre\n", 0)):
        _ajustes(monkeypatch)
        _postconf(monkeypatch, salida, codigo)
        assert "mail.example.org" in m.identidades_del_servidor()
        assert len(m.identidades_del_servidor()) == 2


def test_configurado_valen_solo_los_indicados(monkeypatch):
    _ajustes(monkeypatch, "mail2.example.org, Mail.example.org")
    _postconf(monkeypatch, "otro.example.org\n")
    assert m.identidades_del_servidor() == {"mail2.example.org", "mail.example.org"}


def test_un_correo_firmado_con_el_myhostname_cuenta_como_autenticado(monkeypatch):
    import email

    _ajustes(monkeypatch)
    _postconf(monkeypatch, "mail2.example.org\n")
    msg = email.message_from_string(
        "Authentication-Results: mail2.example.org;\n"
        " dkim=pass header.d=example.com; dmarc=pass header.from=example.com\n"
        "From: ana@example.com\n\nhola\n"
    )
    assert m.autenticado(msg, "example.com", m.identidades_del_servidor())
    assert not m.autenticado(msg, "example.com", {"mail.example.org"})
