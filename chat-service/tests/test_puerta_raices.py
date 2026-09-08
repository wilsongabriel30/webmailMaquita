# -*- coding: utf-8 -*-
"""N-24: la puerta dedicada del chat admite vales de Raíces, y solo de quien debe.

Antes Raíces firmaba la cookie del chat con la clave MAESTRA del correo. Ahora entra por
la misma puerta que el correo, con el secreto DEDICADO, y la sesión que abre se rige por su
propia regla: tope absoluto y revocación empujada, sin preguntar por una sesión del correo
que no existe. Sin base de datos ni Redis: el directorio y el uso único se sustituyen.
"""
import os
import time
import uuid

import pytest

os.environ.setdefault("CHAT_JWT_SECRET", "secreto-de-pruebas-del-chat-2026")  # gitleaks:allow
os.environ.setdefault("CHAT_SSO_SECRET", "secreto-sso-de-pruebas-2026")  # gitleaks:allow
os.environ.setdefault("CHAT_SESSION_KEY", "clave-de-sesion-de-pruebas-2026")  # gitleaks:allow
os.environ.setdefault("NOTIF_SECRET", "secreto-de-servicios-de-pruebas-2026")  # gitleaks:allow
os.environ.setdefault("CHAT_SOCKETIO_ASYNC_MODE", "threading")
os.environ.setdefault("DATABASE_URL", "postgresql://prueba:prueba@127.0.0.1:1/prueba")
os.environ.pop("CHAT_REDIS_URL", None)

import jwt  # noqa: E402
import app_chat  # noqa: E402
from interfaces.api import sesion_central  # noqa: E402

UID = 777
CORREO = "pasante@example.com"
SSO = os.environ["CHAT_SSO_SECRET"]


@pytest.fixture
def app(monkeypatch):
    a = app_chat.application
    a.config["TESTING"] = True
    monkeypatch.setattr(app_chat, "_uid_por_correo", lambda correo: UID if correo == CORREO else None)
    # Sin Redis, el uso único falla cerrado; aquí se sustituye por uno de memoria.
    usados = set()
    monkeypatch.setattr(app_chat, "_consumir_vale", lambda jti: not (jti in usados or usados.add(jti)))
    sesion_central.resolver_uid = app_chat._uid_por_correo
    sesion_central._memoria.clear()
    sesion_central._contador.clear()
    if "/api/chat/_prueba" not in [r.rule for r in a.url_map.iter_rules()]:
        @a.get("/api/chat/_prueba")
        def _prueba():
            return {"ok": True}
    return a


def _vale(**extra):
    ahora = int(time.time())
    datos = {
        "sub": CORREO,
        "aud": "chat-sso",
        "jti": uuid.uuid4().hex,
        "iat": ahora,
        "exp": ahora + 60,
        "iss": "raices",
        "sid": "sesion-de-raices-1",
        "av": 0,
    }
    datos.update(extra)
    for clave, valor in list(datos.items()):
        if valor is None:
            datos.pop(clave)
    return jwt.encode(datos, SSO, algorithm="HS256")


def test_vale_de_raices_abre_sesion(app):
    """Positivo: con el vale de Raíces se entra y la sesión sirve para las rutas del chat."""
    cli = app.test_client()
    r = cli.get(f"/sso/entrar?t={_vale()}&r=/chat/?embed=1")
    assert r.status_code == 302
    assert cli.get("/api/chat/_prueba").status_code == 200


def test_emisor_desconocido_rechazado(app):
    """Un vale firmado con el secreto correcto pero de otro emisor no entra."""
    cli = app.test_client()
    r = cli.get(f"/sso/entrar?t={_vale(iss='otro-sistema')}&r=/chat/")
    assert r.status_code == 401
    assert cli.get("/api/chat/_prueba").status_code == 401


def test_vale_de_raices_sin_sid_rechazado(app):
    """Sin identificador de sesión no habría forma de revocarla después: no entra."""
    cli = app.test_client()
    assert cli.get(f"/sso/entrar?t={_vale(sid=None)}&r=/chat/").status_code == 401


def test_vale_no_sirve_dos_veces(app):
    """El vale es de un solo uso, también para Raíces."""
    cli = app.test_client()
    v = _vale()
    assert cli.get(f"/sso/entrar?t={v}&r=/chat/").status_code == 302
    otro = app.test_client()
    assert otro.get(f"/sso/entrar?t={v}&r=/chat/").status_code == 401


def test_sesion_de_raices_caduca(app):
    """Pasado el tope absoluto hay que volver a entrar por la puerta."""
    cli = app.test_client()
    assert cli.get(f"/sso/entrar?t={_vale()}&r=/chat/").status_code == 302
    with cli.session_transaction() as s:
        s["expira"] = time.time() - 1
    assert cli.get("/api/chat/_prueba").status_code == 401


def test_revocacion_corta_la_sesion_de_raices(app):
    """La revocación empujada sigue mandando sobre la sesión abierta por Raíces."""
    cli = app.test_client()
    assert cli.get(f"/sso/entrar?t={_vale()}&r=/chat/").status_code == 302
    assert cli.get("/api/chat/_prueba").status_code == 200
    sesion_central.registrar_revocacion(UID, "sesion-de-raices-1", 0)
    assert cli.get("/api/chat/_prueba").status_code == 401


def test_sesion_del_correo_sigue_exigiendo_sid(app):
    """Negativo de siempre: una sesión del correo sin sid/av no vale (F-03 intacto)."""
    cli = app.test_client()
    with cli.session_transaction() as s:
        s["usuario_id"] = UID
        s["usuario_correo"] = CORREO
        s["origen"] = "correo"
        s["validado_hasta"] = time.time() + 300
    assert cli.get("/api/chat/_prueba").status_code == 401
