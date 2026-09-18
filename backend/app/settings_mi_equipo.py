"""Código de enrolamiento autoservicio (Configuración del usuario).

La persona, ya autenticada en el webmail (incluida la verificación en dos pasos si la tiene), genera
un código de un solo uso para activar la app «Mi equipo» en SU propio teléfono. El código:
- es de **modo limitado** (el equipo Device Owner de fábrica lo sigue enrolando Tecnología por QR),
- deja al propio usuario como **custodio** del equipo,
- caduca en 24 h y solo hay uno activo por persona a la vez.
No da acceso al correo: es solo para la gestión del equipo. La lectura del correo en la app usa el
inicio de sesión normal (con su verificación en dos pasos).
"""

import hashlib
import logging
import secrets

from fastapi import APIRouter, Depends, Request

from app.auth.dependencies import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/settings/mi-equipo", tags=["mi-equipo"])

ALFABETO = "abcdefghjkmnpqrstuvwxyz23456789"  # sin 0/o/1/l/i: se teclea en el teléfono
HORAS_VALIDEZ = 24


def _generar() -> tuple[str, str, str]:
    grupos = ["".join(secrets.choice(ALFABETO) for _ in range(4)) for _ in range(3)]
    return "-".join(grupos), "".join(grupos), grupos[0]


async def _equipos_del_usuario(db, username: str) -> list[dict]:
    filas = await db.fetch(
        "SELECT id, nombre, modelo, fabricante, estado, modo, ultimo_contacto FROM disp_equipos "
        "WHERE custodio_email = $1 AND estado <> 'baja' ORDER BY enrolado_en DESC", username)
    return [dict(f) for f in filas]


@router.get("")
async def estado(request: Request, username: str = Depends(get_current_user)):
    db = request.app.state.db_pool
    activo = await db.fetchrow(
        "SELECT prefijo, caduca_en, usos, usos_max FROM disp_codigos "
        "WHERE custodio_email = $1 AND autoservicio = true AND revocado_en IS NULL "
        "AND usos < usos_max AND (caduca_en IS NULL OR caduca_en > NOW()) ORDER BY creado_en DESC LIMIT 1",
        username)
    return {
        "tiene_codigo_activo": activo is not None,
        "prefijo": activo["prefijo"] if activo else None,
        "caduca_en": activo["caduca_en"].isoformat() if activo and activo["caduca_en"] else None,
        "equipos": await _equipos_del_usuario(db, username),
    }


@router.post("", status_code=201)
async def generar(request: Request, username: str = Depends(get_current_user)):
    db = request.app.state.db_pool
    claro, junto, prefijo = _generar()
    async with db.acquire() as con, con.transaction():
        # Uno activo por persona: se revoca el anterior antes de dar el nuevo.
        await con.execute(
            "UPDATE disp_codigos SET revocado_en = NOW() WHERE custodio_email = $1 AND autoservicio = true AND revocado_en IS NULL",
            username)
        fila = await con.fetchrow(
            "INSERT INTO disp_codigos (codigo_hash, prefijo, etiqueta, modo, usos_max, creado_por, autoservicio, "
            "custodio_email, caduca_en) VALUES ($1,$2,$3,'limitado',1,$4,true,$4, NOW() + make_interval(hours => $5)) "
            "RETURNING id, caduca_en",
            hashlib.sha256(junto.encode()).hexdigest(), prefijo, "Autoservicio (mi teléfono)", username, HORAS_VALIDEZ)
    logger.info("codigo_autoservicio | user=%s | id=%s", username, fila["id"])
    return {"codigo": claro, "caduca_en": fila["caduca_en"].isoformat(), "horas": HORAS_VALIDEZ}


@router.delete("")
async def revocar(request: Request, username: str = Depends(get_current_user)):
    await request.app.state.db_pool.execute(
        "UPDATE disp_codigos SET revocado_en = NOW() WHERE custodio_email = $1 AND autoservicio = true AND revocado_en IS NULL",
        username)
    return {"ok": True}
