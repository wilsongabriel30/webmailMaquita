"""Tabla de las fichas de API del panel y autenticación con una de ellas («Authorization: Bearer mqa_…» o X-Admin-Token).

La ficha vale con las mismas condiciones que una sesión (cuenta activa, rol leído de la base en cada petición) más
las suyas: no revocada, no vencida y con alcance para el método y la ruta. No lleva segundo factor («totp»: False):
lo que lo exige en la interfaz sigue sin poderse hacer con ella. Cada petición que cambia algo queda en la auditoría
(«ficha_api_uso», con el número de la ficha, el método y la ruta).
"""

import hashlib

from fastapi import HTTPException, Request

from app.fichas_api import alcance

ESQUEMA = """
CREATE TABLE IF NOT EXISTS admin_fichas_api (
    id SERIAL PRIMARY KEY,
    user_id INT NOT NULL REFERENCES admin_users(id) ON DELETE CASCADE,
    nombre VARCHAR(80) NOT NULL,
    prefijo VARCHAR(16) NOT NULL,
    token_hash CHAR(64) NOT NULL UNIQUE,
    alcances TEXT[] NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
    revoked_at TIMESTAMP WITH TIME ZONE,
    last_used_at TIMESTAMP WITH TIME ZONE,
    last_ip VARCHAR(45)
);
CREATE INDEX IF NOT EXISTS idx_admin_fichas_api_user ON admin_fichas_api(user_id);
"""


CERROJO_ESQUEMA = 7_311_011  # pg_advisory_xact_lock: varios workers arrancan a la vez


async def crear_tabla(pool) -> None:
    # Sin el cerrojo, dos workers que crean la tabla a la vez chocan en pg_type y el panel no arranca.
    async with pool.acquire() as conexion:
        async with conexion.transaction():
            await conexion.execute("SELECT pg_advisory_xact_lock($1)", CERROJO_ESQUEMA)
            await conexion.execute(ESQUEMA)


def _ip(request: Request) -> str:
    return request.headers.get("X-Real-IP", request.client.host if request.client else "")[:45]


async def admin_de_ficha(request: Request, ficha: str) -> dict:
    db = request.app.state.db
    fila = await db.fetchrow(
        """SELECT f.id AS ficha_id, f.alcances, u.id, u.username, u.role, u.active
             FROM admin_fichas_api f JOIN admin_users u ON u.id = f.user_id
            WHERE f.token_hash = $1 AND f.revoked_at IS NULL AND f.expires_at > NOW()""",
        hashlib.sha256(ficha.encode()).hexdigest(),
    )
    if not fila or not fila["active"]:
        raise HTTPException(401, "Ficha de API revocada, vencida o de una cuenta desactivada")
    alcances = list(fila["alcances"] or [])
    if not alcance.permitido(alcances, request.method, request.url.path):
        raise HTTPException(403, "La ficha de API no tiene permiso para esto")
    await db.execute(
        """UPDATE admin_fichas_api SET last_used_at = NOW(), last_ip = $2
            WHERE id = $1 AND (last_used_at IS NULL OR last_used_at < NOW() - INTERVAL '1 minute')""",
        fila["ficha_id"], _ip(request))
    if request.method not in alcance.LECTURA:
        await db.execute(
            "INSERT INTO admin_audit (admin_id, admin_username, action, target, details, ip_address) "
            "VALUES ($1, $2, 'ficha_api_uso', $3, jsonb_build_object('ficha_api', $4::int, 'metodo', $5::text), $6)",
            fila["id"], fila["username"], request.url.path[:255], fila["ficha_id"], request.method, _ip(request))
    return {"id": fila["id"], "username": fila["username"], "role": fila["role"], "session_id": None,
            "totp": False, "ficha_api": fila["ficha_id"], "alcances": alcances}
