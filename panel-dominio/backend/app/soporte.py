"""Entrada de soporte: canjear el vale que emitió el superadministrador por una sesión del portal.

El vale (pd_vales_soporte) lo crea el panel general o la consola; aquí solo se canjea, una vez:
se guarda como hash, caduca en minutos y el UPDATE que lo marca usado es atómico, así que dos
canjes a la vez no abren dos sesiones. La sesión resultante dura PD_MINUTOS_SOPORTE y queda en
pd_auditoria como «el superadmin X entró como soporte de <dominio>».
"""

import hashlib
import re
import secrets
from datetime import datetime, timedelta, timezone

import asyncpg
from fastapi import APIRouter, HTTPException, Request

from app import sesion_soporte
from app.sesion import auditar, ip_de

router = APIRouter(prefix="/api/acceso", tags=["acceso"])

RE_VALE = re.compile(r"[A-Za-z0-9_-]{32,128}")
_NO_VALE = "El vale de soporte no es válido, ya se usó o caducó. Pide otro en el panel general."
NO_INSTALADO = "La entrada de soporte no está instalada en este servidor (ajuste 66)"


def _hash(texto: str) -> str:
    return hashlib.sha256(texto.encode()).hexdigest()


@router.post("/soporte")
async def entrar_como_soporte(request: Request):
    try:
        datos = await request.json()
    except Exception:
        datos = {}
    vale = str(datos.get("vale", "") if isinstance(datos, dict) else "")
    if not RE_VALE.fullmatch(vale):
        raise HTTPException(401, _NO_VALE)
    db = request.app.state.db
    try:
        fila = await db.fetchrow(
            """UPDATE pd_vales_soporte v SET usado_en = NOW()
                WHERE v.vale_hash = $1 AND v.usado_en IS NULL AND v.expires_at > NOW()
                  AND EXISTS (SELECT 1 FROM domain d WHERE d.domain = v.domain)
            RETURNING v.id, v.domain, v.superadmin, v.solo_lectura, v.origen, v.motivo""",
            _hash(vale),
        )
    except asyncpg.exceptions.UndefinedTableError:
        raise HTTPException(503, NO_INSTALADO)
    if not fila:
        raise HTTPException(401, _NO_VALE)

    ficha = secrets.token_urlsafe(32)
    vence = datetime.now(timezone.utc) + timedelta(minutes=sesion_soporte.MINUTOS_SOPORTE)
    sesion_id = await db.fetchval(
        """INSERT INTO pd_sesiones_soporte (vale_id, token_hash, domain, superadmin, solo_lectura, ip, user_agent, expires_at)
           VALUES ($1,$2,$3,$4,$5,$6,$7,$8) RETURNING id""",
        fila["id"], _hash(ficha), fila["domain"], fila["superadmin"], fila["solo_lectura"],
        ip_de(request), request.headers.get("User-Agent", "")[:300], vence,
    )
    admin = sesion_soporte.como_admin(sesion_id, fila["domain"], fila["superadmin"], fila["solo_lectura"], vence)
    await auditar(request, admin, "soporte_entrada", fila["domain"],
                  {"texto": f"el superadmin {fila['superadmin']} entró como soporte de {fila['domain']}",
                   "origen": fila["origen"], "motivo": (fila["motivo"] or "")[:255],
                   "minutos": sesion_soporte.MINUTOS_SOPORTE})
    return {"token": ficha, "vence": vence.isoformat(), "soporte": admin["soporte"], "dominio": fila["domain"]}
