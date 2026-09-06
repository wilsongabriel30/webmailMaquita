import hashlib
import secrets
from datetime import datetime, timedelta, timezone

import jwt

from app.config import get_settings


def create_access_token(
    username: str,
    *,
    sid: str,
    av: int,
    kind: str = "normal",
    abs_exp: datetime | None = None,
) -> str:
    """Access JWT de una sesión concreta (F-01): lleva `sid`, `av`, `kind` y `abs_exp`.
    El vencimiento nunca supera `abs_exp` (F-04)."""
    settings = get_settings()
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=settings.access_token_expire_minutes
    )
    if abs_exp is not None and abs_exp < expire:
        expire = abs_exp
    payload = {
        "sub": username,
        "sid": sid,
        "av": int(av),
        "kind": kind,
        "abs_exp": (
            int(abs_exp.timestamp()) if abs_exp is not None else int(expire.timestamp())
        ),
        "exp": expire,
        "type": "access",
    }
    return jwt.encode(payload, settings.secret_key, algorithm="HS256")


def create_refresh_token() -> tuple[str, str]:
    """Returns (raw_token, token_hash) — store hash in DB, send raw to client."""
    raw = secrets.token_urlsafe(48)
    token_hash = hashlib.sha256(raw.encode()).hexdigest()
    return raw, token_hash


def decode_access_token(token: str) -> dict | None:
    settings = get_settings()
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=["HS256"])
        if payload.get("type") != "access":
            return None
        # Las cuentas EXTERNAS del Drive comparten cookie y secreto pero llevan
        # `aud`/`ambito` propios: no son sesiones de buzón y aquí no valen.
        # (PyJWT ya rechaza un `aud` no solicitado; esto lo hace explícito.)
        if payload.get("aud") or payload.get("ambito"):
            return None
        return payload
    except jwt.PyJWTError:
        return None


def hash_refresh_token(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()
