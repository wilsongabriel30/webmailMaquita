# -*- coding: utf-8 -*-
"""Q-2 (Alice): el JWT de Meet va atado a UNA sala, dura minutos y no se persiste."""
import os
import sys
import time

import jwt
import pytest

os.environ.setdefault("JITSI_APP_SECRET", "secreto-jitsi-de-pruebas-2026")  # gitleaks:allow
_RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(_RAIZ, "app"))
from aplicacion.servicios import jitsi_jwt as jj  # noqa: E402


def _payload(tok):
    return jwt.decode(tok, os.environ["JITSI_APP_SECRET"], algorithms=["HS256"], audience="jitsi")


def test_atado_a_la_sala_y_corto():
    tok = jj.generar_jwt(7, "Ana", "ana@example.com", "Maquita2026abc", True)
    p = _payload(tok)
    assert p["room"] == "Maquita2026abc" and p["moderator"] is True
    assert 0 < p["exp"] - int(time.time()) <= jj.MAX_MINUTOS * 60
    assert p["exp"] - p["iat"] == jj.MINUTOS_POR_DEFECTO * 60


def test_sin_sala_concreta_no_hay_token():
    for sala in ("*", "", None, "a b", "sala/otra"):
        with pytest.raises(ValueError):
            jj.generar_jwt(7, "Ana", "ana@example.com", sala, True)


def test_duracion_acotada():
    p = _payload(jj.generar_jwt(7, "Ana", "a@x", "Sala1", False, duracion_min=10_000))
    assert p["exp"] - p["iat"] == jj.MAX_MINUTOS * 60 and p["moderator"] is False
    p = _payload(jj.generar_jwt(7, "Ana", "a@x", "Sala1", False, duracion_min=1))
    assert p["exp"] - p["iat"] == jj.MIN_MINUTOS * 60


def test_url_sala_sin_token_no_lleva_jwt():
    assert "jwt=" not in jj.url_sala("Sala1")
    assert "?jwt=" in jj.url_sala("Sala1", "t.o.k")
