# -*- coding: utf-8 -*-
"""P2 de la quinta revisión (Alice): presencia solo a relacionados (M-03/L-01), llamadas con
relación y bloqueo (L-02), conversación directa con tenant y bloqueo (L-03) y limitador
conservador sin Redis (L-04). Sin base ni Redis: dobles."""
import logging
import os

import pytest

os.environ.setdefault("CHAT_JWT_SECRET", "secreto-de-pruebas-del-chat-2026")  # gitleaks:allow
os.environ.setdefault("CHAT_SSO_SECRET", "secreto-sso-de-pruebas-2026")  # gitleaks:allow
os.environ.setdefault("CHAT_SESSION_KEY", "clave-de-sesion-de-pruebas-2026")  # gitleaks:allow
os.environ.setdefault("NOTIF_SECRET", "secreto-de-servicios-de-pruebas-2026")  # gitleaks:allow
os.environ.setdefault("CHAT_SOCKETIO_ASYNC_MODE", "threading")
os.environ.setdefault("DATABASE_URL", "postgresql://prueba:prueba@127.0.0.1:1/prueba")
os.environ.pop("CHAT_REDIS_URL", None)

import app_chat  # noqa: E402,F401
from interfaces import relacion_chat as rc  # noqa: E402
from interfaces.websocket.limitador import FACTOR_SIN_REDIS, Limitador  # noqa: E402


# ------------------------------------------------------------------ L-04 limitador
class _RedisContador:
    def __init__(self):
        self.n = {}

    def incr(self, k):
        self.n[k] = self.n.get(k, 0) + 1
        return self.n[k]

    def expire(self, k, s):
        return True


class _RedisRoto(_RedisContador):
    def incr(self, k):
        raise ConnectionError("redis caído")


def test_con_redis_el_tope_es_el_configurado():
    lim = Limitador(_RedisContador())
    assert [lim.is_allowed("send:1", 20, 10) for _ in range(21)] == [True] * 20 + [False]


def test_sin_redis_tope_conservador_y_marca(caplog):
    caplog.set_level(logging.ERROR, logger="seguridad.chat.limitador")
    lim = Limitador(None)
    tope = max(1, 20 // FACTOR_SIN_REDIS)
    res = [lim.is_allowed("send:1", 20, 10) for _ in range(tope + 1)]
    assert res == [True] * tope + [False]
    assert sum("RATE_LIMIT_SIN_REDIS" in r.message for r in caplog.records) == 1  # una vez, no por evento


def test_redis_que_falla_a_mitad_cae_al_tope_conservador(caplog):
    caplog.set_level(logging.ERROR, logger="seguridad.chat.limitador")
    lim = Limitador(_RedisRoto())
    assert [lim.is_allowed("typing:1", 4, 5) for _ in range(2)] == [True, False]  # 4 // 4 = 1
    assert any("RATE_LIMIT_SIN_REDIS" in r.message for r in caplog.records)


# ------------------------------------------------------------------ M-03/L-01 presencia
def test_filtrar_visibles_solo_relacionados(monkeypatch):
    monkeypatch.setattr(rc, "relacionados", lambda db, uid, redis=None: {7, 8, 9})
    assert rc.filtrar_visibles(None, 7, [8, "9", 10, "x", None]) == [8, 9]
    assert rc.puede_ver(None, 7, 9) and not rc.puede_ver(None, 7, 10)


def test_relacionados_fallo_cerrado_sin_base(caplog):
    class _DB:
        def query(self, *a):
            raise RuntimeError("sin base")

    caplog.set_level(logging.ERROR, logger="seguridad.chat.relacion")
    assert rc.relacionados(_DB(), 7) == {7}
    assert any("RELACION_NO_CONSULTABLE" in r.message for r in caplog.records)


def test_relacionados_usa_la_cache(monkeypatch):
    class _Redis:
        def __init__(self):
            self.d = {}

        def get(self, k):
            return self.d.get(k)

        def set(self, k, v, ttl_segundos=None):
            self.d[k] = v

        def delete(self, *ks):
            for k in ks:
                self.d.pop(k, None)

    r = _Redis()
    r.d[rc.CLAVE_CACHE % 7] = "7,8,9"
    assert rc.relacionados(None, 7, r) == {7, 8, 9}  # sin tocar la base
    rc.olvidar(r, 7)
    assert rc.CLAVE_CACHE % 7 not in r.d


# ------------------------------------------------------------------ L-02 / L-03 contacto y llamadas
def test_puede_contactar_tenant_y_bloqueo(monkeypatch):
    import tenant_chat

    monkeypatch.setattr(tenant_chat, "primer_bloqueado", lambda db, uid, otros: None)
    monkeypatch.setattr(rc, "bloqueo_entre", lambda db, a, b: False)
    assert rc.puede_contactar(None, 1, 2) == (True, "")
    assert rc.puede_contactar(None, 1, 1) == (False, "mismo_usuario")
    assert rc.puede_contactar(None, 1, "x") == (False, "destino_invalido")
    monkeypatch.setattr(rc, "bloqueo_entre", lambda db, a, b: True)
    assert rc.puede_contactar(None, 1, 2) == (False, "bloqueo")
    monkeypatch.setattr(tenant_chat, "primer_bloqueado", lambda db, uid, otros: otros[0])
    assert rc.puede_contactar(None, 1, 2) == (False, "otra_organizacion")


def test_puede_llamar_exige_conversacion_compartida(monkeypatch):
    monkeypatch.setattr(rc, "puede_contactar", lambda db, a, b: (True, ""))
    monkeypatch.setattr(rc, "comparten_conversacion", lambda db, a, b, c=None, redis=None: c == 55)
    assert rc.puede_llamar(None, 1, 2, conversacion_id=55) == (True, "")
    assert rc.puede_llamar(None, 1, 2, conversacion_id=56) == (False, "sin_conversacion")
    monkeypatch.setattr(rc, "puede_contactar", lambda db, a, b: (False, "bloqueo"))
    assert rc.puede_llamar(None, 1, 2, conversacion_id=55) == (False, "bloqueo")


def test_bloqueo_entre_fallo_cerrado():
    class _DB:
        def query(self, *a):
            raise RuntimeError("sin base")

    assert rc.bloqueo_entre(_DB(), 1, 2) is True
