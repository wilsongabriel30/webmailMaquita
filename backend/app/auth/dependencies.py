from fastapi import Request, HTTPException, status
from app.auth.jwt import decode_access_token


async def get_current_user(request: Request) -> str:
    """Extract and validate the current user from the access_token cookie."""
    token = request.cookies.get("access_token")
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")

    payload = decode_access_token(token)
    if payload is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")

    username = payload.get("sub")
    if not username:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token payload")

    # Check if session is still active (logout deletes imap_pass from Redis)
    redis = request.app.state.redis
    session_active = await redis.exists(f"imap_pass:{username}")
    # Extend password TTL on every authenticated request (keep-alive)
    if session_active:
        from app.config import get_settings
        _s = get_settings()
        await redis.expire(f"imap_pass:{username}", _s.access_token_expire_minutes * 60)
    if not session_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session expired")

    return username


async def require_admin(request: Request) -> str:
    """Verify user is authenticated AND is an admin (superadmin or domain admin)."""
    username = await get_current_user(request)
    db = request.app.state.db_pool

    row = await db.fetchrow(
        "SELECT superadmin FROM admin WHERE username = $1 AND active = true",
        username,
    )
    if row is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")

    return username
