"""Segundo factor obligatorio para cuentas privilegiadas (N-7, re-auditoría del 04/09).

Los buzones `admin@` y `postmaster@` (o los que diga `TOTP_OBLIGATORIO`) tienen que tener
TOTP activo para usar el webmail. Mientras no lo tengan, la sesión solo sirve para activarlo o
salir (RUTAS_PERMITIDAS_2FA); el resto responde 403 con `must_setup_2fa`, y la pantalla de
entrada lleva a la activación. Mismo mecanismo que el cambio de contraseña obligatorio (H-01).

Nadie puede enrolar el segundo factor por otra persona (hace falta su aplicación): la política
garantiza que la próxima vez que esa cuenta entre, lo primero que hace es activarlo.
"""

_TTL_CACHE = 60

RUTAS_PERMITIDAS_2FA = frozenset(
    {
        "/api/auth/totp/setup",
        "/api/auth/totp/verify",
        "/api/auth/totp/status",
        "/api/auth/change-password",
        "/api/auth/logout",
        "/api/auth/logout-all",
        "/api/auth/me",
        "/api/auth/verify",
        "/api/auth/refresh",
    }
)


def cuenta_privilegiada(username: str, politica: str) -> bool:
    """`politica`: lista separada por comas de partes locales (`admin`) o direcciones completas
    (`soporte@example.org`). Se compara en minúsculas."""
    u = (username or "").strip().lower()
    if "@" not in u:
        return False
    local = u.split("@", 1)[0]
    for regla in (politica or "").split(","):
        r = regla.strip().lower()
        if not r:
            continue
        if ("@" in r and r == u) or ("@" not in r and r == local):
            return True
    return False


async def debe_activar_2fa(
    db, redis, username: str, politica: str | None = None
) -> bool:
    """True si la cuenta es privilegiada y aún no tiene TOTP. Cacheado 60 s en Redis."""
    if politica is None:
        from app.config import get_settings

        politica = get_settings().totp_obligatorio
    if not cuenta_privilegiada(username, politica):
        return False
    clave = f"mfa_oblig:{username}"
    try:
        v = await redis.get(clave)
        if v is not None:
            return v == "1"
    except Exception:
        pass
    from app.auth.totp import is_totp_enabled

    falta = not await is_totp_enabled(db, username)
    try:
        await redis.set(clave, "1" if falta else "0", ex=_TTL_CACHE)
    except Exception:
        pass
    return falta


async def olvidar(redis, username: str) -> None:
    """Tras activar o desactivar TOTP: que la política se reevalúe en el acto."""
    try:
        await redis.delete(f"mfa_oblig:{username}")
    except Exception:
        pass
