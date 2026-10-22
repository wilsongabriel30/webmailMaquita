"""OpenID Connect sin base de datos: descubrimiento, PKCE, canje del código y validación del id_token.

Flujo «authorization code» con PKCE (S256), state y nonce. El id_token se valida entero: firma con
las claves publicadas por el proveedor (JWKS), emisor (iss), destinatario (aud y azp), caducidad
(exp, iat) y nonce. Solo firmas asimétricas: «none» y HS256 se rechazan siempre.

Todo lo que habla con el proveedor va por HTTPS, sin seguir redirecciones y con tope de tamaño.
`transporte` existe para las pruebas (httpx.MockTransport); en producción es None.
"""

import base64
import hashlib
import hmac
import re
import secrets
import time
from urllib.parse import urlencode, urlsplit

import httpx
import jwt

ALGORITMOS = ("RS256", "RS384", "RS512", "PS256", "PS384", "PS512", "ES256", "ES384", "ES512", "EdDSA")
CACHE_SEGUNDOS = 600
MARGEN_SEGUNDOS = 60  # desfase de relojes admitido en exp/iat
MAX_RESPUESTA = 1024 * 1024
RE_EMISOR = re.compile(r"https://[A-Za-z0-9.-]+(:[0-9]{1,5})?(/[A-Za-z0-9._~%!$&'()*+,;=:@-]+)*/?")

transporte: httpx.AsyncBaseTransport | None = None
_cache: dict[str, tuple[float, object]] = {}


class ErrorOidc(Exception):
    """`codigo` va a la pantalla de entrada (/login?entrada=codigo); `motivo` solo a la auditoría."""

    def __init__(self, codigo: str, motivo: str = ""):
        super().__init__(motivo or codigo)
        self.codigo, self.motivo = codigo, motivo or codigo


def olvidar_cache() -> None:
    _cache.clear()


def emisor_valido(emisor: str) -> bool:
    return bool(RE_EMISOR.fullmatch(emisor or ""))


def _https(url) -> bool:
    partes = urlsplit(url) if isinstance(url, str) else None
    return bool(partes and partes.scheme == "https" and partes.hostname)


def _cliente() -> httpx.AsyncClient:
    return httpx.AsyncClient(timeout=10.0, follow_redirects=False, transport=transporte,
                             headers={"Accept": "application/json", "User-Agent": "panel-correo-oidc"})


def _leer_json(respuesta: httpx.Response, que: str) -> dict:
    if respuesta.status_code != 200:
        raise ErrorOidc("proveedor", f"{que}: el proveedor respondió {respuesta.status_code}")
    if len(respuesta.content) > MAX_RESPUESTA:
        raise ErrorOidc("proveedor", f"{que}: respuesta demasiado grande")
    try:
        datos = respuesta.json()
    except ValueError:
        raise ErrorOidc("proveedor", f"{que}: la respuesta no es JSON")
    if not isinstance(datos, dict):
        raise ErrorOidc("proveedor", f"{que}: respuesta inesperada")
    return datos


async def _obtener(url: str, que: str, cabeceras: dict | None = None) -> dict:
    if not _https(url):
        raise ErrorOidc("proveedor", f"{que}: la dirección no es HTTPS")
    try:
        async with _cliente() as c:
            return _leer_json(await c.get(url, headers=cabeceras), que)
    except httpx.HTTPError as e:
        raise ErrorOidc("proveedor", f"{que}: {type(e).__name__}")


