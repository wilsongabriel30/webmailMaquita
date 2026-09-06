import asyncio
import re
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel

from app.auth.cookies import dominio_cookie, poner_cookies_sesion, quitar_cookies_sesion
from app.auth.dependencies import get_current_user
from app.auth.dovecot_auth_service import authenticate
from app.auth.jwt import create_access_token, create_refresh_token, hash_refresh_token
from app.auth.sesiones import (
    av_actual,
    cerrar_sid,
    crear_sesion,
    prorrogar,
    revocar_todo,
    sesion_valida,
)
from app.auth.totp import is_totp_enabled, validate_totp_code
from app.config import get_settings
from app.core.session import encrypt_password


def _sanitize_username(username: str) -> str:
    """Sanitize username: strip control chars, validate email format."""
    username = re.sub(r"[\r\n\x00-\x08\x0b\x0c\x0e-\x1f\x7f\x85  ]", "", username)
    username = username.strip().lower()
    if not re.match(r"^[a-zA-Z0-9._%+-]+(@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})?$", username):
        raise HTTPException(status_code=422, detail="Nombre de usuario inválido")
    return username


async def _check_login_rate_limit(request: Request, username: str, redis):
    """Rate limit login attempts by IP and username."""
    ip = request.client.host if request.client else "unknown"

    # Per-IP: max 20 attempts in 5 minutes
    ip_key = f"login_rl:ip:{ip}"
    ip_count = await redis.incr(ip_key)
    if ip_count == 1:
        await redis.expire(ip_key, 300)
    if ip_count > 20:
        raise HTTPException(
            status_code=429,
            detail="Demasiados intentos desde esta IP. Intente en 5 minutos.",
        )

    # Per-user: max 10 attempts in 15 minutes
    user_key = f"login_rl:user:{username}"
    user_count = await redis.incr(user_key)
    if user_count == 1:
        await redis.expire(user_key, 900)
    if user_count > 10:
        raise HTTPException(
            status_code=429,
            detail="Cuenta bloqueada temporalmente por múltiples intentos fallidos. Intente en 15 minutos.",
        )


async def _clear_login_rate_limit(request: Request, username: str, redis):
    """Clear rate limit counters on successful login."""
    ip = request.client.host if request.client else "unknown"
    await redis.delete(f"login_rl:ip:{ip}")
    await redis.delete(f"login_rl:user:{username}")


router = APIRouter(prefix="/api/auth", tags=["auth"])


DEFAULT_BOOTSTRAP_PASSWORD = "Cambiar2026"


class LoginRequest(BaseModel):
    username: str
    password: str
    totp_code: str | None = None


class UserInfo(BaseModel):
    username: str
    is_admin: bool = False


@router.post("/login")
async def login(body: LoginRequest, request: Request, response: Response):
    start_time = asyncio.get_event_loop().time()
    settings = get_settings()

    # Normalize and sanitize
    username = _sanitize_username(body.username)
    if "@" not in username:
        username = f"{username}@{settings.mail_domain}"

    # Rate limiting
    redis = request.app.state.redis
    await _check_login_rate_limit(request, username, redis)

    ok = await authenticate(
        username, body.password, settings.imap_host, settings.imap_port
    )

    # Anti-timing: pad ALL responses (success AND failure) to uniform 2s
    # This prevents user enumeration via response time differences
    elapsed = asyncio.get_event_loop().time() - start_time
    if elapsed < 2.0:
        await asyncio.sleep(2.0 - elapsed)

    if not ok:
        # Si la cuenta fue CONTENIDA por seguridad (deteccion de envio masivo),
        # explicar el motivo en vez del generico "Credenciales incorrectas".
        try:
            _db = request.app.state.db_pool
            contenida = await _db.fetchrow(
                "SELECT 1 FROM mailbox m WHERE m.username=$1 AND m.active=false "
                "AND EXISTS (SELECT 1 FROM outbound_anomaly_events e "
                "WHERE e.username=$1 AND e.action='locked' "
                "AND e.created_at > now() - interval '30 days')",
                username,
            )
        except Exception:
            contenida = None
        if contenida:
            raise HTTPException(
                status_code=403,
                detail="Tu cuenta fue bloqueada por seguridad: se detecto un envio masivo inusual "
                "(posible acceso no autorizado). Por favor cambia tu contrasena y activa la "
                "verificacion en dos pasos (2FA). Contacta a soporte de Tecnologia para reactivarla.",
            )
        raise HTTPException(status_code=401, detail="Credenciales incorrectas")

    # 2FA check
    db = request.app.state.db_pool
    if await is_totp_enabled(db, username):
        if not body.totp_code:
            return {"requires_2fa": True, "username": username}
        if not await validate_totp_code(db, username, body.totp_code):
            raise HTTPException(status_code=401, detail="Código 2FA inválido")

    # Clear rate limit on success
    await _clear_login_rate_limit(request, username, redis)
    # Detección de login riesgoso (en segundo plano, no bloquea la respuesta)
    try:
        import asyncio as _asyncio

        from app.risky_login import detection as _rl

        _rip = (
            request.headers.get("x-real-ip")
            or (request.headers.get("x-forwarded-for", "").split(",")[0].strip())
            or (request.client.host if request.client else "")
        )
        _rua = request.headers.get("user-agent", "")
        _asyncio.create_task(_rl.analyze(db, redis, username, _rip, _rua))
    except Exception:
        pass

    # Sesión propia (sid) con la generación vigente (av). La contraseña IMAP queda
    # cifrada en Redis, por sesión: cerrar esta no toca las demás. (F-01)
    sesion = await crear_sesion(db, redis, request, username, body.password)
    poner_cookies_sesion(response, request, sesion)

    return {
        "message": "Login successful",
        "username": username,
        "must_change_password": body.password == DEFAULT_BOOTSTRAP_PASSWORD,
    }


