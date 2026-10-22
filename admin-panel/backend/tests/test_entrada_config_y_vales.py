"""Configuración de OIDC (secreto cifrado y nunca devuelto, validaciones), vales de la consola y vale
de soporte del portal de dominio desde el panel."""

import asyncio
import hashlib
from datetime import datetime, timedelta, timezone

import pytest
from cryptography.fernet import Fernet
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.admins_dominio import soporte
from app.auth.dependencies import require_superadmin
from app.auth.jwt import decode_token
from app.entrada import cifrado, oidc_config, vales
from dobles_entrada import BaseFalsa

SUPERADMIN = {"id": 1, "username": "jefa", "role": "superadmin", "session_id": 1, "totp": True}


@pytest.fixture
def mundo():
    base = BaseFalsa()
    base.usuario("jefa")
    app = FastAPI()
    for r in (oidc_config.router, vales.router, soporte.router):
        app.include_router(r)
    app.state.db = base
    quien = dict(SUPERADMIN)
    app.dependency_overrides[require_superadmin] = lambda: quien
    return base, TestClient(app, base_url="https://panel.example.org:8443"), quien


BUENA = {"activado": True, "emisor": "https://id.example.org/", "client_id": "panel-correo",
         "client_secret": "s3creto-largo", "claim_usuario": "preferred_username", "texto_boton": "Entrar con Andes"}


def test_guardar_cifra_el_secreto_y_no_lo_devuelve(mundo):
    base, c, _ = mundo
    r = c.put("/api/auth/oidc/config", json=BUENA)
    assert r.status_code == 200, r.text
    assert "s3creto-largo" not in r.text and r.json()["secreto_guardado"] is True
    guardado = base.config["client_secret_cifrado"]
    assert guardado.startswith("gAAAA") and cifrado.descifrar(guardado) == "s3creto-largo"
    assert base.config["emisor"] == "https://id.example.org"  # sin la barra final
    ver = c.get("/api/auth/oidc/config").json()
    assert "s3creto" not in str(ver) and ver["url_vuelta"] == "https://panel.example.org:8443/api/auth/oidc/vuelta"
    (aud,) = [a for a in base.auditoria if a["accion"] == "oidc_config"]
    assert aud["detalles"]["secreto_cambiado"] is True and "s3creto" not in str(aud)
    # Guardar sin secreto conserva el que había.
    c.put("/api/auth/oidc/config", json={**BUENA, "client_secret": "", "texto_boton": "Otro"})
    assert base.config["client_secret_cifrado"] == guardado


@pytest.mark.parametrize("cambio", [
    {"emisor": "http://id.example.org"}, {"emisor": "https://id.example.org/ espacio"}, {"emisor": "javascript:x"},
    {"client_id": "con espacio"}, {"claim_usuario": "1numero"}, {"claim_grupos": "a b"},
    {"grupo_requerido": "admins"},  # sin claim de grupos
    {"rol_nuevo": "dios"}, {"texto_boton": "<script>"}, {"texto_boton": "x" * 61},
    {"client_secret": "con\nsalto"},
])
def test_validaciones(mundo, cambio):
    base, c, _ = mundo
    assert c.put("/api/auth/oidc/config", json={**BUENA, **cambio}).status_code == 400
    assert base.config["activado"] is False


def test_activar_sin_secreto(mundo):
    _, c, _ = mundo
    assert c.put("/api/auth/oidc/config", json={**BUENA, "client_secret": ""}).status_code == 400


def test_url_vuelta_de_la_organizacion(monkeypatch):
    from app import organizacion

    monkeypatch.setattr(organizacion, "url", lambda clave, defecto: "https://mail.example.org:8443" if clave == "ORG_URL_PANEL" else defecto)

    class P:
        headers = {"host": "inventado.example.com"}

    assert oidc_config.url_vuelta(P()) == "https://mail.example.org:8443/api/auth/oidc/vuelta"


def test_rotacion_de_la_llave(monkeypatch):
    vieja = Fernet.generate_key().decode()
    monkeypatch.setenv("WEBMAIL_CREDENTIAL_ENCRYPTION_KEY", vieja)
    token = cifrado.cifrar("x")
    monkeypatch.setenv("WEBMAIL_CREDENTIAL_ENCRYPTION_KEY", Fernet.generate_key().decode())
    with pytest.raises(cifrado.InvalidToken):
        cifrado.descifrar(token)
    monkeypatch.setenv("WEBMAIL_CREDENTIAL_ENCRYPTION_KEY_ANTERIOR", vieja)
    assert cifrado.descifrar(token) == "x"
    monkeypatch.delenv("WEBMAIL_CREDENTIAL_ENCRYPTION_KEY")
    monkeypatch.delenv("CREDENTIAL_ENCRYPTION_KEY", raising=False)
    with pytest.raises(cifrado.SinLlave):
        cifrado.cifrar("x")


