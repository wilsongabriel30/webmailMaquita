"""Entrada al panel por OpenID Connect: flujo completo con PKCE, state y nonce contra un proveedor
simulado, validación del id_token y enlace con admin_users sin crear cuentas por sorpresa."""

import asyncio
import time
from urllib.parse import parse_qs, urlsplit

import pyotp
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.auth.dependencies import require_superadmin
from app.auth.jwt import decode_token
from app.entrada import cifrado, oidc_config, oidc_protocolo, oidc_rutas, vales
from dobles_entrada import CLIENT_ID, EMISOR, SECRETO, BaseFalsa, ProveedorFalso

SUPERADMIN = {"id": 1, "username": "jefa", "role": "superadmin", "session_id": 1, "totp": True}


def _app(base):
    app = FastAPI()
    for r in (oidc_config.router, oidc_rutas.router, vales.router):
        app.include_router(r)
    app.state.db = base
    app.dependency_overrides[require_superadmin] = lambda: SUPERADMIN
    return app


@pytest.fixture
def mundo(monkeypatch):
    base, idp = BaseFalsa(), ProveedorFalso()
    base.usuario("admin")
    base.config.update(activado=True, emisor=EMISOR, client_id=CLIENT_ID,
                       client_secret_cifrado=cifrado.cifrar(SECRETO))
    monkeypatch.setattr(oidc_protocolo, "transporte", idp.transporte())
    oidc_protocolo.olvidar_cache()
    c = TestClient(_app(base), base_url="https://panel.example.org:8443", follow_redirects=False)

    class M:
        pass

    m = M()
    m.base, m.idp, m.c = base, idp, c
    yield m
    oidc_protocolo.olvidar_cache()


def _ida(m):
    r = m.c.get("/api/auth/oidc/inicio")
    assert r.status_code == 302, r.text
    return r, m.idp.autorizar(r.headers["location"])


def _vuelta(m, q, codigo="codigo-1", **extra):
    return m.c.get("/api/auth/oidc/vuelta", params={"code": codigo, "state": q["state"], **extra})


def _vale(r):
    destino = urlsplit(r.headers["location"])
    assert destino.path == "/entrar", r.headers["location"]
    return parse_qs(destino.query)["vale"][0]


def test_flujo_completo(mundo):
    r, q = _ida(mundo)
    assert r.headers["location"].startswith(f"{EMISOR}/autorizar?")
    assert q["response_type"] == "code" and q["client_id"] == CLIENT_ID
    assert q["code_challenge_method"] == "S256" and len(q["code_challenge"]) == 43
    assert q["redirect_uri"] == "https://panel.example.org:8443/api/auth/oidc/vuelta"
    assert "openid" in q["scope"].split()
    galleta = r.headers["set-cookie"]
    assert "HttpOnly" in galleta and "Secure" in galleta and "Path=/api/auth/oidc" in galleta
    # El verificador PKCE no sale del servidor.
    assert all(f["verificador"] not in r.headers["location"] for f in mundo.base.flujos.values())

    r = _vuelta(mundo, q)
    assert r.status_code == 302
    vale = _vale(r)
    assert vale not in str(mundo.base.vales)  # solo el hash
    peticion = mundo.idp.peticiones_token[0]
    assert b"code_verifier=" in peticion.content and SECRETO.encode() not in peticion.content

    s = mundo.c.post("/api/auth/vale", json={"vale": vale})
    assert s.status_code == 200, s.text
    datos = s.json()
    assert datos["user"]["username"] == "admin"
    assert decode_token(datos["token"])["totp"] is False
    assert mundo.base.sesiones
    assert "login_oidc" in mundo.base.acciones() and "login_vale" in mundo.base.acciones()
    # Un solo uso.
    assert mundo.c.post("/api/auth/vale", json={"vale": vale}).status_code == 401


