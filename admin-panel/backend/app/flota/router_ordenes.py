"""Panel · Flota Maquita: emitir órdenes FIRMADAS, anularlas, verlas y consultar el registro.

Formato de la carga firmada (contrato T-88, v1) — ver `firma.py`:
    {"proposito": "maquita-flota-orden", "v": 1, "kid": "...", "orden_id": "<uuid>", "equipo_id": "<uuid>",
     "machine_guid": "<uuid>", "tipo": "...", "parametros": {...}, "emitida_en": "...Z", "caduca_en": "...Z",
     "emitida_por": "<usuario del panel>"}

Túnel de soporte (T-120): `abrir_tunel_soporte` lleva además sus campos PLANOS junto a `tipo` y, si procede,
la clave privada en `clave` (ver `cargas.py`). Esa clave no se guarda en `parametros`, no se anota en ningún
registro y no se devuelve al navegador; de la carga guardada la retira `tunel_purga.py`.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Body, Depends, HTTPException, Query, Request

from app.auth.dependencies import require_operador
from app.flota import cargas, catalogo, firma, tunel, tunel_parametros, tunel_purga
from app.flota.comun import anotar, auditar, con_json, db, texto, uuid_o_400

router = APIRouter(prefix="/api/flota", tags=["flota"])
MAX_EQUIPOS = 500
VIVAS = ("pendiente", "entregada", "recibida", "ejecutando")


def _z(momento: datetime) -> str:
    return momento.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


@router.post("/ordenes")
async def emitir(request: Request, cuerpo: dict = Body(default={}), admin: dict = Depends(require_operador)):
    tipo = str(cuerpo.get("tipo") or "")
    es_tunel = tipo in tunel.aj.TIPOS
    recibidos = cuerpo.get("parametros") if isinstance(cuerpo.get("parametros"), dict) else {}
    parametros = catalogo.validar(tipo, recibidos, str(cuerpo.get("confirmacion") or ""))
    motivo = texto(cuerpo.get("motivo"), 300)
    if not motivo or len(motivo) < 5:
        raise HTTPException(400, "Indique el motivo de la orden (mínimo 5 caracteres): queda en el registro")
    try:
        horas = tunel_parametros.validez(cuerpo) if es_tunel else int(cuerpo.get("horas_validez") or 72)
    except (TypeError, ValueError):
        raise HTTPException(400, "horas_validez debe ser un número")
    if not 1 <= horas <= 720:
        raise HTTPException(400, "Validez de 1 a 720 horas")
    if not firma.disponible():
        raise HTTPException(503, "Falta la clave de firma de Flota en el servidor: no se puede emitir ninguna orden")

    base = db(request)
    if cuerpo.get("todos") is True:
        destinos = await base.fetch("SELECT equipo_id::text AS equipo_id, machine_guid::text AS machine_guid, nombre "
                                    "FROM flota_equipos WHERE estado='activo' ORDER BY nombre")
    else:
        ids = list(dict.fromkeys(uuid_o_400(i, "equipo_id") for i in (cuerpo.get("equipos") or [])))
        if not ids:
            raise HTTPException(400, "Elija al menos un equipo (o «todos»)")
        destinos = await base.fetch("SELECT equipo_id::text AS equipo_id, machine_guid::text AS machine_guid, nombre "
                                    "FROM flota_equipos WHERE estado='activo' AND equipo_id = ANY($1::uuid[])", ids)
        if len(destinos) != len(ids):
            raise HTTPException(400, "Alguno de los equipos no está enrolado o fue retirado")
    if not destinos:
        raise HTTPException(400, "No hay equipos activos en la flota")
    if len(destinos) > MAX_EQUIPOS:
        raise HTTPException(400, f"Máximo {MAX_EQUIPOS} equipos por orden")
    if es_tunel:
        tunel.un_solo_equipo(cuerpo, destinos)

    ahora = datetime.now(timezone.utc).replace(microsecond=0)
    caduca = ahora + timedelta(hours=horas)
    emitidas = []
    async with base.acquire() as c, c.transaction():
        for d in destinos:
            orden_id = str(uuid.uuid4())
            firmados, clave = parametros, None  # `parametros` es lo que se guarda y se muestra: nunca lleva la clave
            if tipo == tunel.aj.ABRIR:
                firmados, clave, parametros = await tunel.preparar(c, d, parametros, recibidos.get("clave"))
            carga = cargas.construir(orden_id=orden_id, equipo_id=d["equipo_id"], machine_guid=d["machine_guid"],
                                     tipo=tipo, parametros=firmados, emitida_en=_z(ahora), caduca_en=_z(caduca),
                                     emitida_por=admin["username"], clave=clave)
            carga_b64, firma_b64 = firma.firmar(carga)
            del carga, clave
            await c.execute(
                "INSERT INTO flota_ordenes (orden_id, equipo_id, tipo, parametros, kid, carga, firma, emitida_por, "
                "motivo, emitida_en, caduca_en) VALUES ($1,$2,$3,$4::jsonb,$5,$6,$7,$8,$9,$10,$11)",
                orden_id, d["equipo_id"], tipo, json.dumps(parametros), firma.KID, carga_b64, firma_b64,
                admin["username"], motivo, ahora, caduca)
            await anotar(c, request, admin, "orden_emitida", equipo_id=d["equipo_id"], orden_id=orden_id,
                         detalle={"tipo": tipo, "parametros": parametros, "motivo": motivo, "caduca_en": _z(caduca)})
            emitidas.append({"orden_id": orden_id, "equipo_id": d["equipo_id"], "nombre": d["nombre"]})
    if tipo == tunel.aj.CERRAR:  # en modo automático, la clave del equipo deja de valer desde ya
        broker = await tunel.revocar(destinos[0])
        if broker:
            await anotar(base, request, admin, "tunel_clave_revocada", equipo_id=destinos[0]["equipo_id"],
                         orden_id=emitidas[0]["orden_id"], detalle=broker)
    await auditar(request, admin, "flota_orden_emitida", tipo,
                  {"equipos": len(emitidas), "motivo": motivo, "parametros": parametros})
    return {"emitidas": emitidas, "caduca_en": _z(caduca)}


@router.get("/ordenes")
async def listar(request: Request, admin: dict = Depends(require_operador),
                 equipo_id: str | None = None, estado: str | None = None, limite: int = Query(200, ge=1, le=1000)):
    filtros, args = [], []
    if equipo_id:
        args.append(uuid_o_400(equipo_id, "equipo_id"))
        filtros.append(f"o.equipo_id = ${len(args)}")
    if estado:
        args.append(estado)
        filtros.append(f"o.estado = ${len(args)}")
    args.append(limite)
    donde = ("WHERE " + " AND ".join(filtros)) if filtros else ""
    filas = await db(request).fetch(
        "SELECT o.orden_id::text AS orden_id, o.equipo_id::text AS equipo_id, e.nombre, o.tipo, o.parametros, o.estado, "
        "o.motivo, o.emitida_por, o.emitida_en, o.caduca_en, o.entregas, o.entregada_en, o.resultado_en, "
        "left(o.registro, 4000) AS registro, o.anulada_por, "
        "(o.estado IN ('pendiente','entregada') AND o.caduca_en <= NOW()) AS caducada "
        f"FROM flota_ordenes o JOIN flota_equipos e ON e.equipo_id = o.equipo_id {donde} "
        f"ORDER BY o.emitida_en DESC LIMIT ${len(args)}", *args)
    return {"ordenes": [con_json(f) for f in filas]}


@router.delete("/ordenes/{orden_id}")
async def anular(orden_id: str, request: Request, admin: dict = Depends(require_operador)):
    """Deja de entregarla. Si el agente ya la recibió puede estar ejecutándola: su resultado posterior
    responde 409 y queda en el registro."""
    orden_id = uuid_o_400(orden_id, "orden_id")
    async with db(request).acquire() as c, c.transaction():
        fila = await c.fetchrow(
            "UPDATE flota_ordenes SET estado='anulada', anulada_en=NOW(), anulada_por=$2 "
            "WHERE orden_id=$1 AND estado = ANY($3::text[]) RETURNING equipo_id::text AS equipo_id, tipo",
            orden_id, admin["username"], list(VIVAS))
        if not fila:
            raise HTTPException(404, "Orden no encontrada o ya cerrada")
        await anotar(c, request, admin, "orden_anulada", equipo_id=fila["equipo_id"], orden_id=orden_id,
                     detalle={"tipo": fila["tipo"]})
    await auditar(request, admin, "flota_orden_anulada", orden_id, {"tipo": fila["tipo"]})
    if fila["tipo"] == tunel.aj.ABRIR:
        await tunel_purga.purgar_sin_fallar(db(request))  # la clave que llevara se retira ya
    return {"ok": True}


@router.get("/registro")
async def registro(request: Request, admin: dict = Depends(require_operador),
                   equipo_id: str | None = None, limite: int = Query(300, ge=1, le=2000)):
    args: list = []
    donde = ""
    if equipo_id:
        args.append(uuid_o_400(equipo_id, "equipo_id"))
        donde = "WHERE r.equipo_id = $1"
    args.append(limite)
    filas = await db(request).fetch(
        "SELECT r.id, r.momento, r.equipo_id::text AS equipo_id, e.nombre, r.orden_id::text AS orden_id, r.actor, "
        f"r.accion, r.detalle, r.ip FROM flota_registro r LEFT JOIN flota_equipos e ON e.equipo_id = r.equipo_id {donde} "
        f"ORDER BY r.momento DESC LIMIT ${len(args)}", *args)
    return {"registro": [con_json(f) for f in filas]}