@router.post("/refresh")
async def refresh(request: Request, response: Response):
    settings = get_settings()
    raw_token = request.cookies.get("refresh_token")
    if not raw_token:
        return {"refreshed": False, "reason": "no_token"}

    token_hash = hash_refresh_token(raw_token)
    db = request.app.state.db_pool
    redis = request.app.state.redis
    ahora = datetime.now(timezone.utc)

    row = await db.fetchrow(
        """SELECT id, username, expires_at, sid, session_kind, absolute_expires_at, auth_version
           FROM refresh_tokens
           WHERE token_hash = $1 AND is_revoked = false AND expires_at > NOW()""",
        token_hash,
    )
    # F-01/F-04: además del vencimiento propio, el refresh exige la generación vigente,
    # su sesión viva y que no haya pasado el vencimiento ABSOLUTO de la sesión.
    if row is not None:
        username = row["username"]
        sid = row["sid"]
        abs_exp = row["absolute_expires_at"]
        motivo = None
        if not sid or abs_exp is None:
            motivo = "sesion_anterior"
        elif abs_exp <= ahora:
            motivo = "vencimiento_absoluto"
        elif int(row["auth_version"]) != await av_actual(db, redis, username):
            motivo = "revocada"
        elif not await redis.exists(f"sess:{username}:{sid}"):
            motivo = "cerrada"
        if motivo:
            await db.execute(
                "UPDATE refresh_tokens SET is_revoked = true WHERE id = $1", row["id"]
            )
            row = None
    if row is None:
        quitar_cookies_sesion(response, request)
        return {"refreshed": False, "reason": "expired"}

    # Revoke old token (rotation)
    await db.execute(
        "UPDATE refresh_tokens SET is_revoked = true WHERE id = $1", row["id"]
    )

    kind = row["session_kind"] or "normal"
    av = int(row["auth_version"])

    # La sesión (sid) es la misma; solo se renuevan el access y el refresh.
    if kind == "normal":
        await prorrogar(redis, username, sid, abs_exp)
    access = create_access_token(username, sid=sid, av=av, kind=kind, abs_exp=abs_exp)
    new_refresh_raw, new_refresh_hash = create_refresh_token()
    # Nunca más allá del vencimiento absoluto: una impersonación de una hora muere a la
    # hora, se renueve lo que se renueve (F-04).
    expires_at = min(
        ahora + timedelta(days=settings.refresh_token_expire_days), abs_exp
    )

    await db.execute(
        """INSERT INTO refresh_tokens
             (username, token_hash, expires_at, user_agent, ip_address,
              sid, session_kind, absolute_expires_at, auth_version)
           VALUES ($1, $2, $3, $4, $5::inet, $6, $7, $8, $9)""",
        username,
        new_refresh_hash,
        expires_at,
        request.headers.get("user-agent", "")[:500],
        request.client.host if request.client else "0.0.0.0",
        sid,
        kind,
        abs_exp,
        av,
    )

    poner_cookies_sesion(
        response,
        request,
        {
            "access": access,
            "refresh_raw": new_refresh_raw,
            "refresh_expires_at": expires_at,
            "abs_exp": abs_exp,
        },
    )

    return {"message": "Token refreshed", "username": username}


@router.post("/logout")
async def logout(
    request: Request, response: Response, username: str = Depends(get_current_user)
):
    """Cierra ESTA sesión (su sid): las demás del usuario siguen."""
    await cerrar_sid(
        request.app.state.db_pool,
        request.app.state.redis,
        username,
        request.state.sid,
        "logout",
    )
    quitar_cookies_sesion(response, request)
    return {"message": "Logged out"}


