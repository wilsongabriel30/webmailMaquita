"""SSO/OIDC con Keycloak — flujo add-on. El login local queda intacto (break-glass).

Tras autenticar en Keycloak, se monta la sesión del buzón vía impersonación
Dovecot master (no se requiere la contraseña del usuario). Solo entran buzones
activos existentes (match por email).
"""

import secrets
import urllib.parse
from datetime import datetime, timedelta, timezone

import httpx
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import RedirectResponse

from app.auth.cookies import dominio_cookie
from app.auth.dovecot_auth_service import authenticate
from app.auth.jwt import create_access_token, create_refresh_token
from app.config import get_settings
from app.core.session import encrypt_password

router = APIRouter(prefix="/api/auth", tags=["oidc"])


def _endpoints(s):
    base = s.kc_base.rstrip("/") + f"/realms/{s.kc_realm}/protocol/openid-connect"
    return base + "/auth", base + "/token", base + "/userinfo"


def _redirect_uri(s):
    return s.public_base_url.rstrip("/") + "/api/auth/oidc/callback"


@router.get("/oidc/enabled")
async def oidc_enabled():
    return {"enabled": bool(get_settings().kc_oidc_enabled)}


@router.get("/oidc/login")
async def oidc_login(request: Request):
    s = get_settings()
    if not s.kc_oidc_enabled:
        raise HTTPException(404, "SSO no habilitado")
    authz, _, _ = _endpoints(s)
    state = secrets.token_urlsafe(24)
    await request.app.state.redis.set(f"oidc_state:{state}", "1", ex=600)
    q = urllib.parse.urlencode(
        {
            "client_id": s.kc_client_id,
            "response_type": "code",
            "scope": "openid email profile",
            "redirect_uri": _redirect_uri(s),
            "state": state,
        }
    )
    return RedirectResponse(f"{authz}?{q}", status_code=302)


@router.get("/oidc/callback")
async def oidc_callback(request: Request, code: str = "", state: str = ""):
    s = get_settings()
    if not s.kc_oidc_enabled:
        raise HTTPException(404, "SSO no habilitado")
    redis = request.app.state.redis
    if not code or not state or not await redis.get(f"oidc_state:{state}"):
        return RedirectResponse("/webmail/?sso_error=state", status_code=302)
    await redis.delete(f"oidc_state:{state}")

    _, token_url, userinfo_url = _endpoints(s)
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            tok = await client.post(
                token_url,
                data={
                    "grant_type": "authorization_code",
                    "code": code,
                    "redirect_uri": _redirect_uri(s),
                    "client_id": s.kc_client_id,
                    "client_secret": s.kc_client_secret,
                },
            )
            tok.raise_for_status()
            access_token = tok.json().get("access_token", "")
            ui = await client.get(
                userinfo_url, headers={"Authorization": f"Bearer {access_token}"}
            )
            ui.raise_for_status()
            info = ui.json()
    except Exception:
        return RedirectResponse("/webmail/?sso_error=token", status_code=302)

    email = (info.get("email") or info.get("preferred_username") or "").strip().lower()
    if email and "@" not in email:
        email = f"{email}@{s.mail_domain}"
    if not email:
        return RedirectResponse("/webmail/?sso_error=nouser", status_code=302)

    db = request.app.state.db_pool
    row = await db.fetchrow(
        "SELECT 1 FROM mailbox WHERE username=$1 AND active=true", email
    )
    if not row:
        return RedirectResponse("/webmail/?sso_error=nomailbox", status_code=302)

    # Sesión vía impersonación master (mismo mecanismo que /impersonate)
    ok = await authenticate(
        f"{email}*admin", s.master_password, s.imap_host, s.imap_port
    )
    if not ok:
        return RedirectResponse("/webmail/?sso_error=imap", status_code=302)

    # Sesión federada (kind=oidc) con la contraseña maestra cifrada por sid y vencimiento
    # absoluto de una hora, sin prórroga (F-01/F-04).
    from app.auth.cookies import poner_cookies_sesion
    from app.auth.sesiones import crear_sesion

    sesion = await crear_sesion(
        db,
        redis,
        request,
        email,
        s.master_password,
        kind="oidc",
        abs_exp=datetime.now(timezone.utc) + timedelta(hours=1),
        master="admin",
        user_agent="SSO-OIDC",
    )
    resp = RedirectResponse("/webmail/", status_code=302)
    poner_cookies_sesion(resp, request, sesion)
    return resp
