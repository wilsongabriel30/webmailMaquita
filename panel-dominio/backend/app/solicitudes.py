"""Eliminar una cuenta: el administrador de dominio la pide y el administrador general la confirma.

Borrar un buzón no tiene vuelta atrás, así que el portal no puede hacerlo por sí mismo (su
usuario de base de datos ni siquiera tiene ese permiso). Al pedirlo, la cuenta queda
desactivada de inmediato: deja de recibir y nadie puede entrar. El borrado definitivo lo hace
el administrador general desde su panel.
"""

from fastapi import APIRouter, Depends, HTTPException, Request

from app.alcance import exigir_alcance
from app.sesion import admin_actual, auditar
from app.validacion import texto_limpio

router = APIRouter(prefix="/api/solicitudes", tags=["solicitudes"])


@router.get("")
async def listar(request: Request, admin: dict = Depends(admin_actual)):
    filas = await request.app.state.db.fetch(
        """SELECT id, tipo, objetivo, motivo, estado, creado_en, resuelto_en FROM pd_solicitudes
            WHERE dominio = ANY($1::varchar[]) ORDER BY creado_en DESC LIMIT 100""", admin["dominios"])
    return [dict(f) for f in filas]


@router.post("/eliminar-cuenta", status_code=201)
async def pedir_eliminacion(request: Request, admin: dict = Depends(admin_actual)):
    datos = await request.json()
    cuenta = str(datos.get("cuenta", "")).strip().lower()
    dominio = exigir_alcance(admin, cuenta)
    db = request.app.state.db
    if not await db.fetchval("SELECT 1 FROM mailbox WHERE username = $1", cuenta):
        raise HTTPException(404, "No encontrado")
    if await db.fetchval(
            "SELECT 1 FROM pd_solicitudes WHERE objetivo = $1 AND tipo = 'eliminar_cuenta' AND estado = 'pendiente'", cuenta):
        raise HTTPException(409, "Ya hay una solicitud pendiente para esa cuenta")
    motivo = texto_limpio(datos.get("motivo"), 500)
    async with db.acquire() as con, con.transaction():
        await con.execute("UPDATE mailbox SET active = false, modified = NOW() WHERE username = $1", cuenta)
        nueva = await con.fetchval(
            """INSERT INTO pd_solicitudes (admin_id, admin_username, tipo, objetivo, dominio, motivo)
               VALUES ($1, $2, 'eliminar_cuenta', $3, $4, $5) RETURNING id""",
            admin["id"], admin["username"], cuenta, dominio, motivo)
    await auditar(request, admin, "cuenta_pedir_eliminacion", cuenta, {"motivo": motivo})
    return {"id": nueva, "estado": "pendiente"}
