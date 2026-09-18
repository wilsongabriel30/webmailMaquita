"""Panel · Dispositivos (fase 4): reasignación de equipos con historial de custodia.

Un teléfono pasa de una persona a otra (jefe → subordinado → técnico) sin dejar de funcionar. Cada
reasignación cierra el tramo del custodio anterior y abre el del nuevo, así queda el rastro de quién
lo tuvo y cuándo. Opcionalmente pide el respaldo de cierre del custodio saliente antes del cambio.
"""

from fastapi import APIRouter, Depends, HTTPException, Request

from app.auth.dependencies import get_current_admin, require_role
from app.dispositivos.comun import auditar, db, texto
from app.dispositivos.perdido import _encolar, _equipo, _motivo

router = APIRouter(prefix="/api/dispositivos", tags=["dispositivos"])
_ADMIN = require_role("superadmin", "admin")


@router.get("/equipos/{equipo_id}/custodia")
async def historial(equipo_id: int, request: Request, admin: dict = Depends(get_current_admin)):
    filas = await db(request).fetch(
        "SELECT id, custodio_nombre, custodio_email, centro_costo, sede, desde, hasta, asignado_por, motivo "
        "FROM disp_custodia WHERE equipo_id = $1 ORDER BY desde DESC", equipo_id)
    return {"custodia": [dict(f) for f in filas]}


@router.post("/equipos/{equipo_id}/reasignar")
async def reasignar(equipo_id: int, request: Request, admin: dict = Depends(_ADMIN)):
    b = await request.json()
    e = await _equipo(request, equipo_id)
    nombre = texto(b.get("custodio_nombre"), 160)
    correo = texto(b.get("custodio_email"), 255)
    if not nombre and not correo:
        raise HTTPException(400, "Indique al menos el nombre o el correo del nuevo custodio")
    motivo = _motivo(b)
    centro = texto(b.get("centro_costo"), 120)
    sede = texto(b.get("sede"), 120)
    respaldo_cierre = bool(b.get("respaldo_cierre", True))
    async with db(request).acquire() as con, con.transaction():
        actual = await con.fetchrow(
            "SELECT custodio_nombre, custodio_email, centro_costo, sede, enrolado_en FROM disp_equipos WHERE id = $1", equipo_id)
        # Cierra el tramo abierto del custodio anterior (o crea uno histórico si nunca hubo).
        cerrado = await con.execute("UPDATE disp_custodia SET hasta = NOW() WHERE equipo_id = $1 AND hasta IS NULL", equipo_id)
        if cerrado.endswith(" 0") and (actual["custodio_nombre"] or actual["custodio_email"]):
            await con.execute(
                "INSERT INTO disp_custodia (equipo_id, custodio_nombre, custodio_email, centro_costo, sede, desde, hasta, asignado_por, motivo) "
                "VALUES ($1,$2,$3,$4,$5, COALESCE($6, NOW()), NOW(), $7, 'tramo previo al registro de reasignaciones')",
                equipo_id, actual["custodio_nombre"], actual["custodio_email"], actual["centro_costo"], actual["sede"],
                actual["enrolado_en"], admin["username"])
        await con.execute(
            "INSERT INTO disp_custodia (equipo_id, custodio_nombre, custodio_email, centro_costo, sede, asignado_por, motivo) "
            "VALUES ($1,$2,$3,$4,$5,$6,$7)", equipo_id, nombre, correo, centro, sede, admin["username"], motivo)
        await con.execute(
            "UPDATE disp_equipos SET custodio_nombre = $2, custodio_email = $3, "
            "centro_costo = COALESCE($4, centro_costo), sede = COALESCE($5, sede) WHERE id = $1",
            equipo_id, nombre, correo, centro, sede)
        if respaldo_cierre:
            await _encolar(con, equipo_id, "respaldar", {"tipo": "cierre"}, admin, f"reasignación: {motivo}")
    await auditar(request, admin, "dispositivo_reasignar", str(equipo_id),
                  {"de": actual["custodio_nombre"] or actual["custodio_email"], "a": nombre or correo, "motivo": motivo})
    return {"ok": True, "respaldo_cierre_encolado": respaldo_cierre}
