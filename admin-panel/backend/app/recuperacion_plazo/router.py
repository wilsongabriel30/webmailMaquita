"""Plazo para recuperar correos enviados (panel :8443).

«Recuperar mensaje» retira un correo enviado por error del buzón del destinatario. Aquí se fija
durante cuánto tiempo se puede hacer: un plazo para los correos que el destinatario ya leyó y otro
para los que siguen sin leer. El correo aplica el cambio en la siguiente recuperación, sin
reiniciar nada (backend/app/mail/services/plazo_recuperacion.py). Mientras no se guarde nada desde
el panel rige el .env del correo para lo leído y «sin límite» para lo no leído.
"""

import json

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from app.auth.dependencies import get_current_admin, require_superadmin
from app.recuperacion_plazo import reglas

router = APIRouter(prefix="/api/recuperacion-plazo", tags=["recuperacion-plazo"])


def _db(r: Request):
    return r.app.state.db


class Plazo(BaseModel):
    minutos_leidos: int
    minutos_sin_leer: int


async def _guardado(db):
    try:
        return await db.fetchrow(
            "SELECT minutos_leidos, minutos_sin_leer, actualizado, por "
            "FROM recuperacion_plazo_politica WHERE id = 1"
        )
    except Exception:
        return None


@router.get("")
async def ver(r: Request, a=Depends(get_current_admin)):
    fila = await _guardado(_db(r))
    if fila:
        return {
            "minutos_leidos": int(fila["minutos_leidos"]),
            "minutos_sin_leer": int(fila["minutos_sin_leer"]),
            "origen": "panel",
            "actualizado": fila["actualizado"],
            "por": fila["por"],
            "maximo": reglas.MAXIMO,
        }
    return {
        **reglas.leer_env_del_correo(),
        "origen": "archivo",
        "actualizado": None,
        "por": "",
        "maximo": reglas.MAXIMO,
    }


@router.post("")
async def guardar(body: Plazo, r: Request, a=Depends(require_superadmin)):
    error = reglas.validar(body.minutos_leidos, body.minutos_sin_leer)
    if error:
        raise HTTPException(400, error)
    db = _db(r)
    await db.execute(
        "INSERT INTO recuperacion_plazo_politica (id, minutos_leidos, minutos_sin_leer, actualizado, por) "
        "VALUES (1, $1, $2, now(), $3) "
        "ON CONFLICT (id) DO UPDATE SET minutos_leidos = EXCLUDED.minutos_leidos, "
        "minutos_sin_leer = EXCLUDED.minutos_sin_leer, actualizado = now(), por = EXCLUDED.por",
        body.minutos_leidos,
        body.minutos_sin_leer,
        a["username"],
    )
    await db.execute(
        "INSERT INTO admin_audit (admin_id, admin_username, action, target, details, ip_address) "
        "VALUES ($1, $2, $3, $4, $5::jsonb, $6)",
        a["id"],
        a["username"],
        "recuperacion_plazo_politica",
        "recuperacion_plazo_politica",
        json.dumps(
            {
                "minutos_leidos": body.minutos_leidos,
                "minutos_sin_leer": body.minutos_sin_leer,
            }
        ),
        r.headers.get("X-Real-IP", r.client.host if r.client else ""),
    )
    return {
        "ok": True,
        "minutos_leidos": body.minutos_leidos,
        "minutos_sin_leer": body.minutos_sin_leer,
    }
