"""Tokens del panel de administración.

- Token de SESIÓN: lo emite /api/auth/login; solo vale mientras exista una fila viva en
  admin_sessions (ver dependencies.get_current_admin). Lleva `totp` = si la sesión se abrió
  con segundo factor.
- Vale de IMPERSONACIÓN: de un solo uso, 5 minutos, para UN buzón concreto; lo consume el
  backend del correo en /api/auth/impersonate. No sirve para llamar al panel.
"""
import secrets
from datetime import datetime, timedelta, timezone

import jwt as pyjwt

from app.config import JWT_SECRET, JWT_ALGORITHM, JWT_EXPIRE_MINUTES

IMPERSONACION_MINUTOS = 5


def create_token(user_id: int, username: str, role: str, totp: bool = False) -> tuple[str, datetime]:
    ahora = datetime.now(timezone.utc)
    expires = ahora + timedelta(minutes=JWT_EXPIRE_MINUTES)
    payload = {
        "sub": str(user_id),
        "username": username,
        "role": role,
        "totp": bool(totp),
        "jti": secrets.token_urlsafe(16),
        "exp": expires,
        "iat": ahora,
    }
    return pyjwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM), expires


def create_impersonation_token(user_id: int, username: str, role: str, totp: bool, target: str) -> str:
    """Vale con ámbito: `purpose` y `target` los exige el backend del correo."""
    ahora = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "username": username,
        "role": role,
        "totp": bool(totp),
        "purpose": "impersonate",
        "target": target,
        "jti": secrets.token_urlsafe(16),
        "exp": ahora + timedelta(minutes=IMPERSONACION_MINUTOS),
        "iat": ahora,
    }
    return pyjwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_token(token: str) -> dict | None:
    try:
        return pyjwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except pyjwt.ExpiredSignatureError:
        return None
    except pyjwt.InvalidTokenError:
        return None
