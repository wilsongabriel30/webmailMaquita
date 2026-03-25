from fastapi import APIRouter, Request, Response, HTTPException, status, Depends
from pydantic import BaseModel
from datetime import datetime, timedelta, timezone

from app.config import get_settings
from app.auth.dovecot_auth_service import authenticate
from app.auth.jwt import create_access_token, create_refresh_token, hash_refresh_token
from app.auth.dependencies import get_current_user

router = APIRouter(prefix="/api/auth", tags=["auth"])


class LoginRequest(BaseModel):
    username: str
    password: str


class UserInfo(BaseModel):
    username: str
    is_admin: bool = False


@router.post("/login")
async def login(body: LoginRequest, request: Request, response: Response):
    settings = get_settings()

    # Normalize: accept "user" or "user@domain"
    username = body.username
    if "@" not in username:
        username = f"{username}@{settings.mail_domain}"

    ok = await authenticate(username, body.password, settings.imap_host, settings.imap_port)
    if not ok:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    # Cache password in Redis for IMAP/SMTP operations (encrypted, TTL matches session)
    redis = request.app.state.redis
    await redis.set(f"imap_pass:{username}", body.password, ex=settings.access_token_expire_minutes * 60)

    # Create tokens
    access = create_access_token(username)
    refresh_raw, refresh_hash = create_refresh_token()

    # Store refresh token in DB
    db = request.app.state.db_pool
    expires_at = datetime.now(timezone.utc) + timedelta(days=settings.refresh_token_expire_days)
    await db.execute(
        """INSERT INTO webmail.refresh_tokens (username, token_hash, expires_at, user_agent, ip_address)
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

    return {"message": "Login successful", "username": username, "is_admin": row is not None}


@router.post("/refresh")
async def refresh(request: Request, response: Response):
    settings = get_settings()
    raw_token = request.cookies.get("refresh_token")
    if not raw_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="No refresh token")

    token_hash = hash_refresh_token(raw_token)
    db = request.app.state.db_pool

    row = await db.fetchrow(
        """SELECT id, username, expires_at FROM webmail.refresh_tokens
           WHERE token_hash = $1 AND is_revoked = false AND expires_at > NOW()""",
        token_hash,
    )
    if row is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired refresh token")

    # Revoke old token (rotation)
    await db.execute("UPDATE webmail.refresh_tokens SET is_revoked = true WHERE id = $1", row["id"])

    # Extend password cache TTL
    redis = request.app.state.redis
    await redis.expire(f"imap_pass:{username}", settings.access_token_expire_minutes * 60)

    # Issue new tokens
    username = row["username"]
    access = create_access_token(username)
    new_refresh_raw, new_refresh_hash = create_refresh_token()
    expires_at = datetime.now(timezone.utc) + timedelta(days=settings.refresh_token_expire_days)

    await db.execute(
        """INSERT INTO webmail.refresh_tokens (username, token_hash, expires_at, user_agent, ip_address)
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
            "UPDATE webmail.refresh_tokens SET is_revoked = true WHERE token_hash = $1",
            token_hash,
        )

    response.delete_cookie("access_token", domain=settings.cookie_domain, path="/")
    response.delete_cookie("refresh_token", domain=settings.cookie_domain, path="/api/auth/refresh")
    return {"message": "Logged out"}


@router.get("/me")
async def me(request: Request, username: str = Depends(get_current_user)):
    db = request.app.state.db_pool
    row = await db.fetchrow(
        "SELECT superadmin FROM admin WHERE username = $1 AND active = true", username
    )
    return UserInfo(username=username, is_admin=row is not None)
