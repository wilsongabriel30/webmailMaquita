import hashlib
from datetime import datetime, timezone

import bcrypt
from fastapi import APIRouter, Request, HTTPException, Depends
import asyncpg

from app.auth.jwt import create_token
from app.auth.dependencies import get_current_admin, require_superadmin

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _hash_pw(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def _check_pw(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode(), hashed.encode())


def _db(request: Request) -> asyncpg.Pool:
    return request.app.state.db


def _ip(request: Request) -> str:
    return request.headers.get("X-Real-IP", request.client.host if request.client else "unknown")


@router.post("/login")
async def login(request: Request):
    data = await request.json()
    username = data.get("username", "").strip()
    password = data.get("password", "")
    db = _db(request)

    user = await db.fetchrow(
        "SELECT * FROM admin_users WHERE username = $1", username
    )

    if not user:
        raise HTTPException(401, "Credenciales inválidas")

    if user["locked_until"] and user["locked_until"] > datetime.now(timezone.utc):
        raise HTTPException(423, "Cuenta bloqueada temporalmente")

    if not user["active"]:
        raise HTTPException(403, "Cuenta desactivada")

    if not _check_pw(password, user["password_hash"]):
        attempts = (user["failed_attempts"] or 0) + 1
        locked = None
        if attempts >= 5:
            from datetime import timedelta
            locked = datetime.now(timezone.utc) + timedelta(minutes=15)

        await db.execute(
            "UPDATE admin_users SET failed_attempts = $1, locked_until = $2 WHERE id = $3",
            attempts, locked, user["id"],
        )
        raise HTTPException(401, "Credenciales inválidas")

    # 2FA (TOTP): si está habilitado, exigir código antes de emitir sesión.
    # ("totp_enabled" in keys: tolera BD sin la migración 2026-07-admin-totp.sql)
    if "totp_enabled" in user.keys() and user["totp_enabled"]:
        totp_code = str(data.get("totp_code", "")).strip()
        if not totp_code:
            return {"requires_totp": True}
        import pyotp
        if not pyotp.TOTP(user["totp_secret"]).verify(totp_code, valid_window=1):
            attempts = (user["failed_attempts"] or 0) + 1
            locked = None
            if attempts >= 5:
                from datetime import timedelta
                locked = datetime.now(timezone.utc) + timedelta(minutes=15)
            await db.execute(
                "UPDATE admin_users SET failed_attempts = $1, locked_until = $2 WHERE id = $3",
                attempts, locked, user["id"],
            )
            raise HTTPException(401, "Código de verificación inválido")

    # Reset failed attempts
    await db.execute(
        "UPDATE admin_users SET failed_attempts = 0, locked_until = NULL, last_login = NOW() WHERE id = $1",
        user["id"],
    )

    token, expires = create_token(user["id"], user["username"], user["role"])

    # Log session
    await db.execute(
        """INSERT INTO admin_sessions (user_id, token_hash, ip_address, user_agent, expires_at)
           VALUES ($1, $2, $3, $4, $5)""",
        user["id"],
        hashlib.sha256(token.encode()).hexdigest(),
        _ip(request),
        request.headers.get("User-Agent", ""),
        expires,
    )

    # Audit
    await db.execute(
        "INSERT INTO admin_audit (admin_id, admin_username, action, ip_address) VALUES ($1, $2, $3, $4)",
        user["id"], user["username"], "login", _ip(request),
    )

    return {
        "token": token,
        "expires": expires.isoformat(),
        "user": {
            "id": user["id"],
            "username": user["username"],
            "display_name": user["display_name"],
            "role": user["role"],
        },
    }


@router.get("/me")
async def get_me(admin: dict = Depends(get_current_admin)):
    return admin


@router.post("/change-password")
async def change_password(request: Request, admin: dict = Depends(get_current_admin)):
    data = await request.json()
    current = data.get("current_password", "")
    new_pw = data.get("new_password", "")

    if len(new_pw) < 8:
        raise HTTPException(400, "La contraseña debe tener al menos 8 caracteres")

    db = _db(request)
    user = await db.fetchrow("SELECT password_hash FROM admin_users WHERE id = $1", admin["id"])

    if not _check_pw(current, user["password_hash"]):
        raise HTTPException(401, "Contraseña actual incorrecta")

    await db.execute(
        "UPDATE admin_users SET password_hash = $1 WHERE id = $2",
        _hash_pw(new_pw), admin["id"],
    )
    return {"ok": True}


# ── Admin user management (superadmin only) ───────────────

@router.get("/admins")
async def list_admins(request: Request, admin: dict = Depends(require_superadmin)):
    db = _db(request)
    rows = await db.fetch(
        """SELECT id, username, display_name, role, active, created_at, last_login
           FROM admin_users ORDER BY created_at"""
    )
    return [dict(r) for r in rows]


@router.post("/admins")
async def create_admin(request: Request, admin: dict = Depends(require_superadmin)):
    data = await request.json()
    username = data.get("username", "").strip()
    password = data.get("password", "")
    display_name = data.get("display_name", username)
    role = data.get("role", "admin")

    if role not in ("superadmin", "admin", "viewer"):
        raise HTTPException(400, "Rol inválido. Opciones: superadmin, admin, viewer")
    if len(password) < 8:
        raise HTTPException(400, "Contraseña mínimo 8 caracteres")

    db = _db(request)
    try:
        row = await db.fetchrow(
            """INSERT INTO admin_users (username, password_hash, display_name, role)
               VALUES ($1, $2, $3, $4)
               RETURNING id, username, display_name, role, active, created_at""",
            username, _hash_pw(password), display_name, role,
        )
    except asyncpg.UniqueViolationError:
        raise HTTPException(409, "El usuario ya existe")

    await db.execute(
        "INSERT INTO admin_audit (admin_id, admin_username, action, target, ip_address) VALUES ($1, $2, $3, $4, $5)",
        admin["id"], admin["username"], "admin_create", username, _ip(request),
    )
    return dict(row)


@router.put("/admins/{user_id}")
async def update_admin(user_id: int, request: Request, admin: dict = Depends(require_superadmin)):
    data = await request.json()
    db = _db(request)

    current = await db.fetchrow("SELECT * FROM admin_users WHERE id = $1", user_id)
    if not current:
        raise HTTPException(404, "Admin no encontrado")

    new_hash = current["password_hash"]
    if data.get("password"):
        new_hash = _hash_pw(data["password"])

    await db.execute(
        """UPDATE admin_users SET
              display_name = $2, role = $3, active = $4, password_hash = $5
           WHERE id = $1""",
        user_id,
        data.get("display_name", current["display_name"]),
        data.get("role", current["role"]),
        data.get("active", current["active"]),
        new_hash,
    )

    await db.execute(
        "INSERT INTO admin_audit (admin_id, admin_username, action, target, ip_address) VALUES ($1, $2, $3, $4, $5)",
        admin["id"], admin["username"], "admin_update", current["username"], _ip(request),
    )
    return {"ok": True}


@router.delete("/admins/{user_id}")
async def delete_admin(user_id: int, request: Request, admin: dict = Depends(require_superadmin)):
    if user_id == admin["id"]:
        raise HTTPException(400, "No puedes eliminarte a ti mismo")

    db = _db(request)
    target = await db.fetchrow("SELECT username FROM admin_users WHERE id = $1", user_id)
    if not target:
        raise HTTPException(404, "Admin no encontrado")

    await db.execute("DELETE FROM admin_users WHERE id = $1", user_id)

    await db.execute(
        "INSERT INTO admin_audit (admin_id, admin_username, action, target, ip_address) VALUES ($1, $2, $3, $4, $5)",
        admin["id"], admin["username"], "admin_delete", target["username"], _ip(request),
    )
    return {"ok": True}


@router.post("/verify-password")
async def verify_password(request: Request, admin: dict = Depends(get_current_admin)):
    """Verify current admin password for sensitive operations."""
    db = _db(request)
    data = await request.json()
    password = data.get("password", "")
    if not password:
        raise HTTPException(400, "Contraseña requerida")
    row = await db.fetchrow("SELECT password_hash FROM admin_users WHERE id = $1", admin["id"])
    if not row or not _check_pw(password, row["password_hash"]):
        raise HTTPException(403, "Contraseña incorrecta")
    return {"ok": True, "verified": True}


# ── 2FA (TOTP) del panel ──────────────────────────────────

async def _require_own_password(db, request: Request, admin: dict):
    data = await request.json()
    row = await db.fetchrow("SELECT password_hash FROM admin_users WHERE id = $1", admin["id"])
    if not row or not _check_pw(data.get("password", ""), row["password_hash"]):
        raise HTTPException(403, "Contraseña incorrecta")
    return data


@router.get("/totp/status")
async def totp_status(request: Request, admin: dict = Depends(get_current_admin)):
    db = _db(request)
    row = await db.fetchrow("SELECT totp_enabled FROM admin_users WHERE id = $1", admin["id"])
    return {"enabled": bool(row and row["totp_enabled"])}


@router.post("/totp/setup")
async def totp_setup(request: Request, admin: dict = Depends(get_current_admin)):
    """Genera un secreto TOTP pendiente (requiere contraseña actual). Se activa con /totp/verify."""
    import base64
    import io

    import pyotp
    import qrcode
    import qrcode.image.svg

    db = _db(request)
    await _require_own_password(db, request, admin)

    secret = pyotp.random_base32()
    await db.execute(
        "UPDATE admin_users SET totp_secret = $1, totp_enabled = FALSE WHERE id = $2",
        secret, admin["id"],
    )
    uri = pyotp.TOTP(secret).provisioning_uri(name=admin["username"], issuer_name="Maquita Mail Admin")
    img = qrcode.make(uri, image_factory=qrcode.image.svg.SvgPathImage)
    buf = io.BytesIO()
    img.save(buf)
    qr_data_uri = "data:image/svg+xml;base64," + base64.b64encode(buf.getvalue()).decode()
    return {"secret": secret, "otpauth_uri": uri, "qr_svg": qr_data_uri}


@router.post("/totp/verify")
async def totp_verify(request: Request, admin: dict = Depends(get_current_admin)):
    """Confirma el código del autenticador y activa el 2FA."""
    import pyotp

    db = _db(request)
    data = await request.json()
    code = str(data.get("code", "")).strip()
    row = await db.fetchrow("SELECT totp_secret, totp_enabled FROM admin_users WHERE id = $1", admin["id"])
    if not row or not row["totp_secret"]:
        raise HTTPException(400, "Primero genere el secreto con /totp/setup")
    if not pyotp.TOTP(row["totp_secret"]).verify(code, valid_window=1):
        raise HTTPException(401, "Código de verificación inválido")

    await db.execute("UPDATE admin_users SET totp_enabled = TRUE WHERE id = $1", admin["id"])
    await db.execute(
        "INSERT INTO admin_audit (admin_id, admin_username, action, ip_address) VALUES ($1, $2, $3, $4)",
        admin["id"], admin["username"], "totp_enabled", _ip(request),
    )
    return {"ok": True, "enabled": True}


@router.post("/totp/disable")
async def totp_disable(request: Request, admin: dict = Depends(get_current_admin)):
    """Desactiva el 2FA (requiere contraseña actual)."""
    db = _db(request)
    await _require_own_password(db, request, admin)

    await db.execute(
        "UPDATE admin_users SET totp_secret = NULL, totp_enabled = FALSE WHERE id = $1",
        admin["id"],
    )
    await db.execute(
        "INSERT INTO admin_audit (admin_id, admin_username, action, ip_address) VALUES ($1, $2, $3, $4)",
        admin["id"], admin["username"], "totp_disabled", _ip(request),
    )
    return {"ok": True, "enabled": False}
