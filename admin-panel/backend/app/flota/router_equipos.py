"""Panel · Flota Maquita: inventario, ficha de equipo, retiro y datos de la firma."""

from __future__ import annotations

from fastapi import APIRouter, Body, Depends, HTTPException, Request

from app.auth.dependencies import require_operador
from app.flota import catalogo, firma, inventario
from app.flota.comun import anotar, auditar, con_json, db, texto, uuid_o_400

router = APIRouter(prefix="/api/flota", tags=["flota"])


@router.get("/equipos")
async def equipos(request: Request, admin: dict = Depends(require_operador)):
    return await inventario.listar(db(request))


@router.get("/catalogo")
async def catalogo_y_firma(request: Request, admin: dict = Depends(require_operador)):
    datos = {"tipos": catalogo.para_panel(), "kid": firma.KID, "firma_disponible": firma.disponible()}
    if datos["firma_disponible"]:
        datos["clave_publica"] = firma.publica_pem()
    return datos


@router.get("/equipos/{equipo_id}")
async def ficha(equipo_id: str, request: Request, admin: dict = Depends(require_operador)):
    equipo_id = uuid_o_400(equipo_id, "equipo_id")
    base = db(request)
    e = await base.fetchrow(
        "SELECT equipo_id::text AS equipo_id, machine_guid::text AS machine_guid, nombre, etiqueta, estado, windows, "
        "version_app, inventario, inventario_en, enrolado_en, reenrolado_en, ultimo_sondeo, ultima_ip, "
        "retirado_en, retirado_por, motivo_retiro, codigo_id FROM flota_equipos WHERE equipo_id = $1", equipo_id)
    if not e:
        raise HTTPException(404, "Equipo no enrolado")
    ordenes = await base.fetch(
        "SELECT orden_id::text AS orden_id, tipo, parametros, estado, motivo, emitida_por, emitida_en, caduca_en, "
        "entregas, entregada_en, resultado_en, registro, datos, (estado IN ('pendiente','entregada') AND caduca_en <= NOW()) AS caducada "
        "FROM flota_ordenes WHERE equipo_id = $1 ORDER BY emitida_en DESC LIMIT 50", equipo_id)
    registro = await base.fetch(
        "SELECT id, momento, orden_id::text AS orden_id, actor, accion, detalle, ip FROM flota_registro "
        "WHERE equipo_id = $1 ORDER BY momento DESC LIMIT 200", equipo_id)
    return {"equipo": con_json(e), "ordenes": [con_json(o) for o in ordenes], "registro": [con_json(r) for r in registro]}


@router.post("/equipos/{equipo_id}/retirar")
async def retirar(equipo_id: str, request: Request, cuerpo: dict = Body(default={}),
                  admin: dict = Depends(require_operador)):
    """Saca el equipo de la flota: deja de recibir órdenes (el agente recibe 403 equipo_retirado) y se
    anulan sus órdenes vivas. Para volver a gestionarlo hace falta un código de alta nuevo."""
    equipo_id = uuid_o_400(equipo_id, "equipo_id")
    motivo = texto(cuerpo.get("motivo"), 300)
    if not motivo or len(motivo) < 5:
        raise HTTPException(400, "Indique el motivo del retiro (mínimo 5 caracteres)")
    async with db(request).acquire() as c, c.transaction():
        nombre = await c.fetchval(
            "UPDATE flota_equipos SET estado='retirado', retirado_en=NOW(), retirado_por=$2, motivo_retiro=$3 "
            "WHERE equipo_id=$1 AND estado='activo' RETURNING nombre", equipo_id, admin["username"], motivo)
        if nombre is None:
            raise HTTPException(404, "Equipo no encontrado o ya retirado")
        anuladas = await c.fetchval(
            "WITH a AS (UPDATE flota_ordenes SET estado='anulada', anulada_en=NOW(), anulada_por=$2 "
            "WHERE equipo_id=$1 AND estado IN ('pendiente','entregada','recibida','ejecutando') RETURNING 1) "
            "SELECT count(*) FROM a", equipo_id, admin["username"])
        await anotar(c, request, admin, "equipo_retirado", equipo_id=equipo_id,
                     detalle={"motivo": motivo, "ordenes_anuladas": anuladas})
    await auditar(request, admin, "flota_equipo_retirado", nombre, {"equipo_id": equipo_id, "motivo": motivo})
    return {"ok": True, "ordenes_anuladas": anuladas}
