# -*- coding: utf-8 -*-
"""Aplicaciones del Drive (Editor de PDF y Tableros): sesión por `sid` y archivos comunes.

El webmail guarda la sesión como `imap_pass:<usuario>:<sid>` desde el 12/10/2026
(`backend/app/auth/sesiones.py`); `auth_drive.py` seguía mirando `imap_pass:<usuario>` y
las dos aplicaciones respondían 401 a todo el que tenía la sesión abierta.

`auth_drive.py` y `marca_drive.py` son copias idénticas en cada aplicación (se instalan
por separado): aquí se comprueba que no divergen.
"""
import importlib.util
import os
import re
import sys
import types

import jwt
import pytest
from flask import Flask

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APLICACIONES = os.path.join(RAIZ, "aplicaciones")
APPS = ("pdf_editor", "bi")
COMUNES = ("auth_drive.py", "marca_drive.py")
SECRETO = "valor-de-prueba-del-ci-no-es-un-secreto-89ab"  # gitleaks:allow


def _asegurar_flask_login():
    """El CI del Almacén no instala Flask-Login (es de las aplicaciones): basta un doble."""
    try:
        import flask_login  # noqa: F401
    except ImportError:
        falso = types.ModuleType("flask_login")
        falso.UserMixin = type("UserMixin", (), {"is_authenticated": True})
        falso.LoginManager = type("LoginManager", (), {
            "init_app": lambda self, app: None,
            "request_loader": lambda self, f: f,
        })
        sys.modules["flask_login"] = falso


def _cargar(app, archivo="auth_drive.py"):
    _asegurar_flask_login()
    nombre = "%s_%s" % (archivo[:-3], app)
    spec = importlib.util.spec_from_file_location(nombre, os.path.join(APLICACIONES, app, archivo))
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


def _patron_a_regex(patron):
    """Glob de Redis (con escapes `\\`) → expresión regular, como hace MATCH."""
    salida, i = "", 0
    while i < len(patron):
        c = patron[i]
        if c == "\\" and i + 1 < len(patron):
            salida += re.escape(patron[i + 1])
            i += 2
            continue
        salida += {"*": ".*", "?": "."}.get(c, re.escape(c))
        i += 1
    return re.compile(salida + r"\Z", re.S)


class _RedisFalso:
    def __init__(self, claves):
        self.claves, self.llamadas = set(claves), []

    def exists(self, clave):
        self.llamadas.append(("exists", clave))
        return 1 if clave in self.claves else 0

    def scan_iter(self, match=None, count=None):
        self.llamadas.append(("scan", match, count))
        regex = _patron_a_regex(match)
        return iter(sorted(c for c in self.claves if regex.match(c)))

    def keys(self, *_a, **_k):  # nunca se debe usar: bloquea Redis entero
        raise AssertionError("auth_drive usó KEYS")


@pytest.fixture(params=APPS)
def auth(request, monkeypatch):
    modulo = _cargar(request.param)
    monkeypatch.setattr(modulo, "_REDIS_URL", "redis://192.0.2.10/0")
    monkeypatch.setattr(modulo, "_SECRET", SECRETO)
    return modulo


def _con_redis(monkeypatch, modulo, claves):
    falso = _RedisFalso(claves)
    monkeypatch.setattr(modulo, "_redis", falso)
    return falso


def test_con_sid_vale_solo_la_clave_de_esa_sesion(auth, monkeypatch):
    falso = _con_redis(monkeypatch, auth, {"imap_pass:ana@example.org:SID1"})
    assert auth._sesion_viva("ana@example.org", sid="SID1") is True
    assert auth._sesion_viva("ana@example.org", sid="SID2") is False   # cerrada o revocada
    assert ("exists", "imap_pass:ana@example.org:SID1") in falso.llamadas
    assert not any(ll[0] == "scan" for ll in falso.llamadas)


def test_sid_revocado_no_revive_por_la_clave_antigua_ni_por_otra_sesion(auth, monkeypatch):
    _con_redis(monkeypatch, auth, {"imap_pass:ana@example.org", "imap_pass:ana@example.org:OTRA"})
    assert auth._sesion_viva("ana@example.org", sid="SID1") is False


def test_sin_sid_vale_cualquier_sesion_del_usuario_por_scan_acotado(auth, monkeypatch):
    falso = _con_redis(monkeypatch, auth, {"imap_pass:ana@example.org:SID9"})
    assert auth._sesion_viva("ana@example.org") is True
    scans = [ll for ll in falso.llamadas if ll[0] == "scan"]
    assert scans == [("scan", "imap_pass:ana@example.org:*", auth._LOTE_SCAN)]
    assert 0 < auth._LOTE_SCAN <= 1000


