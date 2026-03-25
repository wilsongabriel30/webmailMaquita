"""Password change router — uses doveadm for SHA512-CRYPT hashing."""
import subprocess
import imaplib

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field

from app.auth.dependencies import get_current_user
from app.core.session import get_user_password
from app.core.config import get_settings

router = APIRouter(prefix="/api/auth", tags=["auth-password"])


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(..., min_length=1)
    new_password: str = Field(..., min_length=8, max_length=256)


def hash_password_doveadm(password: str) -> str:
    """Generate SHA512-CRYPT hash using doveadm pw."""
    result = subprocess.run(
        ["doveadm", "pw", "-s", "SHA512-CRYPT", "-p", password],
        capture_output=True, text=True, timeout=10,
    )
    if result.returncode != 0:
        raise RuntimeError(f"doveadm pw failed: {result.stderr}")
    return result.stdout.strip()


def verify_imap(username: str, password: str) -> bool:
    """Verify credentials via IMAP login."""
    settings = get_settings()
    try:
        conn = imaplib.IMAP4(settings.imap_host, settings.imap_port)
        conn.login(username, password)
        conn.logout()
        return True
    except Exception:
        return False


@router.post("/change-password")
async def change_password(
    request: Request,
    body: ChangePasswordRequest,
    username: str = Depends(get_current_user),
):
    """Change password: verify current → hash new → update DB → update Redis."""
    # 1. Verify current password
    stored = await get_user_password(request, username)
    if body.current_password != stored:
        if not verify_imap(username, body.current_password):
            raise HTTPException(status_code=401, detail="Contrasena actual incorrecta")

    if body.current_password == body.new_password:
        raise HTTPException(status_code=400, detail="La nueva contrasena debe ser diferente")

    # 2. Hash with doveadm
    try:
        hashed = hash_password_doveadm(body.new_password)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al generar hash: {e}")

    # 3. Update DB
    db = request.app.state.db_pool
    result = await db.execute(
        "UPDATE mailbox SET password = $1 WHERE username = $2",
        hashed, username,
    )
    if result == "UPDATE 0":
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    # 4. Update Redis cache
    try:
        redis = request.app.state.redis
        settings = get_settings()
        await redis.set(
            f"imap_pass:{username}",
            body.new_password,
            ex=settings.access_token_expire_minutes * 60,
        )
    except Exception:
        pass  # Non-fatal

    return {"status": "changed"}
