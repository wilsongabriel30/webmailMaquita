"""Contraseña inicial y cambio obligatorio (H-01, cuarta revisión).

Ya no existe una contraseña «bootstrap» conocida en el código. Cada buzón nuevo (o cada
reset del administrador) recibe una contraseña aleatoria de un solo uso y queda marcado con
`must_change_password` en `auth_estado`. Mientras la marca esté activa, el servidor solo
permite cambiar la contraseña y cerrar sesión (RUTAS_PERMITIDAS); el resto responde 403.
"""

import secrets
import string

RUTAS_PERMITIDAS = frozenset(
    {
        "/api/auth/change-password",
        "/api/auth/logout",
        "/api/auth/logout-all",
        "/api/auth/me",
        "/api/auth/verify",
        "/api/auth/refresh",
    }
)
_TTL_CACHE = 300


def clave_inicial_aleatoria() -> str:
    """Contraseña de un solo uso que cumple las reglas del cambio (10+, mayúscula,
    minúscula, número y símbolo) y se lee bien al dictarla: sin 0/O ni 1/l."""
    alfabeto = "ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnpqrstuvwxyz23456789"
    cuerpo = "".join(secrets.choice(alfabeto) for _ in range(9))
    partes = [
        secrets.choice("ABCDEFGHJKLMNPQRSTUVWXYZ"),
        secrets.choice("abcdefghijkmnpqrstuvwxyz"),
        secrets.choice("23456789"),
        secrets.choice("!@#$%&*"),  # los que acepta validate_password_strength
    ]
    caracteres = list(cuerpo + "".join(partes))
    secrets.SystemRandom().shuffle(caracteres)
    return "".join(caracteres)


async def debe_cambiar_clave(db, redis, username: str) -> bool:
    try:
        v = await redis.get(f"mcp:{username}")
        if v is not None:
            return v in ("1", b"1")
    except Exception:
        pass
    fila = await db.fetchval(
        "SELECT must_change_password FROM auth_estado WHERE username = $1", username
    )
    valor = bool(fila)
    try:
        await redis.set(f"mcp:{username}", "1" if valor else "0", ex=_TTL_CACHE)
    except Exception:
        pass
    return valor


async def marcar_cambio_obligatorio(db, redis, username: str, valor: bool) -> None:
    await db.execute(
        """INSERT INTO auth_estado (username, must_change_password) VALUES ($1, $2)
           ON CONFLICT (username) DO UPDATE
             SET must_change_password = EXCLUDED.must_change_password, updated_at = now()""",
        username,
        valor,
    )
    try:
        await redis.set(f"mcp:{username}", "1" if valor else "0", ex=_TTL_CACHE)
    except Exception:
        pass
