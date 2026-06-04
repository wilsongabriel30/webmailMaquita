from datetime import datetime, timedelta, timezone
import jwt as pyjwt
from app.config import JWT_SECRET, JWT_ALGORITHM, JWT_EXPIRE_MINUTES


def create_token(user_id: int, username: str, role: str) -> tuple[str, datetime]:
    expires = datetime.now(timezone.utc) + timedelta(minutes=JWT_EXPIRE_MINUTES)
    payload = {
        "sub": str(user_id),
        "username": username,
        "role": role,
        "exp": expires,
        "iat": datetime.now(timezone.utc),
    }
    token = pyjwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)
    return token, expires


def decode_token(token: str) -> dict | None:
    try:
        return pyjwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except pyjwt.ExpiredSignatureError:
        return None
    except pyjwt.InvalidTokenError:
        return None
