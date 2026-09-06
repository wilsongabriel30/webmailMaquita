"""Códigos de respaldo de 2FA (H-03, cuarta revisión; cierra F-09 de la tercera).

Antes: 8 códigos de 32 bits (`token_hex(4)`) guardados EN CLARO en `user_totp.backup_codes`
y consumidos con leer-quitar-escribir (dos peticiones simultáneas podían usar el mismo).
Ahora:

- 128 bits por código (`token_hex(16)`), mostrados en grupos de 4 para poder copiarlos.
- Un código por fila en `user_totp_backup_codes`, guardado como HMAC-SHA256 con sal propia
  (la entropía del código hace innecesario un KDF lento; la sal evita tablas precalculadas).
- Consumo atómico: `UPDATE ... WHERE id = $1 AND used_at IS NULL RETURNING id`; solo una
  petición gana.
- Los códigos antiguos dejan de valer con la migración: cada persona con 2FA genera unos
  nuevos desde Ajustes (`POST /api/auth/totp/backup-codes`, exige un TOTP vigente).
"""

import hashlib
import hmac
import re
import secrets

CANTIDAD = 8
BITS = 128
_NO_HEX = re.compile(r"[^0-9A-F]")
_TABLA = """
CREATE TABLE IF NOT EXISTS user_totp_backup_codes (
    id         bigserial PRIMARY KEY,
    username   varchar(255) NOT NULL,
    sal        text         NOT NULL,
    code_hash  text         NOT NULL,
    created_at timestamptz  NOT NULL DEFAULT now(),
    used_at    timestamptz
);
CREATE INDEX IF NOT EXISTS user_totp_backup_codes_username
    ON user_totp_backup_codes (username) WHERE used_at IS NULL;
"""
_tabla_ok = False


def generar(n: int = CANTIDAD) -> list[str]:
    """`n` códigos de 128 bits: XXXX-XXXX-XXXX-XXXX-XXXX-XXXX-XXXX-XXXX."""
    salida = []
    for _ in range(n):
        h = secrets.token_hex(BITS // 8).upper()
        salida.append("-".join(h[i : i + 4] for i in range(0, len(h), 4)))
    return salida


def normalizar(codigo: str | None) -> str:
    """Mayúsculas y solo hexadecimal: da igual cómo lo escriba la persona."""
    return _NO_HEX.sub("", (codigo or "").upper())


def es_formato(codigo: str | None) -> bool:
    return len(normalizar(codigo)) == BITS // 4


def hash_codigo(codigo: str, sal_hex: str) -> str:
    return hmac.new(
        bytes.fromhex(sal_hex), normalizar(codigo).encode(), hashlib.sha256
    ).hexdigest()


async def asegurar_tabla(db) -> None:
    """La migración la crea; esto es la red por si el despliegue la olvidó (lección de F-06)."""
    global _tabla_ok
    if _tabla_ok:
        return
    await db.execute(_TABLA)
    _tabla_ok = True


async def guardar(db, username: str, codigos: list[str]) -> None:
    """Sustituye los códigos de la persona por `codigos` (los anteriores dejan de valer)."""
    await asegurar_tabla(db)
    await db.execute("DELETE FROM user_totp_backup_codes WHERE username = $1", username)
    for codigo in codigos:
        sal = secrets.token_hex(16)
        await db.execute(
            "INSERT INTO user_totp_backup_codes (username, sal, code_hash) VALUES ($1, $2, $3)",
            username,
            sal,
            hash_codigo(codigo, sal),
        )


async def consumir(db, username: str, codigo: str) -> bool:
    """True si `codigo` era un código de respaldo sin usar de `username`; lo marca usado de
    forma atómica. Un código con formato antiguo (8 hex) no llega ni a la base."""
    if not es_formato(codigo):
        return False
    await asegurar_tabla(db)
    filas = await db.fetch(
        "SELECT id, sal, code_hash FROM user_totp_backup_codes "
        "WHERE username = $1 AND used_at IS NULL",
        username,
    )
    for fila in filas:
        if hmac.compare_digest(hash_codigo(codigo, fila["sal"]), fila["code_hash"]):
            ganado = await db.fetchrow(
                "UPDATE user_totp_backup_codes SET used_at = now() "
                "WHERE id = $1 AND used_at IS NULL RETURNING id",
                fila["id"],
            )
            return ganado is not None
    return False


async def restantes(db, username: str) -> int:
    await asegurar_tabla(db)
    fila = await db.fetchrow(
        "SELECT count(*) AS n FROM user_totp_backup_codes "
        "WHERE username = $1 AND used_at IS NULL",
        username,
    )
    return int(fila["n"]) if fila else 0


async def borrar(db, username: str) -> None:
    await asegurar_tabla(db)
    await db.execute("DELETE FROM user_totp_backup_codes WHERE username = $1", username)
