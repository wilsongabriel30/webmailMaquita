"""Dar de baja un sitio: el administrador de dominio la pide y el administrador general la confirma.

Borrar un sitio no tiene vuelta atrás para quien lo usa (archivos, base de datos, FTP), así que el
portal no puede hacerlo: el intermediario ni siquiera acepta esa orden. Al pedirla no se apaga
nada; el sitio sigue publicado hasta que el superadministrador la confirma en el panel general.
"""

from fastapi import APIRouter, Depends, HTTPException, Request

from app.sesion import admin_actual, auditar
from app.sitios.comun import cuerpo, exigir_sitio, sitio_existente
from app.validacion import texto_limpio

router = APIRouter(prefix="/api/sitios", tags=["sitios"])


@router.post("/{sitio}/baja", status_code=201)
async def pedir_baja(sitio: str, request: Request, admin: dict = Depends(admin_actual)):
    sitio, dominio = exigir_sitio(admin, sitio)
    await sitio_existente(request, admin, sitio)
    motivo = texto_limpio((await cuerpo(request)).get("motivo"), 500)
    db = request.app.state.db
    if await db.fetchval(
            "SELECT 1 FROM pd_solicitudes WHERE objetivo = $1 AND tipo = 'baja_sitio' AND estado = 'pendiente'", sitio):
        raise HTTPException(409, "Ya hay una solicitud de baja pendiente para ese sitio")
    nueva = await db.fetchval(
        """INSERT INTO pd_solicitudes (admin_id, admin_username, tipo, objetivo, dominio, motivo)
           VALUES ($1, $2, 'baja_sitio', $3, $4, $5) RETURNING id""",
        admin["id"], admin["username"], sitio, dominio, motivo)
    await auditar(request, admin, "sitio_pedir_baja", sitio, {"motivo": motivo})
    return {"id": nueva, "estado": "pendiente"}
