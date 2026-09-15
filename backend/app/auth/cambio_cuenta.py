"""Cambio de cuenta dentro de la misma sesión del navegador (como en Outlook).

Caso: una persona administra direccion@ y presidencia@. Entra con SU clave (cuenta principal)
y, desde la barra lateral, pasa a cualquier cuenta que le hayan asignado en el panel
(Buzones compartidos, nivel full o send-as = `mail_delegation.can_send_as`). Al cambiar, TODO
pasa a ser de esa cuenta: correo, calendario, contactos, drive, firmas... porque lo que se
crea es una sesión completa de esa cuenta, abierta con el usuario maestro de Dovecot (el
mismo mecanismo de la impersonación del panel). Nunca hace falta la clave de la otra cuenta
y la clave maestra nunca sale del servidor.

- La sesión de la cuenta principal se conserva; cada sesión "delegada" guarda un puntero a
  ella (`cuenta_principal:<cuenta>:<sid>` = "principal|sid_principal") para poder volver y para
  saber qué otras cuentas se pueden abrir.
- Volver a la principal crea una sesión normal nueva con la clave que la principal dejó
  guardada (cifrada) en su sesión viva; si esa sesión ya venció, hay que entrar de nuevo.
- Tipo de sesión `delegada`: se prorroga como una normal (no vence a la hora como la
  impersonación de un administrador).
- Cada cambio queda en `audit_log` (acción `cambio_cuenta`).
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel

from app.auth.cookies import poner_cookies_sesion
from app.auth.dependencies import get_current_user
from app.auth.dovecot_auth_service import authenticate
from app.auth.sesiones import cerrar_sid, crear_sesion
from app.config import get_settings
from app.core.session import decrypt_password
from app.mail.services.cuentas_delegadas import USUARIO_MAESTRO, puede_usar

router = APIRouter(prefix="/api/auth/cuentas", tags=["auth-cuentas"])
log = logging.getLogger(__name__)

PREFIJO_PRINCIPAL = "cuenta_principal"
DIAS_SESION_DELEGADA = 1


class CambioIn(BaseModel):
    cuenta: str


async def _principal_de(redis, username: str, sid: str) -> tuple[str, str]:
    """(cuenta principal, sid de su sesión). Si la sesión actual es la principal, ella misma."""
    raw = await redis.get(f"{PREFIJO_PRINCIPAL}:{username}:{sid}")
    if raw:
        valor = raw.decode() if isinstance(raw, bytes) else str(raw)
        principal, _, sid_principal = valor.partition("|")
        if principal and sid_principal:
            return principal.lower(), sid_principal
    return username.lower(), sid


async def _cuentas_asignadas(db, principal: str) -> list[dict]:
    filas = await db.fetch(
        """
        SELECT d.mailbox AS email, COALESCE(m.name, '') AS nombre
          FROM mail_delegation d
          JOIN mailbox m ON m.username = d.mailbox AND m.active = true
         WHERE lower(d.delegate) = lower($1) AND COALESCE(d.can_send_as, false)
         ORDER BY d.mailbox
        """,
        principal,
    )
    return [dict(f) for f in filas]


@router.get("")
async def listar(request: Request, username: str = Depends(get_current_user)):
    db = request.app.state.db_pool
    redis = request.app.state.redis
    principal, _ = await _principal_de(redis, username, request.state.sid)
    fila = await db.fetchrow("SELECT COALESCE(name, '') AS nombre FROM mailbox WHERE username = $1", principal)
    cuentas = [{"email": principal, "nombre": (fila["nombre"] if fila else "") or "", "principal": True}]
    cuentas += [{**c, "principal": False} for c in await _cuentas_asignadas(db, principal)]
    for c in cuentas:
        c["activa"] = c["email"].lower() == username.lower()
    return {"principal": principal, "activa": username, "cuentas": cuentas}


@router.post("/cambiar")
async def cambiar(
    body: CambioIn,
    request: Request,
    response: Response,
    username: str = Depends(get_current_user),
):
    db = request.app.state.db_pool
    redis = request.app.state.redis
    settings = get_settings()
    sid_actual = request.state.sid
    principal, sid_principal = await _principal_de(redis, username, sid_actual)
    cuenta = body.cuenta.strip().lower()
    if "@" not in cuenta:
        cuenta = f"{cuenta}@{settings.mail_domain}"
    if cuenta == username.lower():
        return {"activa": username, "principal": principal, "cambiado": False}

    ahora = datetime.now(timezone.utc)
    if cuenta == principal:
        # Volver a la cuenta con la que se entró: su clave sigue cifrada en su sesión viva.
        raw = await redis.get(f"imap_pass:{principal}:{sid_principal}")
        if not raw:
            raise HTTPException(401, "La sesión principal venció: vuelve a iniciar sesión")
        try:
            clave = decrypt_password(raw)
        except Exception:
            raise HTTPException(401, "La sesión principal venció: vuelve a iniciar sesión")
        sesion = await crear_sesion(db, redis, request, principal, clave, kind="normal")
    else:
        if not await puede_usar(db, principal, cuenta, para_enviar=True):
            raise HTTPException(403, f"La cuenta {cuenta} no está asignada a {principal}")
        if await db.fetchval("SELECT 1 FROM admin WHERE username = $1 AND superadmin = true", cuenta):
            raise HTTPException(403, "No se puede abrir la cuenta de un superadministrador")
        if not await authenticate(f"{cuenta}*{USUARIO_MAESTRO}", settings.master_password, settings.imap_host, settings.imap_port):
            raise HTTPException(400, f"No se pudo abrir el buzón de {cuenta}")
        sesion = await crear_sesion(
            db, redis, request, cuenta, settings.master_password,
            kind="delegada",
            abs_exp=ahora + timedelta(days=DIAS_SESION_DELEGADA),
            master=USUARIO_MAESTRO,
            user_agent=f"Cuenta-Delegada:{principal}",
        )
        ttl = int((sesion["abs_exp"] - ahora).total_seconds()) if sesion.get("abs_exp") else 86400
        await redis.set(f"{PREFIJO_PRINCIPAL}:{cuenta}:{sesion['sid']}", f"{principal}|{sid_principal}", ex=max(60, ttl))

    # La sesión delegada que se deja atrás se cierra; la principal se conserva para volver.
    if username.lower() != principal:
        try:
            await cerrar_sid(db, redis, username, sid_actual, motivo="cambio-cuenta")
            await redis.delete(f"{PREFIJO_PRINCIPAL}:{username}:{sid_actual}")
        except Exception:
            pass

    try:
        await db.execute(
            "INSERT INTO audit_log (admin_user, action, target, details, ip_address) VALUES ($1, $2, $3, $4::jsonb, $5::inet)",
            principal, "cambio_cuenta", cuenta,
            json.dumps({"desde": username, "hacia": cuenta}),
            (request.headers.get("x-real-ip") or (request.client.host if request.client else None) or "0.0.0.0"),
        )
    except Exception as exc:  # la auditoría no debe impedir trabajar
        log.warning("cambio_cuenta sin auditoría: %s", exc)

    poner_cookies_sesion(response, request, sesion)
    return {"activa": cuenta, "principal": principal, "cambiado": True}
