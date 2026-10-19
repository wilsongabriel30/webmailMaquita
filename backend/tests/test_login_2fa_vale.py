"""Segundo paso del inicio de sesión: el vale admite varios códigos equivocados.

Caso del 19/10/2026: el primer código erróneo consumía el vale y la pantalla seguía
reintentando con él, así que todo código posterior (aunque fuera válido) daba 401.
"""

import asyncio
import json
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.auth import router


class _RedisFalso:
    def __init__(self):
        self.d = {}

    async def get(self, k):
        return self.d.get(k)

    async def set(self, k, v, ex=None):
        self.d[k] = v

    async def incr(self, k):
        self.d[k] = int(self.d.get(k, 0)) + 1
        return self.d[k]

    async def ttl(self, k):
        return 100 if k in self.d else -2

    async def expire(self, k, s):
        return True

    async def delete(self, *ks):
        for k in ks:
            self.d.pop(k, None)


def _peticion(redis):
    app = SimpleNamespace(state=SimpleNamespace(redis=redis, db_pool=None))
    return SimpleNamespace(app=app, client=SimpleNamespace(host="127.0.0.1"))


@pytest.fixture
def entorno(monkeypatch):
    redis = _RedisFalso()
    redis.d["login_ticket:v1"] = json.dumps({"u": "ana@example.com", "p": "cifrada"})

    async def _nada(*a, **k):
        return None

    async def _falso(*a, **k):
        return False

    async def _sesion(*a, **k):
        return {"sid": "s"}

    async def _totp(db, username, code):
        return code == "123456"

    monkeypatch.setattr(router, "validate_totp_code", _totp)
    monkeypatch.setattr(router, "_check_login_rate_limit", _nada)
    monkeypatch.setattr(router, "_clear_login_rate_limit", _nada)
    monkeypatch.setattr(router, "crear_sesion", _sesion)
    monkeypatch.setattr(router, "poner_cookies_sesion", lambda *a, **k: None)
    monkeypatch.setattr(router, "debe_cambiar_clave", _falso)
    monkeypatch.setattr(router, "debe_activar_2fa", _falso)
    monkeypatch.setattr(router.asyncio, "sleep", _nada)  # sin la espera de 1,5 s
    import app.auth.dispositivos_confianza as dc
    import app.core.session as ses

    monkeypatch.setattr(dc, "recordar", _nada)
    monkeypatch.setattr(ses, "decrypt_password", lambda p: "clave")
    return redis


def _canjear(redis, vale, codigo):
    cuerpo = router.Login2FARequest(ticket=vale, totp_code=codigo)
    return asyncio.run(router.login_2fa(cuerpo, _peticion(redis), SimpleNamespace()))


def test_codigo_erroneo_no_consume_el_vale(entorno):
    with pytest.raises(HTTPException) as e:
        _canjear(entorno, "v1", "000000")
    assert e.value.status_code == 401
    assert e.value.detail == router.AVISO_CODIGO_INCORRECTO
    assert "login_ticket:v1" in entorno.d  # el vale sigue vivo
    # El código correcto en el segundo intento entra
    r = _canjear(entorno, "v1", "123456")
    assert r["username"] == "ana@example.com"
    assert "login_ticket:v1" not in entorno.d  # canjeado: no sirve dos veces


def test_vale_agotado_pide_la_contrasena_de_nuevo(entorno):
    for _ in range(router.INTENTOS_POR_VALE):
        with pytest.raises(HTTPException) as e:
            _canjear(entorno, "v1", "000000")
        assert e.value.detail == router.AVISO_CODIGO_INCORRECTO
    with pytest.raises(HTTPException) as e:
        _canjear(entorno, "v1", "123456")  # ya da igual que sea correcto
    assert e.value.detail == router.AVISO_VALE_AGOTADO
    assert "login_ticket:v1" not in entorno.d


def test_vale_inexistente_pide_la_contrasena_de_nuevo(entorno):
    with pytest.raises(HTTPException) as e:
        _canjear(entorno, "no-existe", "123456")
    assert e.value.status_code == 401
    assert e.value.detail == router.AVISO_VALE_AGOTADO
