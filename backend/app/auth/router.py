import re
import asyncio
from fastapi import APIRouter, Request, Response, HTTPException, status, Depends
from pydantic import BaseModel
from datetime import datetime, timedelta, timezone

from app.config import get_settings
from app.auth.dovecot_auth_service import authenticate
from app.auth.jwt import create_access_token, create_refresh_token, hash_refresh_token
from app.auth.dependencies import get_current_user
from app.auth.totp import is_totp_enabled, validate_totp_code


def _sanitize_username(username: str) -> str:
    """Sanitize username: strip control chars, validate email format."""
    username = re.sub(r"[\r\n\x00-\x08\x0b\x0c\x0e-\x1f\x7f\x85\u2028\u2029]", "", username)
    username = username.strip().lower()
    if not re.match(r"^[a-zA-Z0-9._%+-]+(@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})?$", username):
        raise HTTPException(status_code=422, detail="Nombre de usuario inv\u00e1lido")
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

    ok = await authenticate(username, body.password, settings.imap_host, settings.imap_port)
    if not ok:
        # Pad response time to prevent user enumeration via timing
        elapsed = asyncio.get_event_loop().time() - start_time
        if elapsed < 7.0:
            await asyncio.sleep(7.0 - elapsed)
        return {"success": False, "error": "Credenciales incorrectas"}

    # 2FA check
    db = request.app.state.db_pool
    if await is_totp_enabled(db, username):
        if not body.totp_code:
            return {"requires_2fa": True, "username": username}
        if not await validate_totp_code(db, username, body.totp_code):
            return {"success": False, "error": "Código 2FA inválido"}

    # Clear rate limit on success
    await _clear_login_rate_limit(request, username, redis)

    # Cache password in Redis for IMAP/SMTP operations (encrypted, TTL matches session)
    await redis.set(f"imap_pass:{username}", body.password, ex=settings.access_token_expire_minutes * 60)

    # Create tokens
    access = create_access_token(username)
    refresh_raw, refresh_hash = create_refresh_token()

    # Store refresh token in DB
    db = request.app.state.db_pool
    expires_at = datetime.now(timezone.utc) + timedelta(days=settings.refresh_token_expire_days)
    await db.execute(
        """INSERT INTO refresh_tokens (username, token_hash, expires_at, user_agent, ip_address)
           VALUES ($1, $2, $3, $4, $5::inet)""",
        username,
        refresh_hash,
        expires_at,
        request.headers.get("user-agent", "")[:500],
        request.client.host if request.client else "0.0.0.0",
    )

    # Set cookies
    response.set_cookie(
        key="access_token",
        value=access,
        httponly=True,
        secure=True,
        samesite="strict",
        domain=settings.cookie_domain,
        max_age=settings.access_token_expire_minutes * 60,
        path="/",
    )
    response.set_cookie(
        key="refresh_token",
        value=refresh_raw,
        httponly=True,
        secure=True,
        samesite="strict",
        domain=settings.cookie_domain,
        max_age=settings.refresh_token_expire_days * 86400,
        path="/api/auth/refresh",
    )

    # Check admin status
    row = await db.fetchrow(
        "SELECT superadmin FROM admin WHERE username = $1 AND active = true", username
    )

    return {"message": "Login successful", "username": username}


