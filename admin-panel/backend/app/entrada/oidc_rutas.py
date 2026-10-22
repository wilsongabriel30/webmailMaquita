"""Entrada por OpenID Connect: ida al proveedor (/inicio) y vuelta con el código (/vuelta).

1. /inicio genera state, nonce y el par PKCE; guarda en admin_oidc_flujos el hash del state con el
   nonce y el verificador (10 minutos, un solo uso) y deja el state en una galleta HttpOnly limitada a
   /api/auth/oidc: la vuelta solo vale en el MISMO navegador que salió (sin entradas cruzadas).
2. /vuelta comprueba galleta y state, consume el flujo, canjea el código con el verificador, valida
   el id_token (oidc_protocolo) y busca la cuenta en admin_users por el claim configurado. NO crea
   administradores salvo que esté activado «crear si no existe».
3. Si todo cuadra, emite un vale de 120 s y manda a /entrar?vale=…, donde el frontend lo canjea por
   la sesión (vales.py). Si la cuenta tiene segundo factor, se pide ahí.

Toda vuelta queda en admin_audit: «login_oidc» (identidad verificada) o «login_oidc_fallido» (motivo).
"""

import hashlib
import hmac
import json
import logging
import re
import secrets
from datetime import datetime, timedelta, timezone

import bcrypt
from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse

from app.auth.sesion import ip_de
from app.entrada import cifrado, oidc_config, oidc_protocolo, vales
from app.entrada.oidc_protocolo import ErrorOidc

router = APIRouter(prefix="/api/auth/oidc", tags=["auth"])
log = logging.getLogger("admin.oidc")

GALLETA = "panel_oidc"
RUTA_GALLETA = "/api/auth/oidc"
MINUTOS_FLUJO = 10
SEGUNDOS_VALE = 120
RE_STATE = re.compile(r"[A-Za-z0-9_-]{32,128}")
RE_CODIGO = re.compile(r"[\x21-\x7e]{1,2048}")
RE_USUARIO = re.compile(r"[A-Za-z0-9][A-Za-z0-9._@+-]{0,254}")
_CONTROL = re.compile(r"[\x00-\x1f\x7f<>]")


def _huella(texto: str) -> str:
    return hashlib.sha256(texto.encode()).hexdigest()


def _a_la_entrada(codigo: str) -> RedirectResponse:
    r = RedirectResponse(f"/login?entrada={codigo}", status_code=302)
    r.delete_cookie(GALLETA, path=RUTA_GALLETA)
    return r


async def _auditar(db, request: Request, accion: str, user_id, usuario: str, detalles: dict) -> None:
    await db.execute(
        "INSERT INTO admin_audit (admin_id, admin_username, action, target, details, ip_address) "
        "VALUES ($1, $2, $3, $4, $5::jsonb, $6)",
        user_id, (usuario or "")[:255] or None, accion, (usuario or "")[:255], json.dumps(detalles), ip_de(request),
    )


@router.get("/inicio")
async def inicio(request: Request):
    db = request.app.state.db
    cfg = await oidc_config.leer(db)
    if not oidc_config.activa(cfg):
        return _a_la_entrada("desactivada")
    try:
        doc = await oidc_protocolo.descubrir(cfg["emisor"])
    except ErrorOidc as e:
        log.warning("OIDC: descubrimiento fallido: %s", e.motivo)
        return _a_la_entrada(e.codigo)
    state, nonce = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
    verificador, desafio = oidc_protocolo.par_pkce()
    vuelta = oidc_config.url_vuelta(request)
    await db.execute("DELETE FROM admin_oidc_flujos WHERE expires_at < NOW()")
    await db.execute(
        """INSERT INTO admin_oidc_flujos (state_hash, nonce, verificador, redirect_uri, ip, expires_at)
           VALUES ($1, $2, $3, $4, $5, $6)""",
        _huella(state), nonce, verificador, vuelta, ip_de(request),
        datetime.now(timezone.utc) + timedelta(minutes=MINUTOS_FLUJO),
    )
    destino = oidc_protocolo.url_autorizacion(doc, cfg["client_id"], vuelta, state, nonce, desafio,
                                             con_grupos=bool(cfg.get("claim_grupos")))
    r = RedirectResponse(destino, status_code=302)
    r.set_cookie(GALLETA, state, max_age=MINUTOS_FLUJO * 60, path=RUTA_GALLETA, secure=True, httponly=True,
                 samesite="lax")
    return r


async def _cuenta(db, request: Request, cfg: dict, usuario: str, claims: dict):
    """La fila de admin_users de esa persona, o la crea si la configuración lo permite. ErrorOidc si no."""
    filas = await db.fetch(
        "SELECT * FROM admin_users WHERE lower(username) = lower($1) ORDER BY id LIMIT 2", usuario)
    if len(filas) > 1:
        raise ErrorOidc("sin_cuenta", f"hay varias cuentas que coinciden con «{usuario}» (mayúsculas)")
    if filas:
        return filas[0]
    if not cfg.get("crear_si_no_existe"):
        raise ErrorOidc("sin_cuenta", f"no hay ningún administrador «{usuario}» y crear cuentas está apagado")
    if not RE_USUARIO.fullmatch(usuario):
        raise ErrorOidc("sin_cuenta", "el nombre de usuario que da el proveedor no es válido para el panel")
    nombre = _CONTROL.sub(" ", str(claims.get("name") or usuario)).strip()[:255]
    # Clave al azar que nadie conoce: la cuenta solo entra por el proveedor (o tras una recuperación).
    clave = bcrypt.hashpw(secrets.token_urlsafe(32).encode(), bcrypt.gensalt()).decode()
    fila = await db.fetchrow(
        """INSERT INTO admin_users (username, password_hash, display_name, role)
           VALUES ($1, $2, $3, $4) ON CONFLICT (username) DO NOTHING RETURNING *""",
        usuario, clave, nombre, cfg.get("rol_nuevo") or "viewer",
    )
    if not fila:
        raise ErrorOidc("sin_cuenta", "la cuenta se creó a la vez desde otro sitio; vuelva a intentarlo")
    await _auditar(db, request, "admin_create", fila["id"], usuario,
                   {"origen": "oidc", "rol": fila["role"], "emisor": cfg["emisor"]})
    return fila


