"""Session management — credential handling for IMAP/SMTP/CalDAV/CardDAV."""
from fastapi import Request, HTTPException, status


async def get_user_password(request: Request, username: str) -> str:
    """Retrieve cached password from Redis for backend service auth.
    For master user sessions, returns the master password."""
    redis = request.app.state.redis
    password = await redis.get(f"imap_pass:{username}")
    if not password:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session expired",
        )
    return password


async def get_imap_login_user(request: Request, username: str) -> str:
    """Get the IMAP login username. For master user sessions, returns user*admin."""
    redis = request.app.state.redis
    master_user = await redis.get(f"imap_master:{username}")
    if master_user:
        return f"{username}*{master_user}"
    return username