@router.post("/refresh")
async def refresh(request: Request, response: Response):
    settings = get_settings()
    raw_token = request.cookies.get("refresh_token")
    if not raw_token:
        return {"refreshed": False, "reason": "no_token"}

    token_hash = hash_refresh_token(raw_token)
    db = request.app.state.db_pool

    row = await db.fetchrow(
        """SELECT id, username, expires_at FROM refresh_tokens
           WHERE token_hash = $1 AND is_revoked = false AND expires_at > NOW()""",
        token_hash,
    )
    if row is None:
        response.delete_cookie("access_token", domain=settings.cookie_domain, path="/")
        response.delete_cookie("refresh_token", domain=settings.cookie_domain, path="/api/auth/refresh")
        return {"refreshed": False, "reason": "expired"}

    # Revoke old token (rotation)
    await db.execute("UPDATE refresh_tokens SET is_revoked = true WHERE id = $1", row["id"])

    # Issue new tokens
    username = row["username"]

    # Extend password cache TTL
    redis = request.app.state.redis
    await redis.expire(f"imap_pass:{username}", settings.access_token_expire_minutes * 60)
    access = create_access_token(username)
    new_refresh_raw, new_refresh_hash = create_refresh_token()
    expires_at = datetime.now(timezone.utc) + timedelta(days=settings.refresh_token_expire_days)

    await db.execute(
        """INSERT INTO refresh_tokens (username, token_hash, expires_at, user_agent, ip_address)
           VALUES ($1, $2, $3, $4, $5::inet)""",
        username,
        new_refresh_hash,
        expires_at,
        request.headers.get("user-agent", "")[:500],
        request.client.host if request.client else "0.0.0.0",
    )

    response.set_cookie(
        key="access_token",
        value=access,
        httponly=True,
        secure=True,
        samesite="strict",
        domain=settings.cookie_domain,
        max_age=settings.access_token_expire_minutes * 60,
        path="/",
    )
    response.set_cookie(
        key="refresh_token",
        value=new_refresh_raw,
        httponly=True,
        secure=True,
        samesite="strict",
        domain=settings.cookie_domain,
        max_age=settings.refresh_token_expire_days * 86400,
        path="/api/auth/refresh",
    )

    return {"message": "Token refreshed", "username": username}


@router.post("/logout")
async def logout(request: Request, response: Response, username: str = Depends(get_current_user)):
    settings = get_settings()
    # Clean password cache
    redis = request.app.state.redis
    await redis.delete(f"imap_pass:{username}")

    # Revoke refresh token if present
    raw_token = request.cookies.get("refresh_token")
    if raw_token:
        db = request.app.state.db_pool
        token_hash = hash_refresh_token(raw_token)
        await db.execute(
            "UPDATE refresh_tokens SET is_revoked = true WHERE token_hash = $1",
            token_hash,
        )

    response.delete_cookie("access_token", domain=settings.cookie_domain, path="/")
    response.delete_cookie("refresh_token", domain=settings.cookie_domain, path="/api/auth/refresh")
    return {"message": "Logged out"}


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

    username = payload.get("sub")
    if not username:
        return {"user": None}

    # Check if session is still active (logout deletes imap_pass)
    redis = request.app.state.redis
    if not await redis.exists(f"imap_pass:{username}"):
        return {"user": None}

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

    # Verify the admin token is valid (from admin panel)
    try:
        payload = pyjwt.decode(body.admin_token, settings.admin_jwt_secret, algorithms=["HS256"])
        admin_role = payload.get("role", "")
        if admin_role not in ("superadmin", "admin"):
            raise HTTPException(403, "Se requiere rol de administrador")
        admin_user = payload.get("username", "unknown")
    except Exception:
        raise HTTPException(403, "Token de administrador invalido")

    # Normalize target username
    username = body.username.strip().lower()
    if "@" not in username:
        username = f"{username}@{settings.mail_domain}"

    # Authenticate via Dovecot master user
    master_password = settings.master_password  # Securizado Fase 3
    ok = await authenticate(f"{username}*admin", master_password, settings.imap_host, settings.imap_port)
    if not ok:
        raise HTTPException(400, f"No se pudo acceder al buzon de {username}")

    redis = request.app.state.redis

    # Cache the master password for IMAP operations (webmail needs it)
    # Store as user*admin format so IMAP works
    await redis.set(f"imap_pass:{username}", f"{master_password}", ex=3600)
    await redis.set(f"imap_master:{username}", "admin", ex=3600)

    # Create tokens
    access = create_access_token(username)
    refresh_raw, refresh_hash = create_refresh_token()

    db = request.app.state.db_pool
    expires_at = datetime.now(timezone.utc) + timedelta(hours=1)
    await db.execute(
        """INSERT INTO refresh_tokens (username, token_hash, expires_at, user_agent, ip_address)
           VALUES ($1, $2, $3, $4, $5::inet)""",
        username, refresh_hash, expires_at,
        f"Admin-Impersonate:{admin_user}",
        request.client.host if request.client else "0.0.0.0",
    )

    # Set cookies
    response.set_cookie(
        key="access_token", value=access,
        httponly=True, secure=True, samesite="strict",
        domain=settings.cookie_domain, max_age=3600, path="/",
    )
    response.set_cookie(
        key="refresh_token", value=refresh_raw,
        httponly=True, secure=True, samesite="strict",
        domain=settings.cookie_domain, max_age=3600, path="/",
    )

    return {"message": "Impersonation successful", "username": username}
