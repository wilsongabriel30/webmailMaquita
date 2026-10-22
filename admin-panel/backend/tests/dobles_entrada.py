"""Dobles para probar la entrada por OIDC y con vales sin base ni proveedor de verdad.

- BaseFalsa: las tablas que tocan entrada/ y admins_dominio/soporte.py, en memoria.
- ProveedorFalso: un proveedor OpenID Connect (descubrimiento, JWKS, token y userinfo) servido con
  httpx.MockTransport, con su propia clave RSA. Comprueba PKCE y la autenticación del cliente.
"""

import base64
import hashlib
import json
import time
from datetime import datetime, timezone
from urllib.parse import parse_qs, urlsplit

import httpx
import jwt
from cryptography.hazmat.primitives.asymmetric import rsa

EMISOR = "https://id.example.org"
CLIENT_ID = "panel-correo"
SECRETO = "secreto-del-cliente-de-pruebas"


def _ahora():
    return datetime.now(timezone.utc)


class BaseFalsa:
    def __init__(self):
        self.config = {
            "id": 1, "activado": False, "emisor": "", "client_id": "", "client_secret_cifrado": "",
            "claim_usuario": "preferred_username", "claim_grupos": "", "grupo_requerido": "",
            "crear_si_no_existe": False, "rol_nuevo": "viewer", "texto_boton": "Entrar con Identidad",
            "actualizado_por": "", "actualizado_en": _ahora(),
        }
        self.usuarios: dict[int, dict] = {}
        self.flujos: dict[str, dict] = {}
        self.vales: dict[str, dict] = {}
        self.auditoria: list[dict] = []
        self.sesiones: list[tuple] = []
        self.vales_soporte: list[tuple] = []
        self.dominios = {"uno.example"}

    def usuario(self, username, role="superadmin", totp_secret=None, active=True):
        nuevo = max(self.usuarios, default=0) + 1
        self.usuarios[nuevo] = {
            "id": nuevo, "username": username, "display_name": username.title(), "role": role,
            "active": active, "locked_until": None, "failed_attempts": 0, "password_hash": "x",
            "totp_secret": totp_secret, "totp_enabled": bool(totp_secret),
        }
        return self.usuarios[nuevo]

    def acciones(self):
        return [a["accion"] for a in self.auditoria]

    # --- asyncpg ---
    async def fetchrow(self, sql, *a):
        if "FROM admin_oidc_config" in sql:
            return dict(self.config)
        if "DELETE FROM admin_oidc_flujos" in sql:
            f = self.flujos.pop(a[0], None)
            return f if f and f["expires_at"] > _ahora() else None
        if "FROM admin_vales_entrada v JOIN admin_users" in sql:
            v = self.vales.get(a[0])
            if not v or v["usado_en"] or v["expires_at"] <= _ahora():
                return None
            u = self.usuarios[v["user_id"]]
            return {"vale_id": v["vale_hash"], "origen": v["origen"], "exige_totp": v["exige_totp"], **u}
        if "INSERT INTO admin_users" in sql:
            fila = self.usuario(a[0], role=a[3])
            fila["display_name"] = a[2]
            return fila
        raise AssertionError(f"consulta inesperada: {sql}")

    async def fetch(self, sql, *a):
        if "FROM admin_users WHERE lower(username)" in sql:
            return [u for u in self.usuarios.values() if u["username"].lower() == a[0].lower()][:2]
        if "FROM portal_empresa" in sql:
            return [{"host": "mail.uno.example", "dominio": "uno.example"}]
        raise AssertionError(f"consulta inesperada: {sql}")

    async def fetchval(self, sql, *a):
        if "UPDATE admin_vales_entrada" in sql:
            v = self.vales.get(a[0])
            if not v or v["usado_en"] or v["expires_at"] <= _ahora():
                return None
            v["usado_en"], v["usado_ip"] = _ahora(), a[1]
            return 1
        if "SELECT domain FROM domain" in sql:
            return a[0] if a[0] in self.dominios else None
        raise AssertionError(f"consulta inesperada: {sql}")

    async def execute(self, sql, *a):
        if "DELETE FROM admin_oidc_flujos WHERE expires_at" in sql:
            return "DELETE 0"
        if "INSERT INTO admin_oidc_flujos" in sql:
            self.flujos[a[0]] = {"nonce": a[1], "verificador": a[2], "redirect_uri": a[3], "expires_at": a[5]}
        elif "INSERT INTO admin_vales_entrada" in sql:
            self.vales[a[0]] = {"vale_hash": a[0], "user_id": a[1], "origen": a[2], "exige_totp": a[3],
                                "creado_por": a[4], "expires_at": a[5], "usado_en": None}
        elif "INSERT INTO admin_audit" in sql:
            if "details" in sql and len(a) == 6:
                detalles = json.loads(a[4]) if a[4] else None
                self.auditoria.append({"admin_id": a[0], "usuario": a[1], "accion": a[2], "objetivo": a[3],
                                       "detalles": detalles})
            elif "details" in sql:
                self.auditoria.append({"admin_id": a[0], "usuario": a[1], "accion": a[2], "detalles": json.loads(a[3])})
            else:
                self.auditoria.append({"admin_id": a[0], "usuario": a[1], "accion": a[2], "detalles": None})
        elif "UPDATE admin_users SET failed_attempts = 0" in sql:
            self.usuarios[a[0]]["failed_attempts"] = 0
        elif "UPDATE admin_users SET failed_attempts" in sql:
            self.usuarios[a[2]].update(failed_attempts=a[0], locked_until=a[1])
        elif "INSERT INTO admin_sessions" in sql:
            self.sesiones.append(a)
        elif "UPDATE admin_oidc_config" in sql:
            claves = ("activado", "emisor", "client_id", "client_secret_cifrado", "claim_usuario", "claim_grupos",
                      "grupo_requerido", "crear_si_no_existe", "rol_nuevo", "texto_boton", "actualizado_por")
            self.config.update(dict(zip(claves, a)))
        elif "INSERT INTO pd_vales_soporte" in sql:
            self.vales_soporte.append(a)
        else:
            raise AssertionError(f"orden inesperada: {sql}")
        return "OK"


