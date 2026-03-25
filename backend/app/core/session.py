"""Session management — credential handling for IMAP/SMTP/CalDAV/CardDAV."""
from fastapi import Request, HTTPException, status


async def get_user_password(request: Request, username: str) -> str:
    """Retrieve cached password from Redis for backend service auth."""
    redis = request.app.state.redis
    password = await redis.get(f"imap_pass:{username}")
    if not password:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session expired, please login again",
        )
    return password
