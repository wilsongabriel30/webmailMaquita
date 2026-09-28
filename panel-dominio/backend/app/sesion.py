"""Sesiones del portal: fichas opacas al azar, guardadas solo como hash.

No hay JWT ni secreto compartido con el panel general ni con el correo: una sesión de aquí
no sirve en ningún otro sitio. Los dominios y el estado de la cuenta se leen de la base en
cada petición; quitar un dominio o desactivar la cuenta surte efecto al instante.
"""

import hashlib
import json
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, Request

from app import config, config_extra


def _hash(ficha: str) -> str:
    return hashlib.sha256(ficha.encode()).hexdigest()


def ip_de(request: Request) -> str:
    return request.headers.get("X-Real-IP", request.client.host if request.client else "")[:45]


async def abrir(request: Request, admin_id: int) -> tuple[str, datetime]:
    ficha = secrets.token_urlsafe(32)
    vence = datetime.now(timezone.utc) + timedelta(hours=config.HORAS_SESION)
    await request.app.state.db.execute(
        "INSERT INTO pd_sesiones (admin_id, token_hash, ip, user_agent, expires_at) VALUES ($1,$2,$3,$4,$5)",
        admin_id, _hash(ficha), ip_de(request), request.headers.get("User-Agent", "")[:300], vence,
    )
    return ficha, vence


async def cerrar(request: Request, admin: dict, todas: bool = False) -> None:
    if todas:
        await request.app.state.db.execute(
            "UPDATE pd_sesiones SET revoked_at = NOW() WHERE admin_id = $1 AND revoked_at IS NULL", admin["id"])
    else:
        await request.app.state.db.execute(
            "UPDATE pd_sesiones SET revoked_at = NOW() WHERE id = $1", admin["sesion_id"])


async def admin_actual(request: Request) -> dict:
    cabecera = request.headers.get("Authorization", "")
    if not cabecera.startswith("Bearer ") or len(cabecera) > 200:
        raise HTTPException(401, "Sesión requerida")
    db = request.app.state.db
    fila = await db.fetchrow(
        """SELECT s.id AS sesion_id, a.id, a.username, a.display_name, a.active, a.must_change_password, a.totp_enabled
             FROM pd_sesiones s JOIN pd_admins a ON a.id = s.admin_id
            WHERE s.token_hash = $1 AND s.revoked_at IS NULL AND s.expires_at > NOW()""",
        _hash(cabecera[7:]),
    )
    if not fila or not fila["active"]:
        raise HTTPException(401, "Sesión cerrada o vencida")
    # Con la contraseña inicial solo se puede cambiarla: nada de gestionar cuentas todavía.
    if fila["must_change_password"] and not request.url.path.startswith("/api/acceso/"):
        raise HTTPException(403, "Cambia tu contraseña inicial antes de continuar")
    # Sin segundo factor tampoco: solo puede configurarlo.
    if config_extra.TOTP_OBLIGATORIO and not fila["totp_enabled"] and not request.url.path.startswith("/api/acceso/"):
        raise HTTPException(403, "Activa el segundo factor antes de continuar")
    dominios = await db.fetch(
        """SELECT d.domain FROM pd_admin_dominios p JOIN domain d ON d.domain = p.domain
            WHERE p.admin_id = $1 ORDER BY d.domain""",
        fila["id"],
    )
    return {
        "id": fila["id"], "username": fila["username"], "display_name": fila["display_name"],
        "sesion_id": fila["sesion_id"], "totp": fila["totp_enabled"],
        "debe_cambiar_clave": fila["must_change_password"], "dominios": [d["domain"] for d in dominios],
    }


async def auditar(request: Request, admin: dict, accion: str, objetivo: str = "", detalles: dict | None = None):
    await request.app.state.db.execute(
        "INSERT INTO pd_auditoria (admin_id, admin_username, action, target, details, ip) VALUES ($1,$2,$3,$4,$5::jsonb,$6)",
        admin.get("id"), admin["username"], accion, objetivo[:255],
        json.dumps(detalles) if detalles else None, ip_de(request),
    )
