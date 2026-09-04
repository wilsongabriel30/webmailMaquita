"""Password change router — uses doveadm for SHA512-CRYPT hashing."""
import re
import subprocess
import imaplib

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field

from app.auth.dependencies import get_current_user
from app.core.session import get_user_password, encrypt_password
from app.config import get_settings


# Contraseñas comunes prohibidas (top 50)
_COMMON_PASSWORDS = frozenset({
    "password", "123456", "12345678", "1234567890", "qwerty", "abc123",
    "monkey", "master", "dragon", "111111", "baseball", "iloveyou",
    "trustno1", "sunshine", "letmein", "football", "shadow", "123123",
    "654321", "superman", "qazwsx", "michael", "password1", "password123",
    "welcome", "login", "admin", "princess", "mustang", "access",
    "hello", "charlie", "donald", "888888", "passw0rd", "whatever",
    "qwerty123", "000000", 
    "12345", "123456789", "1234", "changeme",
})


def validate_password_strength(password: str, username: str = "") -> str | None:
    """Validate password complexity. Returns error message or None if valid."""
    if len(password) < 10:
        return "La contrasena debe tener al menos 10 caracteres"
    if len(password) > 256:
        return "La contrasena no debe exceder 256 caracteres"
    if not re.search(r'[A-Z]', password):
        return "La contrasena debe incluir al menos una letra mayuscula"
    if not re.search(r'[a-z]', password):
        return "La contrasena debe incluir al menos una letra minuscula"
    if not re.search(r'[0-9]', password):
        return "La contrasena debe incluir al menos un numero"
    if not re.search(r"[!@#$%^&*(),.?:{}|<>_+\\-]", password):
        return "La contrasena debe incluir al menos un caracter especial (!@#$%&*.)"
    # Check common passwords (case-insensitive, also strip trailing digits/symbols)
    pw_lower = password.lower()
    pw_base = pw_lower.rstrip("0123456789!@#$%^&*()_+-=.,")
    if pw_lower in _COMMON_PASSWORDS or pw_base in _COMMON_PASSWORDS:
        return "Esa contrasena es demasiado comun. Elija una mas segura"
    # Check if password contains username
    if username:
        user_part = username.split("@")[0].lower()
        if len(user_part) > 3 and user_part in password.lower():
            return "La contrasena no debe contener su nombre de usuario"
    # Check for repeated characters (aaaa, 1111)
    if re.search(r'(.)\1{3,}', password):
        return "La contrasena no debe tener 4 o mas caracteres repetidos seguidos"
    # Check for sequential patterns (1234, abcd)
    for i in range(len(password) - 3):
        seq = password[i:i+4]
        if seq in "0123456789" or seq in "abcdefghijklmnopqrstuvwxyz" or seq in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
            return "La contrasena no debe contener secuencias obvias (1234, abcd)"
    return None


router = APIRouter(prefix="/api/auth", tags=["auth-password"])


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(..., min_length=1)
    # min_length=1: la fortaleza real (>=10, especial, etc.) la valida
    # validate_password_strength, que devuelve un mensaje claro en espanol.
    # Si aqui pusieramos min_length=10, Pydantic rechazaria antes con un 422
    # generico ("Solicitud invalida") en vez del mensaje especifico.
    new_password: str = Field(..., min_length=1, max_length=1024)


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
    # 1. Verify current password SIEMPRE contra IMAP (la fuente de verdad).
    #    Antes se aceptaba si coincidia con el valor cacheado en Redis; ese valor
    #    lo puede escribir otro servicio que comparta el Redis (p. ej. una marca
    #    de sesion que no es una contrasena), y bastaba conocerlo para cambiar la
    #    clave real del buzon.
    await get_user_password(request, username)   # exige sesion viva (401 si expiro)
    if not verify_imap(username, body.current_password):
        raise HTTPException(status_code=401, detail="Contraseña actual incorrecta")

    if body.current_password == body.new_password:
        raise HTTPException(status_code=400, detail="La nueva contraseña debe ser diferente")

    # 1b. Validate password strength
    strength_error = validate_password_strength(body.new_password, username)
    if strength_error:
        raise HTTPException(status_code=400, detail=strength_error)

    # 2. Hash with doveadm
    try:
        hashed = hash_password_doveadm(body.new_password)
    except Exception as e:
        raise HTTPException(status_code=500, detail="Error al cambiar la contraseña")

    # 3. Update DB
    db = request.app.state.db_pool
    result = await db.execute(
        "UPDATE mailbox SET password = $1 WHERE username = $2",
        hashed, username,
    )
    if result == "UPDATE 0":
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    # 3b. GARANTIA anti-desincronizacion: confirmar que la NUEVA contrasena autentica de verdad
    #     contra Dovecot/BD antes de declarar exito. Si no, el cambio NO quedo aplicado.
    if not verify_imap(username, body.new_password):
        raise HTTPException(status_code=500, detail="La contraseña no se aplicó correctamente. Intenta nuevamente.")

    # 4. Update Redis cache
    try:
        redis = request.app.state.redis
        settings = get_settings()
        await redis.set(
            f"imap_pass:{username}",
            encrypt_password(body.new_password),
            ex=settings.access_token_expire_minutes * 60,
        )
    except Exception:
        pass  # Non-fatal

    return {"status": "changed"}