async def descubrir(emisor: str, forzar: bool = False) -> dict:
    """El documento /.well-known/openid-configuration del emisor, comprobado y en caché 10 minutos."""
    if not emisor_valido(emisor):
        raise ErrorOidc("configuracion", "el emisor debe ser una dirección https://")
    clave = "descubrimiento:" + emisor
    guardado = _cache.get(clave)
    if guardado and not forzar and time.monotonic() - guardado[0] < CACHE_SEGUNDOS:
        return guardado[1]
    doc = await _obtener(emisor.rstrip("/") + "/.well-known/openid-configuration", "descubrimiento")
    if str(doc.get("issuer", "")).rstrip("/") != emisor.rstrip("/"):
        raise ErrorOidc("proveedor", "el emisor que publica el proveedor no coincide con el configurado")
    for campo in ("authorization_endpoint", "token_endpoint", "jwks_uri"):
        if not _https(doc.get(campo)):
            raise ErrorOidc("proveedor", f"descubrimiento: falta {campo} o no es HTTPS")
    if doc.get("userinfo_endpoint") and not _https(doc["userinfo_endpoint"]):
        raise ErrorOidc("proveedor", "descubrimiento: userinfo_endpoint no es HTTPS")
    _cache[clave] = (time.monotonic(), doc)
    return doc


async def claves(jwks_uri: str, forzar: bool = False) -> list[dict]:
    clave = "jwks:" + jwks_uri
    guardado = _cache.get(clave)
    if guardado and not forzar and time.monotonic() - guardado[0] < CACHE_SEGUNDOS:
        return guardado[1]
    lista = (await _obtener(jwks_uri, "claves")).get("keys")
    if not isinstance(lista, list) or not lista:
        raise ErrorOidc("proveedor", "el proveedor no publica claves (JWKS vacío)")
    lista = [k for k in lista if isinstance(k, dict)]
    _cache[clave] = (time.monotonic(), lista)
    return lista


def _b64(datos: bytes) -> str:
    return base64.urlsafe_b64encode(datos).rstrip(b"=").decode()


def par_pkce() -> tuple[str, str]:
    """(verificador, desafío S256). El verificador (64 caracteres) no sale nunca del servidor."""
    verificador = secrets.token_urlsafe(48)
    return verificador, _b64(hashlib.sha256(verificador.encode()).digest())


def url_autorizacion(doc: dict, client_id: str, redirect_uri: str, state: str, nonce: str, desafio: str,
                     con_grupos: bool = False) -> str:
    alcance = "openid profile email" + (" groups" if con_grupos else "")
    parametros = urlencode({
        "response_type": "code", "client_id": client_id, "redirect_uri": redirect_uri, "scope": alcance,
        "state": state, "nonce": nonce, "code_challenge": desafio, "code_challenge_method": "S256",
    })
    destino = doc["authorization_endpoint"]
    return destino + ("&" if "?" in destino else "?") + parametros


async def canjear_codigo(doc: dict, client_id: str, secreto: str, codigo: str, redirect_uri: str,
                         verificador: str) -> dict:
    """Cambia el código por los tokens en el token_endpoint (client_secret_basic o, si no, _post)."""
    metodos = doc.get("token_endpoint_auth_methods_supported") or ["client_secret_basic"]
    datos = {"grant_type": "authorization_code", "code": codigo, "redirect_uri": redirect_uri,
             "code_verifier": verificador}
    autenticacion = None
    if "client_secret_basic" in metodos:
        # RFC 6749 §2.3.1: identificador y secreto van codificados como formulario antes del Basic.
        autenticacion = httpx.BasicAuth(urlencode({"a": client_id})[2:], urlencode({"a": secreto})[2:])
    elif "client_secret_post" in metodos:
        datos.update(client_id=client_id, client_secret=secreto)
    else:
        raise ErrorOidc("configuracion", "el proveedor no admite client_secret_basic ni client_secret_post")
    try:
        async with _cliente() as c:
            r = await c.post(doc["token_endpoint"], data=datos, auth=autenticacion)
    except httpx.HTTPError as e:
        raise ErrorOidc("proveedor", f"canje del código: {type(e).__name__}")
    tokens = _leer_json(r, "canje del código")
    if not isinstance(tokens.get("id_token"), str):
        raise ErrorOidc("token", "el proveedor no devolvió id_token")
    return tokens