def _b64(n: int) -> str:
    datos = n.to_bytes((n.bit_length() + 7) // 8, "big")
    return base64.urlsafe_b64encode(datos).rstrip(b"=").decode()


class ProveedorFalso:
    def __init__(self, emisor=EMISOR):
        self.emisor = emisor
        self.clave = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        numeros = self.clave.public_key().public_numbers()
        self.jwk = {"kty": "RSA", "kid": "k1", "use": "sig", "alg": "RS256", "n": _b64(numeros.n), "e": _b64(numeros.e)}
        self.pendientes: dict[str, dict] = {}  # código → {nonce, desafío, redirect_uri}
        self.claims_extra: dict = {"preferred_username": "admin", "email": "admin@example.org"}
        self.userinfo: dict = {}
        self.peticiones_token: list[httpx.Request] = []
        self.doc_extra: dict = {}
        self.manipular = None  # función(claims) -> claims, para probar tokens malos

    def doc(self):
        return {"issuer": self.emisor, "authorization_endpoint": f"{self.emisor}/autorizar",
                "token_endpoint": f"{self.emisor}/token", "jwks_uri": f"{self.emisor}/jwks",
                "userinfo_endpoint": f"{self.emisor}/userinfo",
                "code_challenge_methods_supported": ["S256"], **self.doc_extra}

    def autorizar(self, url_autorizacion: str, codigo: str = "codigo-1") -> dict:
        """Lo que haría el proveedor al aceptar a la persona: recuerda el nonce y el desafío."""
        q = {k: v[0] for k, v in parse_qs(urlsplit(url_autorizacion).query).items()}
        self.pendientes[codigo] = {"nonce": q["nonce"], "desafio": q["code_challenge"], "redirect_uri": q["redirect_uri"]}
        return q

    def firmar(self, claims: dict, clave=None, kid="k1", alg="RS256") -> str:
        return jwt.encode(claims, clave or self.clave, algorithm=alg, headers={"kid": kid})

    def id_token(self, nonce: str, **extra) -> str:
        ahora = int(time.time())
        claims = {"iss": self.emisor, "aud": CLIENT_ID, "sub": "u-123", "iat": ahora, "exp": ahora + 300,
                  "nonce": nonce, **self.claims_extra, **extra}
        if self.manipular:
            claims = self.manipular(claims)
        return self.firmar(claims)

    def transporte(self) -> httpx.MockTransport:
        def atender(peticion: httpx.Request) -> httpx.Response:
            ruta = peticion.url.path
            if ruta == "/.well-known/openid-configuration":
                return httpx.Response(200, json=self.doc())
            if ruta == "/jwks":
                return httpx.Response(200, json={"keys": [self.jwk]})
            if ruta == "/userinfo":
                if peticion.headers.get("Authorization") != "Bearer acceso-1":
                    return httpx.Response(401, json={})
                return httpx.Response(200, json={"sub": "u-123", **self.userinfo})
            if ruta == "/token" and peticion.method == "POST":
                self.peticiones_token.append(peticion)
                datos = {k: v[0] for k, v in parse_qs(peticion.content.decode()).items()}
                esperado = "Basic " + base64.b64encode(f"{CLIENT_ID}:{SECRETO}".encode()).decode()
                if peticion.headers.get("Authorization") != esperado:
                    return httpx.Response(401, json={"error": "invalid_client"})
                p = self.pendientes.pop(datos.get("code"), None)
                if not p or p["redirect_uri"] != datos.get("redirect_uri"):
                    return httpx.Response(400, json={"error": "invalid_grant"})
                desafio = base64.urlsafe_b64encode(hashlib.sha256(datos["code_verifier"].encode()).digest()).rstrip(b"=").decode()
                if desafio != p["desafio"]:
                    return httpx.Response(400, json={"error": "invalid_grant", "error_description": "PKCE"})
                return httpx.Response(200, json={"id_token": self.id_token(p["nonce"]), "access_token": "acceso-1",
                                                 "token_type": "Bearer"})
            return httpx.Response(404, json={})
        return httpx.MockTransport(atender)
