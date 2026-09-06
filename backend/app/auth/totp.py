"""
2FA / TOTP — Maquita Webmail
=============================
Setup, verify, disable TOTP (Google Authenticator compatible).
Backup codes for recovery.
"""

import base64
import io
import logging
import secrets

import pyotp
import qrcode
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from app.auth.dependencies import get_current_user
from app.branding.service import get_app_name
from app.core import cifrado

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/auth/totp", tags=["2fa"])

BACKUP_CODES_COUNT = 8
# Emisor que se ve en la aplicacion de autenticacion. Sale de la marca
# (branding_settings["app_name"]); esto solo actua si no esta configurada.
ISSUER_POR_DEFECTO = "Maquita Mail"


async def ensure_tables(db):
    # Tabla creada por migrations/init_tables.sql (Fase 3)
    # user_totp
    pass


def username_hint(row) -> str:
    try:
        return str(row["username"])
    except Exception:
        return "?"


def _secreto_totp(valor: str, usuario: str = "?") -> str:
    """Secreto TOTP descifrado. Uno sin cifrar (anterior a H-02) NO se acepta: hay que
    correr deploy/tools/recifrar-credenciales.py. Fallo cerrado: se devuelve un secreto
    aleatorio que no valida ningún código."""
    if cifrado.esta_cifrado(valor):
        try:
            return cifrado.descifrar(valor)
        except Exception:
            logger.error("TOTP_SECRETO_NO_DESCIFRA user=%s", usuario)
            return pyotp.random_base32()
    logger.error(
        "TOTP_SECRETO_SIN_CIFRAR user=%s (correr recifrar-credenciales.py)", usuario
    )
    return pyotp.random_base32()


def generate_backup_codes(n: int = BACKUP_CODES_COUNT) -> list[str]:
    return [secrets.token_hex(4).upper() for _ in range(n)]


class VerifyRequest(BaseModel):
    code: str


class DisableRequest(BaseModel):
    code: str


class SetupRequest(BaseModel):
    password: str


@router.post("/setup")
async def setup_totp(
    body: SetupRequest,
    request: Request,
    user: str = Depends(get_current_user),
):
    """Generate a new TOTP secret and return QR code as base64 PNG.
    Requires current password for re-authentication."""
    # Re-authenticate with password to prevent JWT-only attacks
    from app.auth.dovecot_auth_service import authenticate
    from app.config import get_settings

    settings = get_settings()
    ok = await authenticate(user, body.password, settings.imap_host, settings.imap_port)
    if not ok:
        raise HTTPException(status_code=401, detail="Contraseña incorrecta")

    db = request.app.state.db_pool
    await ensure_tables(db)

    row = await db.fetchrow("SELECT enabled FROM user_totp WHERE username = $1", user)
    if row and row["enabled"]:
        raise HTTPException(
            status_code=400, detail="2FA ya está activado. Desactívalo primero."
        )

    secret = pyotp.random_base32()
    backup_codes = generate_backup_codes()

    await db.execute(
        """
        INSERT INTO user_totp (username, secret, enabled, backup_codes)
        VALUES ($1, $2, FALSE, $3)
        ON CONFLICT (username)
        DO UPDATE SET secret = $2, enabled = FALSE, backup_codes = $3, verified_at = NULL
    """,
        user,
        cifrado.cifrar(secret),  # L-03: nunca en claro en la base
        backup_codes,
    )

    totp = pyotp.TOTP(secret)
    emisor = await get_app_name(request.app.state.db_pool)
    uri = totp.provisioning_uri(name=user, issuer_name=emisor)

    img = qrcode.make(uri)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    qr_b64 = base64.b64encode(buf.getvalue()).decode()

    return {
        "secret": secret,
        "qr_code": f"data:image/png;base64,{qr_b64}",
        "backup_codes": backup_codes,
        "uri": uri,
    }


