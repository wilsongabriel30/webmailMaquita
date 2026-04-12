"""Session management — credential handling for IMAP/SMTP/CalDAV/CardDAV."""
from fastapi import Request, HTTPException, status
from cryptography.fernet import Fernet
import base64, hashlib


def _get_fernet():
    from app.config import get_settings
    settings = get_settings()
    # Derive a 32-byte key from the secret_key
    key = hashlib.sha256(settings.secret_key.encode()).digest()
    return Fernet(base64.urlsafe_b64encode(key))


def encrypt_password(password: str) -> str:
    return _get_fernet().encrypt(password.encode()).decode()


def decrypt_password(token: str) -> str:
    return _get_fernet().decrypt(token.encode()).decode()


async def get_user_password(request: Request, username: str) -> str:
    """Retrieve cached password from Redis for backend service auth.
    For master user sessions, returns the master password."""
    redis = request.app.state.redis
    raw = await redis.get(f"imap_pass:{username}")
    if not raw:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session expired",
        )
    try:
        return decrypt_password(raw)
    except Exception:
        return raw  # fallback for unencrypted legacy values


async def get_imap_login_user(request: Request, username: str) -> str:
    """Get the IMAP login username. For master user sessions, returns user*admin."""
    redis = request.app.state.redis
    master_user = await redis.get(f"imap_master:{username}")
    if master_user:
        return f"{username}*{master_user}"
    return username
