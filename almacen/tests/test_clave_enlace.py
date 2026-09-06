# -*- coding: utf-8 -*-
"""F-08: clave de enlace fuera de la URL, Argon2id con sal, límite de intentos."""
import hashlib
import os
import sys

import pytest
from flask import Flask

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "servicio"))
import clave_enlace as ce  # noqa: E402

app = Flask(__name__)


def test_hash_es_argon2id_con_sal():
    h1, h2 = ce.hash_clave("secreta"), ce.hash_clave("secreta")
    assert h1.startswith("$argon2id$") and h2.startswith("$argon2id$")
    assert h1 != h2  # sal distinta cada vez


def test_verificar_argon2_y_heredado():
    h = ce.hash_clave("secreta")
    assert ce.verificar_clave(h, "secreta") == (True, False)
    assert ce.verificar_clave(h, "otra") == (False, False)
    heredado = hashlib.sha256(b"vieja").hexdigest()
    assert ce.verificar_clave(heredado, "vieja") == (True, True)  # acierta y pide rehash
    assert ce.verificar_clave(heredado, "mala") == (False, False)
    assert ce.verificar_clave(None, "") == (True, False)


def test_leer_clave_ignora_el_query():
    with app.test_request_context("/x?clave=filtrada"):
        assert ce.leer_clave() == ""
    with app.test_request_context("/x?clave=filtrada", headers={"X-Clave-Enlace": "buena"}):
        assert ce.leer_clave() == "buena"
    with app.test_request_context("/x", method="POST", json={"clave": "cuerpo"}):
        assert ce.leer_clave() == "cuerpo"


class _Cur:
    def __init__(self, bd):
        self.bd, self._fila = bd, None

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def execute(self, sql, params=()):
        s = " ".join(sql.split())
        if s.startswith("SELECT n FROM compartidos_intentos"):
            n = self.bd.get(params[:3])
            self._fila = (n,) if n is not None else None
        elif s.startswith("INSERT INTO compartidos_intentos"):
            self.bd[params[:3]] = self.bd.get(params[:3], 0) + 1
        elif s.startswith("DELETE FROM compartidos_intentos"):
            pass
        else:
            raise AssertionError(s)

    def fetchone(self):
        return self._fila


class _Con:
    def __init__(self, bd):
        self.bd = bd

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def cursor(self):
        return _Cur(self.bd)


def test_limite_por_enlace_e_ip_y_rehash():
    bd, actualizaciones = {}, []
    conexion = lambda: _Con(bd)  # noqa: E731
    ejecutar = lambda sql, params: actualizaciones.append(params)  # noqa: E731
    comp = {"token": "t1", "clave_hash": hashlib.sha256(b"vieja").hexdigest()}
    with app.test_request_context("/x", headers={"X-Clave-Enlace": "mala"}):
        for _ in range(ce.INTENTOS_MAX):
            assert ce.comprobar_clave(conexion, comp, ejecutar) == (False, 401)
        assert ce.comprobar_clave(conexion, comp, ejecutar) == (False, 429)
    with app.test_request_context("/x", headers={"X-Clave-Enlace": "vieja"}):
        # la IP agotada sigue bloqueada aunque acierte
        assert ce.comprobar_clave(conexion, comp, ejecutar) == (False, 429)
    with app.test_request_context("/x", headers={"X-Clave-Enlace": "vieja", "X-Real-IP": "10.0.0.9"}):
        assert ce.comprobar_clave(conexion, comp, ejecutar) == (True, 200)
    assert actualizaciones and actualizaciones[0][0].startswith("$argon2id$")  # migrado a Argon2id
    assert ce.comprobar_clave(conexion, {"token": "t2", "clave_hash": None}, ejecutar) == (True, 200)


def test_cabeceras_publicas():
    assert ce.CABECERAS_PUBLICAS["Referrer-Policy"] == "no-referrer"
    assert ce.CABECERAS_PUBLICAS["Cache-Control"] == "no-store"