def test_con_segundo_factor_se_pide_el_codigo(mundo):
    secreto = pyotp.random_base32()
    u = mundo.base.usuarios[1]
    u.update(totp_secret=secreto, totp_enabled=True)
    _, q = _ida(mundo)
    vale = _vale(_vuelta(mundo, q))
    assert mundo.c.post("/api/auth/vale", json={"vale": vale}).json() == {"requires_totp": True}
    r = mundo.c.post("/api/auth/vale", json={"vale": vale, "totp_code": "000000" if pyotp.TOTP(secreto).now() != "000000" else "111111"})
    assert r.status_code == 401 and u["failed_attempts"] == 1
    r = mundo.c.post("/api/auth/vale", json={"vale": vale, "totp_code": pyotp.TOTP(secreto).now()})
    assert r.status_code == 200
    assert decode_token(r.json()["token"])["totp"] is True


def test_otro_navegador_no_puede_terminar_el_flujo(mundo):
    _, q = _ida(mundo)
    mundo.c.cookies.clear()
    r = _vuelta(mundo, q)
    assert r.headers["location"] == "/login?entrada=estado"
    assert "login_oidc_fallido" in mundo.base.acciones()


def test_el_state_se_usa_una_vez(mundo):
    _, q = _ida(mundo)
    galleta = mundo.c.cookies.get("panel_oidc")
    _vale(_vuelta(mundo, q))
    mundo.c.cookies.set("panel_oidc", galleta, domain="panel.example.org", path="/api/auth/oidc")
    assert _vuelta(mundo, q).headers["location"] == "/login?entrada=estado"


def test_error_del_proveedor(mundo):
    _, q = _ida(mundo)
    assert _vuelta(mundo, q, error="access_denied").headers["location"] == "/login?entrada=rechazada"


@pytest.mark.parametrize("cambio", [
    lambda c: {**c, "aud": "otro-cliente"},
    lambda c: {**c, "iss": "https://otro.example.org"},
    lambda c: {**c, "exp": int(time.time()) - 3600, "iat": int(time.time()) - 7200},
    lambda c: {**c, "nonce": "otro-nonce-cualquiera"},
    lambda c: {k: v for k, v in c.items() if k != "nonce"},
    lambda c: {**c, "aud": [CLIENT_ID, "otro"], "azp": "otro"},
    lambda c: {**c, "iat": int(time.time()) + 3600, "exp": int(time.time()) + 7200},
])
def test_id_token_malo_se_rechaza(mundo, cambio):
    mundo.idp.manipular = cambio
    _, q = _ida(mundo)
    assert _vuelta(mundo, q).headers["location"] == "/login?entrada=token"
    assert not mundo.base.vales


def test_firma_de_otra_clave(mundo):
    otra = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    original = mundo.idp.firmar
    mundo.idp.firmar = lambda claims, **kw: original(claims, clave=otra)
    _, q = _ida(mundo)
    assert _vuelta(mundo, q).headers["location"] == "/login?entrada=token"


def test_none_y_hs256_no_se_aceptan(mundo):
    import jwt as pyjwt

    doc = asyncio.run(oidc_protocolo.descubrir(EMISOR))
    ahora = int(time.time())
    claims = {"iss": EMISOR, "aud": CLIENT_ID, "sub": "x", "iat": ahora, "exp": ahora + 60, "nonce": "n"}
    for token in (pyjwt.encode(claims, None, algorithm="none"), pyjwt.encode(claims, SECRETO * 2, algorithm="HS256")):
        with pytest.raises(oidc_protocolo.ErrorOidc) as e:
            asyncio.run(oidc_protocolo.validar_id_token(doc, CLIENT_ID, token, "n"))
        assert "algoritmo" in e.value.motivo


def test_sin_cuenta_no_se_crea(mundo):
    mundo.idp.claims_extra = {"preferred_username": "desconocida"}
    _, q = _ida(mundo)
    assert _vuelta(mundo, q).headers["location"] == "/login?entrada=sin_cuenta"
    assert [u["username"] for u in mundo.base.usuarios.values()] == ["admin"]


