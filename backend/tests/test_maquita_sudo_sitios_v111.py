"""maquita-sudo: forma exacta de las órdenes de maquita-sitios de la v1.11 (git de los sitios PHP y CPU y memoria)
y de los alias largos. Las del sistema (git-desplegar-ahora, recursos-recoger) no pasan."""

import base64
import importlib.machinery
import importlib.util
import json
import os

import pytest

_RUTA = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                     "deploy", "sudoers", "maquita-sudo")
_loader = importlib.machinery.SourceFileLoader("maquita_sudo_v111", _RUTA)
_spec = importlib.util.spec_from_loader("maquita_sudo_v111", _loader)
ms = importlib.util.module_from_spec(_spec)
_loader.exec_module(ms)


def b64(valor):
    return base64.urlsafe_b64encode(json.dumps(valor).encode()).decode().rstrip("=")


def _ok(*args):
    return ms.autorizar("maquita-admin", "maquita-sitios", list(args))


def _no(*args, usuario="maquita-admin"):
    with pytest.raises(ms.Rechazo):
        ms.autorizar(usuario, "maquita-sitios", list(args))


def test_ordenes_permitidas():
    for orden in ("git-estado", "git-clave", "recursos"):
        assert _ok(orden, "example.org") == [orden, "example.org"]
    largo = b64({"repo": "git@git.example.org:a/" + "b" * 280 + ".git", "exclusiones": ["subidas"] * 20})
    assert len(largo) > 300  # pasa del tope general de 300 caracteres
    assert _ok("git-configurar", "example.org", largo)
    assert _ok("git-gancho", "example.org", "activar") and _ok("git-gancho", "example.org", "desactivar")
    assert _ok("git-desplegar", "example.org", "panel") and _ok("git-desplegar", "example.org", "gancho")
    assert _ok("git-volver", "example.org", "20261021-101010")
    assert _ok("git-quitar", "example.org", "example.org")


def test_alias_largos_pasan():
    lista = b64([f"nombre-largo-de-alias-{i}.example.org" for i in range(10)])
    assert len(lista) > 300
    assert _ok("alias", "example.org", lista)


@pytest.mark.parametrize("args", [
    ["git-desplegar-ahora", "example.org", "panel"], ["recursos-recoger"], ["git-estado"], ["git-estado", "Example.org"],
    ["git-estado", "example.org", "x"], ["git-configurar", "example.org", "no es base64"], ["git-configurar", "example.org"],
    ["git-gancho", "example.org", "renovar"], ["git-desplegar", "example.org", "otro"], ["git-desplegar", "example.org"],
    ["git-volver", "example.org", "../../x"], ["git-volver", "example.org", "20261021-1010"],
    ["git-quitar", "example.org", "example.com"], ["recursos", "../example.org"], ["git-otra", "example.org"],
])
def test_formas_rechazadas(args):
    _no(*args)


def test_solo_el_panel():
    _no("git-estado", "example.org", usuario="www-data")
    _no("recursos", "example.org", usuario="nadie")


# --- Autenticación de git (repositorios privados): validador aparte, deploy/sitios/lib/sudo_git_credencial.py ---


def test_credencial_formas_permitidas():
    assert _ok("git-credencial", "example.org") == ["git-credencial", "example.org"]
    assert _ok("git-credencial-borrar", "example.org") == ["git-credencial-borrar", "example.org"]
    subida = "0123456789abcdef0123456789abcdef.cred"
    assert _ok("git-credencial-guardar", "example.org", subida) == ["git-credencial-guardar", "example.org", subida]


@pytest.mark.parametrize("args", [
    ["git-credencial"], ["git-credencial", "Example.org"], ["git-credencial", "example.org", "x"],
    ["git-credencial-guardar", "example.org"], ["git-credencial-guardar", "example.org", "../x.cred"],
    ["git-credencial-guardar", "example.org", "0123456789abcdef0123456789abcdef.txt"],
    ["git-credencial-guardar", "example.org", b64({"metodo": "token-https", "token": "token-ficticio-de-prueba"})],
    ["git-credencial-borrar", "example.org", "example.org"], ["git-credencial-otra", "example.org"],
])
def test_credencial_formas_rechazadas(args):
    _no(*args)


def test_credencial_sin_el_validador_no_pasa(monkeypatch):
    monkeypatch.setattr(ms.os.path, "isfile", lambda ruta: False)
    _no("git-credencial", "example.org")
