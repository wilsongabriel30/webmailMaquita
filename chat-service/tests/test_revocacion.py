# -*- coding: utf-8 -*-
"""Celdas del chat en la matriz de cierre de F-03: {revocación central} × {chat REST,
chat Socket.IO}. Sin base de datos ni Redis: el directorio se sustituye por un doble y
el estado de revocación cae en el almacén en memoria de sesion_central."""
import os
import time

import pytest

os.environ.setdefault("CHAT_JWT_SECRET", "secreto-de-pruebas-del-chat-2026")
os.environ.setdefault("CHAT_SSO_SECRET", "secreto-sso-de-pruebas-2026")
os.environ.setdefault("CHAT_SESSION_KEY", "clave-de-sesion-de-pruebas-2026")
os.environ.setdefault("NOTIF_SECRET", "secreto-de-servicios-de-pruebas-2026")
os.environ.setdefault("CHAT_SOCKETIO_ASYNC_MODE", "threading")
os.environ.pop("CHAT_REDIS_URL", None)

import app_chat  # noqa: E402  (arranca la app con los secretos de arriba)
from interfaces.api import sesion_central  # noqa: E402

UID = 4242
CORREO = "matriz@example.com"
SECRETO = os.environ["NOTIF_SECRET"]


@pytest.fixture
def app(monkeypatch):
    a = app_chat.application
    a.config["TESTING"] = True
    monkeypatch.setattr(app_chat, "_uid_por_correo", lambda correo: UID if correo == CORREO else None)
    sesion_central.resolver_uid = app_chat._uid_por_correo
    sesion_central._memoria.clear()
    sesion_central._contador.clear()
    if "/api/chat/_prueba" not in [r.rule for r in a.url_map.iter_rules()]:
        @a.get("/api/chat/_prueba")
        def _prueba():
            return {"ok": True}
    return a


def _sesion(client, sid="sid-A", av=1):
    with client.session_transaction() as s:
        s["usuario_id"] = UID
        s["usuario_correo"] = CORREO
        s["usuario_nombre"] = "Prueba"
        s["sid"] = sid
        s["av"] = av
        s["validado_hasta"] = time.time() + 300


def _revocar(client, sid="*", av=2, secreto=SECRETO):
    return client.post(
        "/api/chat/sesion/revocar",
        json={"user": CORREO, "sid": sid, "av": av},
        headers={"X-Notif-Secret": secreto},
    )


def test_rest_vale_con_sesion_central(app):
    c = app.test_client()
    _sesion(c)
    assert c.get("/api/chat/_prueba").status_code == 200


def test_sesion_sin_sid_av_no_vale(app):
    c = app.test_client()
    with c.session_transaction() as s:
        s["usuario_id"] = UID
        s["usuario_correo"] = CORREO
    assert c.get("/api/chat/_prueba").status_code == 401


def test_revocacion_global_corta_rest_y_socketio(app):
    c = app.test_client()
    _sesion(c)
    sio = app_chat.socketio.test_client(app, flask_test_client=c)
    assert sio.is_connected()
    r = _revocar(c, sid="*", av=2)
    assert r.status_code == 200 and r.json["desconectados"] >= 1
    assert not sio.is_connected()  # celda Socket.IO
    assert c.get("/api/chat/_prueba").status_code == 401  # celda REST
    # una sesión nueva con la generación nueva sí vale
    _sesion(c, sid="sid-B", av=2)
    assert c.get("/api/chat/_prueba").status_code == 200


def test_revocacion_de_un_sid_no_toca_los_demas(app):
    a, b = app.test_client(), app.test_client()
    _sesion(a, sid="sid-A")
    _sesion(b, sid="sid-B")
    sio_a = app_chat.socketio.test_client(app, flask_test_client=a)
    sio_b = app_chat.socketio.test_client(app, flask_test_client=b)
    assert sio_a.is_connected() and sio_b.is_connected()
    assert _revocar(a, sid="sid-A", av=1).status_code == 200
    assert not sio_a.is_connected()
    assert sio_b.is_connected()
    assert a.get("/api/chat/_prueba").status_code == 401
    assert b.get("/api/chat/_prueba").status_code == 200


def test_socketio_rechaza_sesion_revocada_al_conectar(app):
    c = app.test_client()
    _sesion(c, sid="sid-C", av=1)
    sesion_central.registrar_revocacion(UID, "*", 5)
    sio = app_chat.socketio.test_client(app, flask_test_client=c)
    assert not sio.is_connected()


def test_revalidacion_falla_cerrado_si_el_correo_no_responde(app, monkeypatch):
    c = app.test_client()
    _sesion(c)
    with c.session_transaction() as s:
        s["validado_hasta"] = 0  # toca revalidar
    monkeypatch.setattr(sesion_central, "_revalidar_con_correo", lambda correo, sid: None)
    assert c.get("/api/chat/_prueba").status_code == 401


def test_revalidacion_con_correo_que_confirma(app, monkeypatch):
    c = app.test_client()
    _sesion(c)
    with c.session_transaction() as s:
        s["validado_hasta"] = 0
    monkeypatch.setattr(sesion_central, "_revalidar_con_correo", lambda correo, sid: True)
    assert c.get("/api/chat/_prueba").status_code == 200


def test_revocar_exige_secreto_y_tiene_limite(app):
    c = app.test_client()
    assert _revocar(c, secreto="otro").status_code == 403
    assert c.post("/api/chat/sesion/revocar", json={"user": CORREO}).status_code == 403
    ok = 0
    for _ in range(sesion_central.LIMITE_REVOCAR_POR_MIN + 5):
        if _revocar(c).status_code == 200:
            ok += 1
    assert ok == sesion_central.LIMITE_REVOCAR_POR_MIN
    assert _revocar(c).status_code == 429


def test_notificaciones_exigen_secreto_correcto_en_el_guard(app):
    """H-02: el before_request compara el secreto, no su mera presencia."""
    c = app.test_client()
    r = c.post("/api/chat/notificaciones", json={}, headers={"X-Notif-Secret": "malo"})
    assert r.status_code in (401, 403)