@router.post("/verify")
async def verify_totp(
    body: VerifyRequest,
    request: Request,
    user: str = Depends(get_current_user),
):
    """Verify a TOTP code to complete 2FA setup."""
    db = request.app.state.db_pool
    await ensure_tables(db)

    row = await db.fetchrow(
        "SELECT username, secret, enabled FROM user_totp WHERE username = $1", user
    )
    if not row:
        raise HTTPException(status_code=404, detail="Configura 2FA primero")
    if row["enabled"]:
        raise HTTPException(status_code=400, detail="2FA ya esta verificado")

    totp = pyotp.TOTP(_secreto_totp(row["secret"], username_hint(row)))
    if not totp.verify(body.code, valid_window=1):
        raise HTTPException(
            status_code=400, detail="Código inválido. Intenta de nuevo."
        )

    await db.execute(
        "UPDATE user_totp SET enabled = TRUE, verified_at = NOW() WHERE username = $1",
        user,
    )

    return {"status": "enabled", "message": "2FA activado correctamente"}


@router.post("/disable")
async def disable_totp(
    body: DisableRequest,
    request: Request,
    user: str = Depends(get_current_user),
):
    """Disable 2FA. Requires current TOTP code or backup code."""
    db = request.app.state.db_pool
    await ensure_tables(db)

    row = await db.fetchrow(
        "SELECT username, secret, enabled, backup_codes FROM user_totp WHERE username = $1",
        user,
    )
    if not row or not row["enabled"]:
        raise HTTPException(status_code=400, detail="2FA no esta activado")

    totp = pyotp.TOTP(_secreto_totp(row["secret"], username_hint(row)))
    code = body.code.strip().upper()
    backup_codes = row["backup_codes"] or []

    if not totp.verify(code, valid_window=1) and code not in backup_codes:
        raise HTTPException(status_code=400, detail="Código inválido")

    if code in backup_codes:
        backup_codes.remove(code)
        await db.execute(
            "UPDATE user_totp SET backup_codes = $1 WHERE username = $2",
            backup_codes,
            user,
        )

    await db.execute("DELETE FROM user_totp WHERE username = $1", user)

    return {"status": "disabled", "message": "2FA desactivado"}


@router.get("/status")
async def totp_status(
    request: Request,
    user: str = Depends(get_current_user),
):
    """Check if 2FA is enabled for the current user."""
    db = request.app.state.db_pool
    await ensure_tables(db)

    row = await db.fetchrow(
        "SELECT enabled, verified_at, array_length(backup_codes, 1) as codes_left FROM user_totp WHERE username = $1",
        user,
    )

    if not row or not row["enabled"]:
        return {"enabled": False}

    return {
        "enabled": True,
        "verified_at": row["verified_at"].isoformat() if row["verified_at"] else None,
        "backup_codes_remaining": row["codes_left"] or 0,
    }


async def validate_totp_code(db, username: str, code: str) -> bool:
    """Validate TOTP code during login. Returns True if valid or 2FA not enabled."""
    row = await db.fetchrow(
        "SELECT username, secret, enabled, backup_codes FROM user_totp WHERE username = $1",
        username,
    )
    if not row or not row["enabled"]:
        return True

    totp = pyotp.TOTP(_secreto_totp(row["secret"], username_hint(row)))
    clean_code = code.strip().upper()
    backup_codes = row["backup_codes"] or []

    if totp.verify(clean_code, valid_window=1):
        return True

    if clean_code in backup_codes:
        backup_codes.remove(clean_code)
        await db.execute(
            "UPDATE user_totp SET backup_codes = $1 WHERE username = $2",
            backup_codes,
            username,
        )
        return True

    return False


async def is_totp_enabled(db, username: str) -> bool:
    """Check if user has 2FA enabled."""
    row = await db.fetchrow(
        "SELECT enabled FROM user_totp WHERE username = $1", username
    )
    return bool(row and row["enabled"])