async def _identidad(db, request: Request, code: str, state: str):
    """(cuenta, claims) tras comprobar todo; ErrorOidc en cuanto algo no cuadra."""
    galleta = request.cookies.get(GALLETA, "")
    if not RE_STATE.fullmatch(state or "") or not hmac.compare_digest(state, galleta or ""):
        raise ErrorOidc("estado", "state ausente o distinto del de la galleta (otro navegador o enlace viejo)")
    flujo = await db.fetchrow(
        "DELETE FROM admin_oidc_flujos WHERE state_hash = $1 AND expires_at > NOW() "
        "RETURNING nonce, verificador, redirect_uri", _huella(state))
    if not flujo:
        raise ErrorOidc("estado", "flujo desconocido, ya usado o caducado")
    if not RE_CODIGO.fullmatch(code or ""):
        raise ErrorOidc("rechazada", "el proveedor no devolvió el código")
    cfg = await oidc_config.leer(db)
    if not oidc_config.activa(cfg):
        raise ErrorOidc("desactivada", "la entrada por OIDC se desactivó durante el flujo")
    try:
        secreto = cifrado.descifrar(cfg["client_secret_cifrado"])
    except (cifrado.SinLlave, cifrado.InvalidToken):
        raise ErrorOidc("configuracion", "no se puede descifrar el client_secret (¿cambió la llave?)")
    doc = await oidc_protocolo.descubrir(cfg["emisor"])
    tokens = await oidc_protocolo.canjear_codigo(doc, cfg["client_id"], secreto, code, flujo["redirect_uri"],
                                                 flujo["verificador"])
    claims = await oidc_protocolo.validar_id_token(doc, cfg["client_id"], tokens["id_token"], flujo["nonce"])
    necesarias = [cfg["claim_usuario"]] + ([cfg["claim_grupos"]] if cfg.get("claim_grupos") else [])
    claims = await oidc_protocolo.completar_con_userinfo(doc, claims, tokens.get("access_token"), necesarias)
    usuario, grupos = oidc_protocolo.usuario_y_grupos(claims, cfg["claim_usuario"], cfg.get("claim_grupos", ""))
    if not usuario:
        raise ErrorOidc("sin_cuenta", f"el proveedor no envió el claim «{cfg['claim_usuario']}»")
    if cfg["claim_usuario"] == "email" and claims.get("email_verified") is False:
        raise ErrorOidc("sin_cuenta", "el correo no está verificado en el proveedor (email_verified)")
    if cfg.get("grupo_requerido") and cfg["grupo_requerido"] not in grupos:
        raise ErrorOidc("grupo", f"«{usuario}» no está en el grupo «{cfg['grupo_requerido']}»")
    cuenta = await _cuenta(db, request, cfg, usuario, claims)
    if not cuenta["active"]:
        raise ErrorOidc("desactivada_cuenta", f"la cuenta «{cuenta['username']}» está desactivada")
    if cuenta["locked_until"] and cuenta["locked_until"] > datetime.now(timezone.utc):
        raise ErrorOidc("bloqueada", f"la cuenta «{cuenta['username']}» está bloqueada por intentos fallidos")
    return cuenta, claims


@router.get("/vuelta")
async def vuelta(request: Request, code: str = "", state: str = "", error: str = ""):
    db = request.app.state.db
    try:
        if error:
            raise ErrorOidc("rechazada", f"el proveedor respondió «{_CONTROL.sub(' ', error)[:60]}»")
        cuenta, claims = await _identidad(db, request, code, state)
    except ErrorOidc as e:
        log.warning("OIDC: entrada rechazada: %s", e.motivo)
        await _auditar(db, request, "login_oidc_fallido", None, "", {"motivo": e.motivo[:300], "codigo": e.codigo})
        return _a_la_entrada(e.codigo)
    con_totp = bool("totp_enabled" in cuenta.keys() and cuenta["totp_enabled"])
    vale = await vales.emitir(db, cuenta["id"], "oidc", con_totp, SEGUNDOS_VALE,
                              f"oidc:{str(claims.get('sub'))[:200]}")
    await _auditar(db, request, "login_oidc", cuenta["id"], cuenta["username"],
                   {"sub": str(claims.get("sub"))[:255], "emisor": str(claims.get("iss"))[:255],
                    "segundo_factor_pendiente": con_totp})
    r = RedirectResponse(f"/entrar?vale={vale}", status_code=302)
    r.delete_cookie(GALLETA, path=RUTA_GALLETA)
    return r
