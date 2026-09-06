"""Password change router — uses doveadm for SHA512-CRYPT hashing."""

import imaplib
import logging
import re
import subprocess

logger = logging.getLogger(__name__)

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, Field

from app.auth.dependencies import get_current_user
from app.config import get_settings
from app.core.session import encrypt_password, get_user_password

# Contraseñas comunes prohibidas (top 50)
_COMMON_PASSWORDS = frozenset(
    {
        "password",
        "123456",
        "12345678",
        "1234567890",
        "qwerty",
        "abc123",
        "monkey",
        "master",
        "dragon",
        "111111",
        "baseball",
        "iloveyou",
        "trustno1",
        "sunshine",
        "letmein",
        "football",
        "shadow",
        "123123",
        "654321",
        "superman",
        "qazwsx",
        "michael",
        "password1",
        "password123",
        "welcome",
        "login",
        "admin",
        "princess",
        "mustang",
        "access",
        "hello",
        "charlie",
        "donald",
        "888888",
        "passw0rd",
        "whatever",
        "qwerty123",
        "000000",
        "12345",
        "123456789",
        "1234",
        "changeme",
    }
)


def validate_password_strength(password: str, username: str = "") -> str | None:
    """Validate password complexity. Returns error message or None if valid."""
    if len(password) < 10:
        return "La contrasena debe tener al menos 10 caracteres"
    if len(password) > 256:
        return "La contrasena no debe exceder 256 caracteres"
    if not re.search(r"[A-Z]", password):
        return "La contrasena debe incluir al menos una letra mayuscula"
    if not re.search(r"[a-z]", password):
        return "La contrasena debe incluir al menos una letra minuscula"
    if not re.search(r"[0-9]", password):
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
    if re.search(r"(.)\1{3,}", password):
        return "La contrasena no debe tener 4 o mas caracteres repetidos seguidos"
    # Check for sequential patterns (1234, abcd)
    for i in range(len(password) - 3):
        seq = password[i : i + 4]
        if (
            seq in "0123456789"
            or seq in "abcdefghijklmnopqrstuvwxyz"
            or seq in "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
        ):
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
        capture_output=True,
        text=True,
        timeout=10,
    )
    if result.returncode != 0:
        raise RuntimeError(f"doveadm pw failed: {result.stderr}")
    return result.stdout.strip()


_HOSTS_LOCALES = {"127.0.0.1", "::1", "localhost"}


def verify_imap(username: str, password: str) -> bool:
    """Comprueba las credenciales entrando por IMAP.

    Cifra con STARTTLS siempre que el servidor lo ofrezca. Antes se abria
    `IMAP4` a secas y se enviaba la contrasena tal cual: aqui no se nota porque
    el IMAP es 127.0.0.1 y Dovecot admite acceso en claro desde localhost
    (`login_trusted_networks`), pero en un despliegue con el IMAP en otra
    maquina la contrasena viajaria por la red sin cifrar, y si ese servidor
    exigiera TLS este paso fallaria y el cambio se reportaria como no aplicado
    aunque si se hubiera guardado.

    Si el servidor es remoto y no ofrece STARTTLS, NO se envia la contrasena:
    se devuelve False y queda anotado. En local se sigue adelante, para no
    romper una instalacion que hoy funciona.
    """
    settings = get_settings()
    host = (settings.imap_host or "").strip()
    es_local = host in _HOSTS_LOCALES
    conn = None
    try:
        conn = imaplib.IMAP4(host, settings.imap_port)
        capacidades = {
            c.decode() if isinstance(c, bytes) else c for c in conn.capabilities
        }
        if "STARTTLS" in capacidades:
            try:
                conn.starttls()
            except Exception as excepcion:
                if not es_local:
                    logger.error(
                        "IMAP %s: STARTTLS fallo (%s); no se envia la contrasena",
                        host,
                        excepcion,
                    )
                    return False
                logger.warning(
                    "IMAP local: STARTTLS fallo (%s); se continua sin cifrar", excepcion
                )
        elif not es_local:
            logger.error(
                "IMAP %s no ofrece STARTTLS; no se envia la contrasena en claro", host
            )
            return False
        conn.login(username, password)
        return True
    except Exception:
        return False
    finally:
        if conn is not None:
            try:
                conn.logout()
            except Exception:
                pass


@router.post("/change-password")
async def change_password(
    request: Request,
    response: Response,
    body: ChangePasswordRequest,
    username: str = Depends(get_current_user),
):
    """Change password: verify current → hash new → update DB → update Redis."""
    # 1. Verify current password SIEMPRE contra IMAP (la fuente de verdad).
    #    Antes se aceptaba si coincidia con el valor cacheado en Redis; ese valor
    #    lo puede escribir otro servicio que comparta el Redis (p. ej. una marca
    #    de sesion que no es una contrasena), y bastaba conocerlo para cambiar la
    #    clave real del buzon.
    await get_user_password(request, username)  # exige sesion viva (401 si expiro)
    if not verify_imap(username, body.current_password):
        raise HTTPException(status_code=401, detail="Contraseña actual incorrecta")

    if body.current_password == body.new_password:
        raise HTTPException(
            status_code=400, detail="La nueva contraseña debe ser diferente"
        )

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
        hashed,
        username,
    )
    if result == "UPDATE 0":
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    # 3b. GARANTIA anti-desincronizacion: confirmar que la NUEVA contrasena autentica de verdad
    #     contra Dovecot/BD antes de declarar exito. Si no, el cambio NO quedo aplicado.
    if not verify_imap(username, body.new_password):
        raise HTTPException(
            status_code=500,
            detail="La contraseña no se aplicó correctamente. Intenta nuevamente.",
        )

    # 4. F-01: la contraseña nueva invalida TODAS las sesiones (sube la generación y
    #    revoca los refresh) y el llamante recibe una sesión nueva en la misma respuesta:
    #    quien cambia la clave no se cae; cualquier otro (incluido un atacante con una
    #    cookie robada) sí.
    from app.auth.cookies import poner_cookies_sesion
    from app.auth.sesiones import crear_sesion, revocar_todo

    db = request.app.state.db_pool
    redis = request.app.state.redis
    await revocar_todo(db, redis, username, "cambio_de_contrasena")
    from app.auth.bootstrap import marcar_cambio_obligatorio

    await marcar_cambio_obligatorio(db, redis, username, False)  # H-01
    sesion = await crear_sesion(db, redis, request, username, body.new_password)
    poner_cookies_sesion(response, request, sesion)

    return {"status": "changed", "sesion_renovada": True}
