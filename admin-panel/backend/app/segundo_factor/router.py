"""Restablecer el segundo factor de otra persona desde el panel.

Para cuando alguien pierde el teléfono y sus códigos de respaldo. Dos casos:

- Un buzón del webmail: se borra su segundo factor, sus códigos de respaldo y sus equipos de
  confianza, y se cierran sus sesiones. La próxima vez entra con su contraseña y lo configura
  de nuevo (si la política lo exige, el webmail se lo pide).
- Otro administrador del panel: nunca sobre la propia cuenta (para eso está «Mi cuenta» o el
  rescate por consola).

Solo superadministradores que hayan entrado con su propio segundo factor. Todo queda en
admin_audit.
"""

import json
import os

from fastapi import APIRouter, Depends, HTTPException, Request

from app import organizacion
from app.auth.dependencies import require_superadmin

router = APIRouter(prefix="/api/segundo-factor", tags=["segundo-factor"])

PUERTO_PORTAL_DOMINIO = "8444"


def _db(r: Request):
    return r.app.state.db


def _ip(r: Request) -> str:
    return r.headers.get("X-Real-IP", r.client.host if r.client else "")


async def _auditar(r: Request, admin: dict, accion: str, objetivo: str, detalles: dict):
    await _db(r).execute(
        "INSERT INTO admin_audit (admin_id, admin_username, action, target, details, ip_address) "
        "VALUES ($1,$2,$3,$4,$5::jsonb,$6)",
        admin["id"], admin["username"], accion, objetivo, json.dumps(detalles), _ip(r),
    )


def _exigir_segundo_factor_propio(admin: dict):
    if not admin.get("totp"):
        raise HTTPException(
            403,
            "Para restablecer el segundo factor de otra persona hay que haber entrado con el propio. "
            "Actívelo en «Mi cuenta», cierre sesión y vuelva a entrar.",
        )


async def _olvidar_en_cache(username: str):
    """Que el webmail reevalúe en el acto si a esta cuenta le toca segundo factor."""
    try:
        import redis.asyncio as aioredis

        r = aioredis.from_url(os.environ.get("WEBMAIL_REDIS_URL") or "redis://localhost:6379/0")
        try:
            await r.delete(f"mfa_oblig:{username}")
        finally:
            await r.aclose()
    except Exception:
        pass  # la clave caduca sola; no debe impedir el restablecimiento


@router.get("/buzon/{username:path}")
async def estado_buzon(username: str, request: Request, admin: dict = Depends(require_superadmin)):
    fila = await _db(request).fetchrow("SELECT enabled FROM user_totp WHERE username = $1", username)
    return {"username": username, "activo": bool(fila and fila["enabled"])}


@router.post("/buzon/{username:path}/restablecer")
async def restablecer_buzon(username: str, request: Request, admin: dict = Depends(require_superadmin)):
    _exigir_segundo_factor_propio(admin)
    db = _db(request)
    if not await db.fetchval("SELECT 1 FROM mailbox WHERE username = $1", username):
        raise HTTPException(404, "Buzón no encontrado")

    async with db.acquire() as con:
        async with con.transaction():
            res = await con.execute("DELETE FROM user_totp WHERE username = $1", username)
            tenia = not res.endswith(" 0")
            # Tablas que crea el webmail al primer uso: pueden no existir todavía.
            for tabla in ("user_totp_backup_codes", "dispositivos_confianza"):
                if await con.fetchval("SELECT to_regclass($1)", f"public.{tabla}"):
                    await con.execute(f"DELETE FROM {tabla} WHERE username = $1", username)  # nosec B608
            # Sus sesiones abiertas dejan de valer (generación de sesión del buzón).
            await con.execute(
                "INSERT INTO auth_estado (username, auth_version) VALUES ($1, 2) "
                "ON CONFLICT (username) DO UPDATE SET auth_version = auth_estado.auth_version + 1, updated_at = now()",
                username,
            )
    await _olvidar_en_cache(username)
    await _auditar(request, admin, "mailbox_2fa_restablecido", username, {"tenia_segundo_factor": tenia})
    return {"ok": True, "tenia_segundo_factor": tenia}


@router.post("/admin/{user_id}/restablecer")
async def restablecer_admin(user_id: int, request: Request, admin: dict = Depends(require_superadmin)):
    _exigir_segundo_factor_propio(admin)
    if user_id == admin["id"]:
        raise HTTPException(400, "No puede restablecer su propio segundo factor desde aquí: use «Mi cuenta».")
    db = _db(request)
    otro = await db.fetchrow("SELECT username, totp_enabled FROM admin_users WHERE id = $1", user_id)
    if not otro:
        raise HTTPException(404, "Administrador no encontrado")

    async with db.acquire() as con:
        async with con.transaction():
            await con.execute(
                "UPDATE admin_users SET totp_secret = NULL, totp_enabled = FALSE WHERE id = $1", user_id
            )
            await con.execute(
                "UPDATE admin_sessions SET revoked_at = NOW() WHERE user_id = $1 AND revoked_at IS NULL", user_id
            )
    await _auditar(
        request, admin, "admin_2fa_restablecido", otro["username"],
        {"tenia_segundo_factor": bool(otro["totp_enabled"])},
    )
    return {"ok": True, "tenia_segundo_factor": bool(otro["totp_enabled"])}


@router.get("/portal-dominio")
async def direccion_portal_dominio(request: Request, admin: dict = Depends(require_superadmin)):
    """Dirección del portal de administradores de dominio, para dársela a quien se da de alta.

    ORG_URL_PORTAL_DOMINIO si está definida; si no, el servidor del correo con el puerto del portal.
    """
    from urllib.parse import urlsplit

    # Por empresa: si el dominio tiene portal propio, su administrador entra por ESE nombre
    # (su certificado es el de la empresa), con el mismo puerto del portal.
    explicita = organizacion.url("ORG_URL_PORTAL_DOMINIO", "")
    puerto = (urlsplit(explicita).port if explicita else None) or PUERTO_PORTAL_DOMINIO
    por_dominio = {}
    try:
        filas = await _db(request).fetch("SELECT host, dominio FROM portal_empresa WHERE activo = true")
        por_dominio = {f["dominio"].lower(): f"https://{f['host'].lower()}:{puerto}" for f in filas}
    except Exception:
        pass  # instalación sin portales por empresa

    if explicita:
        return {"url": explicita, "por_dominio": por_dominio}
    correo = organizacion.url("PUBLIC_BASE_URL", organizacion.url("ORG_URL_CORREO", ""))
    servidor = urlsplit(correo).hostname if correo else None
    return {"url": f"https://{servidor}:{puerto}" if servidor else None, "por_dominio": por_dominio}
