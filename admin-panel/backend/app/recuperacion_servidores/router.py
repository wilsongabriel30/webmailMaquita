"""Recuperación entre servidores: política sobre los correos ya leídos (panel :8443).

Cuando otro servidor de la suite pide retirar un correo de un buzón de este servidor, aquí se decide
si se retira también lo que el destinatario ya leyó: para todos, o solo para los dominios de
confianza. El correo aplica el cambio en la siguiente solicitud, sin reiniciar nada
(backend/app/federacion/recuperacion_politica.py). Mientras no se guarde nada desde el panel rige
el .env del correo.
"""

import json

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from app.auth.dependencies import get_current_admin, require_superadmin
from app.recuperacion_servidores import dominios as dom

router = APIRouter(
    prefix="/api/recuperacion-servidores", tags=["recuperacion-servidores"]
)
ULTIMAS = 30

_SOLICITUDES = f"""
SELECT created_at AS fecha, admin_user AS remitente, target AS message_id, ip_address::text AS ip,
       details->>'dominio_solicitante' AS dominio,
       details->'destinatarios'->0->>'destinatario' AS destinatario,
       details->'destinatarios'->0->>'resultado' AS resultado,
       (details->'destinatarios'->0->>'leido')::boolean AS leido,
       COALESCE((details->>'retirado')::boolean, false) AS retirado
FROM audit_log
WHERE action = 'message_recall' AND details->>'pedido_por_otro_servidor' = 'true'
ORDER BY created_at DESC LIMIT {ULTIMAS}
"""


def _db(r: Request):
    return r.app.state.db


class Politica(BaseModel):
    retirar_leidos: bool
    dominios_confianza: list[str] = []


async def _guardada(db):
    try:
        return await db.fetchrow(
            "SELECT retirar_leidos, dominios_confianza, actualizado, por "
            "FROM federacion_recuperacion_politica WHERE id = 1"
        )
    except Exception:
        return None


async def _solicitudes(db) -> list[dict]:
    try:
        return [dict(f) for f in await db.fetch(_SOLICITUDES)]
    except Exception:
        return []


@router.get("")
async def ver(r: Request, a=Depends(get_current_admin)):
    db = _db(r)
    fila = await _guardada(db)
    if fila:
        politica = {
            "retirar_leidos": bool(fila["retirar_leidos"]),
            "dominios_confianza": list(fila["dominios_confianza"] or []),
            "origen": "panel",
            "actualizado": fila["actualizado"],
            "por": fila["por"],
        }
    else:
        politica = {
            **dom.leer_env_del_correo(),
            "origen": "archivo",
            "actualizado": None,
            "por": "",
        }
    try:
        propios = [
            f["domain"]
            for f in await db.fetch(
                "SELECT domain FROM domain WHERE active = true AND domain <> 'ALL' ORDER BY domain"
            )
        ]
    except Exception:
        propios = []
    return {
        **politica,
        "dominios_propios": propios,
        "solicitudes": await _solicitudes(db),
    }


@router.post("")
async def guardar(body: Politica, r: Request, a=Depends(require_superadmin)):
    db = _db(r)
    validos, rechazados = dom.normalizar(body.dominios_confianza)
    if rechazados:
        raise HTTPException(
            400,
            "No parece un dominio: "
            + ", ".join(f"«{d}»" for d in rechazados[:5])
            + ". Escriba solo el dominio, por ejemplo socio.org",
        )
    if len(validos) > dom.MAX_DOMINIOS:
        raise HTTPException(400, f"Como máximo {dom.MAX_DOMINIOS} dominios de confianza")
    await db.execute(
        "INSERT INTO federacion_recuperacion_politica (id, retirar_leidos, dominios_confianza, actualizado, por) "
        "VALUES (1, $1, $2, now(), $3) "
        "ON CONFLICT (id) DO UPDATE SET retirar_leidos = EXCLUDED.retirar_leidos, "
        "dominios_confianza = EXCLUDED.dominios_confianza, actualizado = now(), por = EXCLUDED.por",
        bool(body.retirar_leidos),
        validos,
        a["username"],
    )
    await db.execute(
        "INSERT INTO admin_audit (admin_id, admin_username, action, target, details, ip_address) "
        "VALUES ($1, $2, $3, $4, $5::jsonb, $6)",
        a["id"],
        a["username"],
        "recuperacion_servidores_politica",
        "federacion_recuperacion_politica",
        json.dumps(
            {"retirar_leidos": bool(body.retirar_leidos), "dominios_confianza": validos}
        ),
        r.headers.get("X-Real-IP", r.client.host if r.client else ""),
    )
    return {"ok": True, "retirar_leidos": bool(body.retirar_leidos), "dominios_confianza": validos}
