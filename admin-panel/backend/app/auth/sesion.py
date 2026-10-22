"""Abrir una sesión del panel: lo común a todas las formas de entrar.

La contraseña (/api/auth/login), el vale de un solo uso de la consola y la vuelta del proveedor de
identidad (/api/auth/vale) terminan aquí: se limpian los intentos fallidos, se emite el token de
sesión, se guarda su hash en admin_sessions (A-9) y se deja la entrada en admin_audit.
"""

import hashlib
import json

from fastapi import Request

from app.auth.jwt import create_token


def ip_de(request: Request) -> str:
    return request.headers.get("X-Real-IP", request.client.host if request.client else "unknown")[:45]


async def abrir_sesion(db, request: Request, user, con_totp: bool, accion: str = "login",
                       detalles: dict | None = None) -> dict:
    """`user`: fila de admin_users (id, username, display_name, role). Devuelve lo que espera el frontend."""
    await db.execute(
        "UPDATE admin_users SET failed_attempts = 0, locked_until = NULL, last_login = NOW() WHERE id = $1",
        user["id"],
    )
    token, expires = create_token(user["id"], user["username"], user["role"], totp=con_totp)
    await db.execute(
        """INSERT INTO admin_sessions (user_id, token_hash, ip_address, user_agent, expires_at)
           VALUES ($1, $2, $3, $4, $5)""",
        user["id"], hashlib.sha256(token.encode()).hexdigest(), ip_de(request),
        request.headers.get("User-Agent", ""), expires,
    )
    if detalles:
        await db.execute(
            "INSERT INTO admin_audit (admin_id, admin_username, action, details, ip_address) VALUES ($1, $2, $3, $4::jsonb, $5)",
            user["id"], user["username"], accion, json.dumps(detalles), ip_de(request),
        )
    else:
        await db.execute(
            "INSERT INTO admin_audit (admin_id, admin_username, action, ip_address) VALUES ($1, $2, $3, $4)",
            user["id"], user["username"], accion, ip_de(request),
        )
    return {
        "token": token,
        "expires": expires.isoformat(),
        "user": {
            "id": user["id"],
            "username": user["username"],
            "display_name": user["display_name"],
            "role": user["role"],
        },
    }