def test_sin_sid_se_conserva_la_clave_antigua(auth, monkeypatch):
    falso = _con_redis(monkeypatch, auth, {"imap_pass:ana@example.org"})
    assert auth._sesion_viva("ana@example.org") is True
    assert not any(ll[0] == "scan" for ll in falso.llamadas)


def test_sin_sid_y_sin_sesiones_no_vale(auth, monkeypatch):
    _con_redis(monkeypatch, auth, {"imap_pass:otra@example.org:SID1", "imap_pass:ana@example.org.mx:SID1"})
    assert auth._sesion_viva("ana@example.org") is False


def test_el_usuario_no_se_cuela_como_comodin(auth, monkeypatch):
    falso = _con_redis(monkeypatch, auth, {"imap_pass:ana@example.org:SID1"})
    assert auth._sesion_viva("*") is False
    assert auth._sesion_viva("an?@example.org") is False
    assert ("scan", "imap_pass:\\*:*", auth._LOTE_SCAN) in falso.llamadas


def test_redis_caido_rechaza(auth, monkeypatch):
    class _Roto:
        def exists(self, _clave):
            raise ConnectionError("sin redis")
    monkeypatch.setattr(auth, "_redis", _Roto())
    assert auth._sesion_viva("ana@example.org", sid="SID1") is False


def _usuario_con_token(auth, payload):
    app = Flask("prueba")
    token = jwt.encode(payload, SECRETO, algorithm="HS256")
    with app.test_request_context("/", headers={"Cookie": "access_token=%s" % token}):
        return auth.usuario_desde_cookie()


def test_cookie_con_sid_de_sesion_abierta_entra(auth, monkeypatch):
    _con_redis(monkeypatch, auth, {"imap_pass:ana@example.org:SID1"})
    usuario = _usuario_con_token(auth, {"sub": "Ana@Example.org", "type": "access", "sid": "SID1"})
    assert usuario is not None and usuario.id == "ana@example.org"


def test_cookie_con_sid_cerrado_no_entra(auth, monkeypatch):
    _con_redis(monkeypatch, auth, {"imap_pass:ana@example.org:SID1"})
    assert _usuario_con_token(auth, {"sub": "ana@example.org", "type": "access", "sid": "SID2"}) is None


def test_cookie_sin_sid_con_sesion_abierta_entra(auth, monkeypatch):
    _con_redis(monkeypatch, auth, {"imap_pass:ana@example.org:SID1"})
    assert _usuario_con_token(auth, {"sub": "ana@example.org", "type": "access"}) is not None


def test_cookie_de_refresco_no_entra(auth, monkeypatch):
    _con_redis(monkeypatch, auth, {"imap_pass:ana@example.org:SID1"})
    assert _usuario_con_token(auth, {"sub": "ana@example.org", "type": "refresh", "sid": "SID1"}) is None


@pytest.mark.parametrize("archivo", COMUNES)
def test_las_copias_de_cada_aplicacion_no_divergen(archivo):
    contenidos = {}
    for app in APPS:
        with open(os.path.join(APLICACIONES, app, archivo), encoding="utf-8") as f:
            contenidos[app] = f.read()
    assert contenidos["pdf_editor"] == contenidos["bi"], (
        "%s difiere entre pdf_editor y bi: copia el cambio en las dos aplicaciones" % archivo)


def test_contrato_con_el_correo():
    """La forma de la clave la define backend/app/auth/sesiones.py; si cambia allí, esto avisa."""
    ruta = os.path.join(os.path.dirname(RAIZ), "backend", "app", "auth", "sesiones.py")
    with open(ruta, encoding="utf-8") as f:
        sesiones = f.read()
    assert re.search(r'f"imap_pass:\{username\}:\{sid\}"', sesiones), "el correo cambió la clave de sesión"
    with open(os.path.join(APLICACIONES, "pdf_editor", "auth_drive.py"), encoding="utf-8") as f:
        fuente = f.read()
    assert '"imap_pass:%s:%s" % (username, sid)' in fuente
    assert ".keys(" not in fuente, "nunca KEYS: bloquea Redis"


def test_ninguna_aplicacion_mira_solo_la_clave_antigua():
    """Todo módulo de las aplicaciones que mira `imap_pass:` debe conocer la clave por sesión."""
    for carpeta, _, nombres in os.walk(APLICACIONES):
        for n in nombres:
            if n.endswith(".py"):
                with open(os.path.join(carpeta, n), encoding="utf-8") as f:
                    fuente = f.read()
                if re.search(r"""["']imap_pass:""", fuente):
                    assert "imap_pass:%s:%s" in fuente, "%s/%s valida solo imap_pass:<usuario>" % (carpeta, n)
