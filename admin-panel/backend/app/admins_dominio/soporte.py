"""Entrar al portal de un dominio «como el cliente», para darle soporte (botón en Dominios).

El superadministrador pide aquí un vale de un solo uso (pd_vales_soporte, solo el hash) y recibe
la dirección https://<portal>:8444/?vale=…; el portal lo canjea por una sesión de soporte corta,
marcada como tal, sin la clave ni el segundo factor del cliente (panel-dominio/app/soporte.py).

- Solo lectura por defecto; «con acciones» permite modificar y cada acción queda auditada en
  pd_auditoria con la marca de soporte.
- Como impersonar un buzón, exige una sesión abierta con segundo factor (IMPERSONAR_EXIGE_TOTP).
- Queda en admin_audit («soporte_vale_emitido») y, al entrar, en pd_auditoria («soporte_entrada»).
La misma orden por consola: maquita-panel-dominio vale-soporte <dominio> (deploy/panel).
"""

import hashlib
import json
import re
import secrets
from datetime import datetime, timedelta, timezone

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, Request

from app import config
from app.admins_dominio import direccion_portal
from app.auth.dependencies import require_superadmin
from app.auth.sesion import ip_de

router = APIRouter(prefix="/api/admins-dominio", tags=["admins-dominio"])

RE_DOMINIO = re.compile(r"(?=.{4,253}$)([a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}")
MODOS = ("solo_lectura", "con_acciones")
_CONTROL = re.compile(r"[\x00-\x1f\x7f]")
VIDA_DEFECTO, VIDA_MINIMA, VIDA_MAXIMA = 300, 10, 900


def _vida(valor) -> int:
    if valor is None or valor == "":
        return VIDA_DEFECTO
    try:
        segundos = int(valor)
    except (TypeError, ValueError):
        raise HTTPException(400, "La vida del vale es un número de segundos")
    if not VIDA_MINIMA <= segundos <= VIDA_MAXIMA:
        raise HTTPException(400, f"La vida del vale va de {VIDA_MINIMA} a {VIDA_MAXIMA} segundos")
    return segundos


@router.post("/soporte", status_code=201)
async def vale_soporte(request: Request, admin: dict = Depends(require_superadmin)):
    if config.IMPERSONAR_EXIGE_TOTP and not admin.get("totp"):
        raise HTTPException(403, "Para entrar como soporte, abre la sesión del panel con tu segundo factor")
    datos = await request.json()
    datos = datos if isinstance(datos, dict) else {}
    dominio = str(datos.get("dominio", "")).strip().lower()
    if not RE_DOMINIO.fullmatch(dominio):
        raise HTTPException(400, "Dominio no válido")
    modo = str(datos.get("modo") or "solo_lectura")
    if modo not in MODOS:
        raise HTTPException(400, "Modo no válido: solo_lectura o con_acciones")
    segundos = _vida(datos.get("vida"))
    motivo = _CONTROL.sub(" ", str(datos.get("motivo", ""))).strip()[:255]
    db = request.app.state.db
    dominio = await db.fetchval("SELECT domain FROM domain WHERE lower(domain) = $1", dominio)
    if not dominio:
        raise HTTPException(404, "Ese dominio no está en el servidor")
    base = await direccion_portal.de_dominio(db, dominio)
    if not base:
        raise HTTPException(409, "No se sabe la dirección del portal de dominio: defina ORG_URL_PORTAL_DOMINIO")
    vale = secrets.token_urlsafe(32)
    try:
        await db.execute(
            """INSERT INTO pd_vales_soporte (vale_hash, domain, solo_lectura, superadmin, origen, motivo, expires_at)
               VALUES ($1, $2, $3, $4, 'panel', $5, $6)""",
            hashlib.sha256(vale.encode()).hexdigest(), dominio, modo == "solo_lectura", admin["username"], motivo,
            datetime.now(timezone.utc) + timedelta(seconds=segundos),
        )
    except asyncpg.exceptions.UndefinedTableError:
        raise HTTPException(503, "La entrada de soporte no está instalada en este servidor (ajuste 66)")
    await db.execute(
        "INSERT INTO admin_audit (admin_id, admin_username, action, target, details, ip_address) "
        "VALUES ($1, $2, $3, $4, $5::jsonb, $6)",
        admin["id"], admin["username"], "soporte_vale_emitido", dominio,
        json.dumps({"origen": "panel", "modo": modo, "vida_segundos": segundos, "motivo": motivo}), ip_de(request),
    )
    return {"url": f"{base.rstrip('/')}/?vale={vale}", "dominio": dominio, "modo": modo, "valido_segundos": segundos}
