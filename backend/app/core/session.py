"""Session management — credential handling for IMAP/SMTP/CalDAV/CardDAV."""

import base64
import hashlib

from cryptography.fernet import Fernet
from fastapi import HTTPException, Request, status


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
    """Retrieve and DECRYPT cached password from Redis.

    OBLIGATORIO usar esta función en todos los routers que necesiten la contraseña IMAP/SMTP.
    Las contraseñas en Redis (key imap_pass:{user}) están cifradas con Fernet.
    Leer directo con redis.get() devuelve el token cifrado, NO la contraseña real.

    Lanza HTTP 401 si la sesión expiró (no hay key en Redis).
    """
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
        # No descifra: no se devuelve jamás el valor crudo. Se cierra la sesión
        # y el usuario vuelve a entrar.
        import logging

        logging.getLogger(__name__).error(
            "Credencial cacheada de %s no descifra; sesión invalidada [CREDENCIAL_NO_DESCIFRA]",
            username,
        )
        await redis.delete(f"imap_pass:{username}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session expired",
        )


async def get_imap_login_user(request: Request, username: str) -> str:
    """Get the IMAP login username. For master user sessions, returns user*admin.

    BLINDAJE: Si existe imap_master:{user} pero la contraseña almacenada NO es
    la master password, significa que el usuario hizo login normal después de una
    impersonación y la key quedó stale. En ese caso se limpia automáticamente
    para evitar que IMAP intente user*admin con la contraseña personal (→ 500).
    """
    redis = request.app.state.redis
    master_user = await redis.get(f"imap_master:{username}")
    if master_user:
        # Verificar que la contraseña almacenada sea realmente la master password
        from app.config import get_settings

        settings = get_settings()
        raw_pass = await redis.get(f"imap_pass:{username}")
        if raw_pass:
            try:
                stored_pass = decrypt_password(raw_pass)
                if stored_pass != settings.master_password:
                    # KEY STALE: la contraseña no es la master → limpiar y usar login normal
                    import logging

                    logging.getLogger(__name__).warning(
                        f"imap_master stale para {username}: password no es master. Limpiando."
                    )
                    await redis.delete(f"imap_master:{username}")
                    return username
            except Exception:
                # No descifra: la sesión no vale. Se limpia y se obliga a reautenticar.
                await redis.delete(f"imap_pass:{username}")
                await redis.delete(f"imap_master:{username}")
                return username
        return f"{username}*{master_user}"
    return username
