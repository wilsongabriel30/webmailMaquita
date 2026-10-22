"""Vales de entrada de un solo uso (admin_vales_entrada) y su canje en /api/auth/vale.

Los emite la consola (`maquita-panel vale-entrada <admin>`, deploy/panel) o la vuelta del proveedor
de identidad (oidc_rutas.py). Solo se guarda su hash; caducan en segundos (la consola admite hasta
900) y se marcan usados con un UPDATE atómico. El frontend los recibe en /entrar?vale=… y los canjea
aquí por una sesión normal del panel.

- Vale de la consola: no pide segundo factor (lo emitió root en el propio servidor), pero la
  sesión NO cuenta como abierta con segundo factor: no sirve para impersonar buzones.
- Vale del proveedor de identidad: si la cuenta tiene segundo factor, se pide aquí el código.
"""

import hashlib
import re
import secrets
from datetime import datetime, timedelta, timezone

import asyncpg
import pyotp
from fastapi import APIRouter, HTTPException, Request

from app.auth.sesion import abrir_sesion, ip_de

router = APIRouter(prefix="/api/auth", tags=["auth"])

RE_VALE = re.compile(r"[A-Za-z0-9_-]{32,128}")
NO_VALE = "El enlace de entrada no es válido, ya se usó o caducó"
INTENTOS_MAXIMOS = 5
MINUTOS_BLOQUEO = 15


def huella(vale: str) -> str:
    return hashlib.sha256(vale.encode()).hexdigest()


async def emitir(db, user_id: int, origen: str, exige_totp: bool, segundos: int, creado_por: str) -> str:
    """Crea un vale y devuelve el valor en claro (solo existe en la respuesta, nunca en la base)."""
    vale = secrets.token_urlsafe(32)
    await db.execute(
        """INSERT INTO admin_vales_entrada (vale_hash, user_id, origen, exige_totp, creado_por, expires_at)
           VALUES ($1, $2, $3, $4, $5, $6)""",
        huella(vale), user_id, origen, exige_totp, creado_por[:255],
        datetime.now(timezone.utc) + timedelta(seconds=segundos),
    )
    return vale


async def _fallo_codigo(db, fila) -> None:
    intentos = (fila["failed_attempts"] or 0) + 1
    bloqueo = datetime.now(timezone.utc) + timedelta(minutes=MINUTOS_BLOQUEO) if intentos >= INTENTOS_MAXIMOS else None
    await db.execute("UPDATE admin_users SET failed_attempts = $1, locked_until = $2 WHERE id = $3",
                     intentos, bloqueo, fila["id"])


@router.post("/vale")
async def canjear(request: Request):
    try:
        datos = await request.json()
    except Exception:
        datos = {}
    datos = datos if isinstance(datos, dict) else {}
    vale = str(datos.get("vale", ""))
    if not RE_VALE.fullmatch(vale):
        raise HTTPException(401, NO_VALE)
    db = request.app.state.db
    try:
        fila = await db.fetchrow(
            """SELECT v.id AS vale_id, v.origen, v.exige_totp, u.id, u.username, u.display_name, u.role, u.active,
                      u.locked_until, u.failed_attempts, u.totp_secret, u.totp_enabled
                 FROM admin_vales_entrada v JOIN admin_users u ON u.id = v.user_id
                WHERE v.vale_hash = $1 AND v.usado_en IS NULL AND v.expires_at > NOW()""",
            huella(vale),
        )
    except asyncpg.exceptions.UndefinedTableError:
        raise HTTPException(503, "Falta la migración de los vales de entrada (ajuste 66)")
    if not fila:
        raise HTTPException(401, NO_VALE)
    if not fila["active"]:
        raise HTTPException(403, "Cuenta desactivada")
    if fila["locked_until"] and fila["locked_until"] > datetime.now(timezone.utc):
        raise HTTPException(423, "Cuenta bloqueada temporalmente")

    con_totp = False
    if fila["exige_totp"] and fila["totp_enabled"]:
        codigo = str(datos.get("totp_code", "")).strip()
        if not codigo:
            return {"requires_totp": True}  # el vale sigue sin usar hasta que llegue el código
        if not fila["totp_secret"] or not pyotp.TOTP(fila["totp_secret"]).verify(codigo, valid_window=1):
            await _fallo_codigo(db, fila)
            raise HTTPException(401, "Código de verificación inválido")
        con_totp = True

    usado = await db.fetchval(
        """UPDATE admin_vales_entrada SET usado_en = NOW(), usado_ip = $2
            WHERE id = $1 AND usado_en IS NULL AND expires_at > NOW() RETURNING id""",
        fila["vale_id"], ip_de(request),
    )
    if not usado:  # otro canje del mismo vale ganó la carrera
        raise HTTPException(401, NO_VALE)
    return await abrir_sesion(db, request, fila, con_totp, "login_vale",
                              {"origen": fila["origen"], "segundo_factor": con_totp})
