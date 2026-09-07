"""Lección de N-15: las sondas de integraciones clasifican bien y detectan copias distintas."""

import importlib.machinery
import importlib.util
import os

_RUTA = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "deploy",
    "hardening",
    "vigilar-integraciones.py",
)
_loader = importlib.machinery.SourceFileLoader("vigilar_integraciones", _RUTA)
_spec = importlib.util.spec_from_loader("vigilar_integraciones", _loader)
vi = importlib.util.module_from_spec(_spec)
_loader.exec_module(vi)


def test_clasificar_http():
    assert vi.clasificar(200) == "ok"
    assert vi.clasificar(401) == "desajuste" and vi.clasificar(403) == "desajuste"
    assert vi.clasificar(502) == "servicio" and vi.clasificar(None) == "servicio"
    # la sonda del chat espera 400 (clave aceptada, cuerpo vacío)
    assert (
        vi.clasificar(400, ok=(400,)) == "ok"
        and vi.clasificar(200, ok=(400,)) == "servicio"
    )


def test_leer_env(tmp_path):
    f = tmp_path / ".env"
    f.write_text(
        "# comentario\nA=1\nB='dos'\nC=\"tres\"\nMALO\nD=x=y\n", encoding="utf-8"
    )
    assert vi.leer_env(str(f)) == {"A": "1", "B": "dos", "C": "tres", "D": "x=y"}
    assert vi.leer_env(str(tmp_path / "no-existe")) == {}


def test_secretos_copias_identicas_o_no():
    be = {
        "SECRET_KEY": "s1",
        "ADMIN_JWT_SECRET": "a1",
        "CREDENTIAL_ENCRYPTION_KEY": "c1",
    }
    al = {"WEBMAIL_SECRET_KEY": "s1"}
    pa = {
        "WEBMAIL_SECRET_KEY": "s1",
        "ADMIN_JWT_SECRET": "a1",
        "WEBMAIL_ADMIN_JWT_SECRET": "a1",
        "WEBMAIL_CREDENTIAL_ENCRYPTION_KEY": "c1",
    }
    assert (
        vi.sonda_secretos(be, al, pa, [("bi", {"WEBMAIL_SECRET_KEY": "s1"})])[1] == "ok"
    )
    n, e, d = vi.sonda_secretos(be, dict(al, WEBMAIL_SECRET_KEY="otro"), pa, [])
    assert (
        e == "desajuste" and d.startswith("SECRET_KEY:") and "otro" not in d
    )  # nunca el valor, solo un hash corto
    n, e, d = vi.sonda_secretos(
        be, al, dict(pa, WEBMAIL_CREDENTIAL_ENCRYPTION_KEY="zz"), []
    )
    assert e == "desajuste" and "CREDENTIAL_ENCRYPTION_KEY" in d