@router.post("/logout-all")
async def logout_all(
    request: Request, response: Response, username: str = Depends(get_current_user)
):
    """Cierra TODAS las sesiones del usuario (sube la generación): ningún token viejo
    vuelve a valer, ni por refresh ni por re-login."""
    await revocar_todo(
        request.app.state.db_pool,
        request.app.state.redis,
        username,
        "cerrar_todas",
    )
    quitar_cookies_sesion(response, request)
    return {"message": "Todas las sesiones cerradas"}


@router.get("/me")
async def me(request: Request):
    """Return current user info. Never returns 401 - returns {user: null} instead."""
    token = request.cookies.get("access_token")
    if not token:
        return {"user": None}

    from app.auth.jwt import decode_access_token

    payload = decode_access_token(token)
    if payload is None:
        return {"user": None}

    valida = await sesion_valida(
        request.app.state.db_pool, request.app.state.redis, payload
    )
    if valida is None:
        return {"user": None}
    username, _sid = valida

    db = request.app.state.db_pool
    row = await db.fetchrow(
        "SELECT superadmin FROM admin WHERE username = $1 AND active = true", username
    )
    return {"user": {"username": username, "is_admin": row is not None}}


@router.get("/verify")
async def verify(request: Request, response: Response):
    """Validate JWT cookie and return 200 with X-Remote-User header.
    Used by Nginx auth_request for CalDAV proxy."""
    username = await get_current_user(request)
    response.headers["X-Remote-User"] = username
    return {"status": "ok", "username": username}


# ── Admin impersonation (master user) ──


class ImpersonateRequest(BaseModel):
    username: str
    admin_token: str


@router.post("/impersonate")
async def impersonate(body: ImpersonateRequest, request: Request, response: Response):
    """Allow admin panel to log in as any user using Dovecot master user.
    Requires a valid admin JWT from the admin panel as admin_token."""
    import jwt as pyjwt

    settings = get_settings()

    # Rate limit impersonate: max 5 attempts per 15 min per IP
    redis_imp = request.app.state.redis
    ip_imp = request.client.host if request.client else "unknown"
    imp_key = f"impersonate_rl:ip:{ip_imp}"
    imp_count = await redis_imp.incr(imp_key)
    if imp_count == 1:
        await redis_imp.expire(imp_key, 900)
    if imp_count > 5:
        raise HTTPException(429, "Demasiados intentos de impersonacion")

    # Vale de impersonación con ámbito (A-17): lo emite el panel para UN buzón, dura 5 min,
    # solo superadmin con sesión abierta con TOTP, y se consume una sola vez.
    try:
        payload = pyjwt.decode(
            body.admin_token, settings.admin_jwt_secret, algorithms=["HS256"]
        )
    except Exception:
        raise HTTPException(403, "Token de administrador inválido")
    if payload.get("purpose") != "impersonate":
        raise HTTPException(403, "El token no es un vale de impersonación")
    if payload.get("role") != "superadmin":
        raise HTTPException(403, "Solo un superadmin puede impersonar")
    if payload.get("totp") is not True:
        raise HTTPException(403, "Impersonar exige sesión con segundo factor (TOTP)")
    admin_user = payload.get("username", "unknown")

    # Normalize target username
    username = body.username.strip().lower()
    if "@" not in username:
        username = f"{username}@{settings.mail_domain}"
    objetivo = str(payload.get("target", "")).strip().lower()
    if "@" not in objetivo:
        objetivo = f"{objetivo}@{settings.mail_domain}"
    if objetivo != username:
        raise HTTPException(403, "El vale no corresponde a este buzón")

    # Nunca contra un superadministrador del correo.
    db_chk = request.app.state.db_pool
    if await db_chk.fetchval(
        "SELECT 1 FROM admin WHERE username = $1 AND superadmin = true", username
    ):
        raise HTTPException(403, "No se puede impersonar a un superadministrador")

    # Un solo uso: el jti queda quemado hasta que el vale venza.
    jti = str(payload.get("jti") or "")
    if not jti or not await redis_imp.set(
        f"imp_usado:{jti}", admin_user, ex=600, nx=True
    ):
        raise HTTPException(403, "Vale de impersonación ya usado o inválido")

    # Authenticate via Dovecot master user
    master_password = settings.master_password  # Securizado Fase 3
    ok = await authenticate(
        f"{username}*admin", master_password, settings.imap_host, settings.imap_port
    )
    if not ok:
        raise HTTPException(400, f"No se pudo acceder al buzon de {username}")

    # Sesión de impersonación: vence de forma ABSOLUTA a la hora (F-04), sin keep-alive,
    # y con la contraseña maestra cifrada solo para este sid.
    sesion = await crear_sesion(
        request.app.state.db_pool,
        request.app.state.redis,
        request,
        username,
        master_password,
        kind="impersonation",
        abs_exp=datetime.now(timezone.utc) + timedelta(hours=1),
        master="admin",
        user_agent=f"Admin-Impersonate:{admin_user}",
    )
    poner_cookies_sesion(response, request, sesion)

    return {"message": "Impersonation successful", "username": username}