def _elegir_clave(lista: list[dict], kid, alg: str) -> dict | None:
    candidatas = [k for k in lista if k.get("use", "sig") == "sig" and (not k.get("alg") or k.get("alg") == alg)]
    if kid is not None:
        candidatas = [k for k in candidatas if k.get("kid") == kid]
    return candidatas[0] if len(candidatas) == 1 or (kid is not None and candidatas) else None


async def validar_id_token(doc: dict, client_id: str, id_token: str, nonce: str) -> dict:
    """Las afirmaciones (claims) del id_token, solo si es auténtico y es para nosotros. Si no, ErrorOidc."""
    try:
        cabecera = jwt.get_unverified_header(id_token)
    except jwt.PyJWTError:
        raise ErrorOidc("token", "id_token mal formado")
    alg = cabecera.get("alg")
    if alg not in ALGORITMOS:
        raise ErrorOidc("token", f"algoritmo de firma no admitido: {str(alg)[:20]}")
    kid = cabecera.get("kid")
    clave = _elegir_clave(await claves(doc["jwks_uri"]), kid, alg)
    if clave is None:  # el proveedor pudo rotar sus claves: se piden otra vez, una sola
        clave = _elegir_clave(await claves(doc["jwks_uri"], forzar=True), kid, alg)
    if clave is None:
        raise ErrorOidc("token", "ninguna clave publicada coincide con la firma del id_token")
    try:
        publica = jwt.PyJWK(clave, algorithm=alg).key
        claims = jwt.decode(id_token, publica, algorithms=[alg], audience=client_id, issuer=doc["issuer"],
                            leeway=MARGEN_SEGUNDOS, options={"require": ["exp", "iat", "iss", "aud", "sub"]})
    except jwt.ExpiredSignatureError:
        raise ErrorOidc("token", "id_token caducado")
    except jwt.InvalidAudienceError:
        raise ErrorOidc("token", "el id_token no es para este panel (aud)")
    except jwt.InvalidIssuerError:
        raise ErrorOidc("token", "el id_token es de otro emisor (iss)")
    except (jwt.PyJWTError, ValueError, TypeError) as e:
        raise ErrorOidc("token", f"id_token no válido: {type(e).__name__}")
    if claims.get("iat", 0) > time.time() + MARGEN_SEGUNDOS:
        raise ErrorOidc("token", "id_token emitido en el futuro (iat)")
    audiencia = claims.get("aud")
    if isinstance(audiencia, list) and len(audiencia) > 1 and claims.get("azp") != client_id:
        raise ErrorOidc("token", "id_token con varios destinatarios y azp ajeno")
    if not isinstance(claims.get("nonce"), str) or not hmac.compare_digest(claims["nonce"], nonce):
        raise ErrorOidc("token", "el nonce no coincide")
    return claims


async def completar_con_userinfo(doc: dict, claims: dict, access_token, necesarias: list[str]) -> dict:
    """Si al id_token le faltan afirmaciones (Authelia 4.39 solo da las mínimas), se piden a userinfo.

    El sub de userinfo tiene que ser el del id_token; lo del id_token manda sobre lo de userinfo."""
    if all(c in claims for c in necesarias) or not doc.get("userinfo_endpoint") or not isinstance(access_token, str):
        return claims
    info = await _obtener(doc["userinfo_endpoint"], "userinfo", {"Authorization": f"Bearer {access_token}"})
    if info.get("sub") != claims.get("sub"):
        raise ErrorOidc("token", "userinfo es de otra persona (sub)")
    return {**info, **claims}


def usuario_y_grupos(claims: dict, claim_usuario: str, claim_grupos: str) -> tuple[str, list[str]]:
    usuario = claims.get(claim_usuario)
    usuario = usuario.strip() if isinstance(usuario, str) else ""
    grupos = claims.get(claim_grupos) if claim_grupos else []
    if isinstance(grupos, str):
        grupos = [grupos]
    grupos = [g for g in grupos if isinstance(g, str)] if isinstance(grupos, list) else []
    return usuario, grupos