# --- Vales de la consola ---


def _vale_consola(base, user_id=1, segundos=120, exige_totp=False):
    return asyncio.run(vales.emitir(base, user_id, "consola", exige_totp, segundos, "consola:root"))


def test_vale_de_consola_abre_sesion_sin_segundo_factor(mundo):
    base, c, _ = mundo
    base.usuarios[1].update(totp_secret="JBSWY3DPEHPK3PXP", totp_enabled=True)
    vale = _vale_consola(base)
    assert hashlib.sha256(vale.encode()).hexdigest() in base.vales and vale not in base.vales
    r = c.post("/api/auth/vale", json={"vale": vale})
    assert r.status_code == 200
    assert decode_token(r.json()["token"])["totp"] is False  # no sirve para impersonar buzones
    (aud,) = [a for a in base.auditoria if a["accion"] == "login_vale"]
    assert aud["detalles"] == {"origen": "consola", "segundo_factor": False}
    assert c.post("/api/auth/vale", json={"vale": vale}).status_code == 401


def test_vale_caducado_o_inventado(mundo):
    base, c, _ = mundo
    vale = _vale_consola(base)
    base.vales[hashlib.sha256(vale.encode()).hexdigest()]["expires_at"] = datetime.now(timezone.utc) - timedelta(seconds=1)
    assert c.post("/api/auth/vale", json={"vale": vale}).status_code == 401
    for malo in ("", "corto", "x" * 300, "'; DROP TABLE admin_users; --", None):
        assert c.post("/api/auth/vale", json={"vale": malo}).status_code == 401
    assert not base.sesiones


def test_vale_de_cuenta_desactivada(mundo):
    base, c, _ = mundo
    vale = _vale_consola(base)
    base.usuarios[1]["active"] = False
    assert c.post("/api/auth/vale", json={"vale": vale}).status_code == 403


# --- Vale de soporte del portal de dominio ---


def test_soporte_emite_vale_de_solo_lectura(mundo, monkeypatch):
    base, c, _ = mundo
    r = c.post("/api/admins-dominio/soporte", json={"dominio": "UNO.example", "motivo": "incidencia\n12"})
    assert r.status_code == 201, r.text
    datos = r.json()
    assert datos["url"].startswith("https://mail.uno.example:8444/?vale=")  # el portal propio de la empresa
    assert datos["modo"] == "solo_lectura" and datos["valido_segundos"] == 300
    vale = datos["url"].split("vale=")[1]
    (fila,) = base.vales_soporte
    assert fila[0] == hashlib.sha256(vale.encode()).hexdigest() and vale not in fila
    assert fila[1] == "uno.example" and fila[2] is True and fila[3] == "jefa" and "\n" not in fila[4]
    (aud,) = [a for a in base.auditoria if a["accion"] == "soporte_vale_emitido"]
    assert aud["objetivo"] == "uno.example" and aud["detalles"]["modo"] == "solo_lectura"


def test_soporte_con_acciones(mundo):
    base, c, _ = mundo
    r = c.post("/api/admins-dominio/soporte", json={"dominio": "uno.example", "modo": "con_acciones", "vida": 60})
    assert r.status_code == 201 and base.vales_soporte[0][2] is False


@pytest.mark.parametrize("cuerpo,codigo", [
    ({"dominio": "dos.example"}, 404), ({"dominio": "no es dominio"}, 400), ({"dominio": "uno.example", "modo": "todo"}, 400),
    ({"dominio": "uno.example", "vida": 5}, 400), ({"dominio": "uno.example", "vida": 901}, 400),
])
def test_soporte_rechaza(mundo, cuerpo, codigo):
    base, c, _ = mundo
    assert c.post("/api/admins-dominio/soporte", json=cuerpo).status_code == codigo
    assert not base.vales_soporte


def test_soporte_exige_sesion_con_segundo_factor(mundo):
    base, c, quien = mundo
    quien["totp"] = False
    assert c.post("/api/admins-dominio/soporte", json={"dominio": "uno.example"}).status_code == 403
    assert not base.vales_soporte