def test_crear_si_no_existe_con_el_rol_configurado(mundo):
    mundo.base.config.update(crear_si_no_existe=True, rol_nuevo="admin")
    mundo.idp.claims_extra = {"preferred_username": "nueva", "name": "Nueva <b>Persona</b>"}
    _, q = _ida(mundo)
    vale = _vale(_vuelta(mundo, q))
    nueva = next(u for u in mundo.base.usuarios.values() if u["username"] == "nueva")
    assert nueva["role"] == "admin" and "<" not in nueva["display_name"]
    assert "admin_create" in mundo.base.acciones()
    assert mundo.c.post("/api/auth/vale", json={"vale": vale}).json()["user"]["role"] == "admin"


def test_grupo_requerido(mundo):
    mundo.base.config.update(claim_grupos="groups", grupo_requerido="admins-correo")
    mundo.idp.claims_extra = {"preferred_username": "admin", "groups": ["contabilidad"]}
    _, q = _ida(mundo)
    assert "groups" in q["scope"].split()
    assert _vuelta(mundo, q).headers["location"] == "/login?entrada=grupo"
    mundo.idp.claims_extra = {"preferred_username": "admin", "groups": ["contabilidad", "admins-correo"]}
    _, q = _ida(mundo)
    _vale(_vuelta(mundo, q))


def test_lo_que_falta_en_el_id_token_se_pide_a_userinfo(mundo):
    mundo.base.config.update(claim_usuario="email")
    mundo.base.usuario("ana@example.org")
    mundo.idp.claims_extra = {}  # id_token mínimo, como Authelia 4.39
    mundo.idp.userinfo = {"email": "ana@example.org", "email_verified": True}
    _, q = _ida(mundo)
    vale = _vale(_vuelta(mundo, q))
    assert mundo.c.post("/api/auth/vale", json={"vale": vale}).json()["user"]["username"] == "ana@example.org"


def test_correo_sin_verificar_no_entra(mundo):
    mundo.base.config.update(claim_usuario="email")
    mundo.base.usuario("ana@example.org")
    mundo.idp.claims_extra = {"email": "ana@example.org", "email_verified": False}
    _, q = _ida(mundo)
    assert _vuelta(mundo, q).headers["location"] == "/login?entrada=sin_cuenta"


def test_cuenta_desactivada_o_bloqueada(mundo):
    mundo.base.usuarios[1]["active"] = False
    _, q = _ida(mundo)
    assert _vuelta(mundo, q).headers["location"] == "/login?entrada=desactivada_cuenta"


def test_desactivada_no_sale_hacia_el_proveedor(mundo):
    mundo.base.config["activado"] = False
    r = mundo.c.get("/api/auth/oidc/inicio")
    assert r.headers["location"] == "/login?entrada=desactivada"
    assert mundo.c.get("/api/auth/oidc/estado").json() == {"activado": False, "texto_boton": ""}


def test_estado_publico_con_el_texto_del_boton(mundo):
    mundo.base.config["texto_boton"] = "Entrar con Andes ID"
    assert mundo.c.get("/api/auth/oidc/estado").json() == {"activado": True, "texto_boton": "Entrar con Andes ID"}


def test_emisor_que_no_coincide_con_el_descubrimiento(mundo):
    mundo.idp.doc_extra = {"issuer": "https://otro.example.org"}
    assert mundo.c.get("/api/auth/oidc/inicio").headers["location"] == "/login?entrada=proveedor"


def test_endpoints_sin_https_se_rechazan(mundo):
    mundo.idp.doc_extra = {"token_endpoint": "http://id.example.org/token"}
    assert mundo.c.get("/api/auth/oidc/inicio").headers["location"] == "/login?entrada=proveedor"


def test_pkce_es_s256():
    verificador, desafio = oidc_protocolo.par_pkce()
    import base64
    import hashlib

    assert 43 <= len(verificador) <= 128
    assert desafio == base64.urlsafe_b64encode(hashlib.sha256(verificador.encode()).digest()).rstrip(b"=").decode()
