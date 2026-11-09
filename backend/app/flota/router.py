"""Endpoints que llama el AGENTE (tarea SYSTEM de Teams Maquita). Contrato T-88 (09/11/2026).

POST /api/flota/enrolar     sin sesión; {codigo, machine_guid, equipo, windows?, app?}
    200 {equipo_id, secreto, nuevo, sondeo_s}
    400 datos_invalidos · 404 codigo_desconocido · 410 codigo_usado_o_caducado · 429 demasiados_intentos
GET  /api/flota/ordenes?equipo_id=…   cabecera X-Flota-Secreto
    200 {equipo_id, hora_servidor, sondeo_s, ordenes: [{orden_id, kid, carga, firma}]}
    400 datos_invalidos · 401 credenciales_invalidas · 403 equipo_retirado
POST /api/flota/resultado   cabecera X-Flota-Secreto; {equipo_id, orden_id, estado, registro?, datos?}
    200 {ok, estado} · 400 · 401 · 403 · 404 orden_desconocida · 409 orden_cerrada

Errores siempre {"error": "<código>", "detail": "<texto>"}. La firma de las órdenes la pone el panel
al emitirlas; aquí solo se entregan tal cual se guardaron.
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from app.flota import credenciales

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/flota", tags=["flota"])

SONDEO_S = 900
ENROLAR_POR_HORA_IP = 20
ESTADOS_AGENTE = ("recibida", "ejecutando", "ok", "error", "rechazada")
FINALES = ("ok", "error", "rechazada", "anulada")
MAX_REGISTRO = 262144
MAX_DATOS = 262144


def _error(estado: int, codigo: str, texto: str) -> JSONResponse:
    return JSONResponse(status_code=estado, content={"error": codigo, "detail": texto})


def _ip(request: Request) -> str:
    return request.headers.get(
        "X-Real-IP", request.client.host if request.client else ""
    )


def _uuid(v) -> str | None:
    try:
        return str(uuid.UUID(str(v)))
    except (ValueError, TypeError, AttributeError):
        return None


def _texto(v, n: int) -> str:
    return "".join(c for c in str(v or "") if c.isprintable())[:n].strip()


async def _cuerpo(request: Request) -> dict:
    try:
        b = await request.json()
    except Exception:
        return {}
    return b if isinstance(b, dict) else {}


async def anotar(
    db, *, actor, accion, equipo_id=None, orden_id=None, detalle=None, ip=""
) -> None:
    try:
        await db.execute(
            "INSERT INTO flota_registro (equipo_id, orden_id, actor, accion, detalle, ip) "
            "VALUES ($1, $2, $3, $4, $5::jsonb, $6)",
            equipo_id,
            orden_id,
            actor,
            accion,
            (
                json.dumps(detalle, ensure_ascii=False, default=str)
                if detalle is not None
                else None
            ),
            ip,
        )
    except Exception:
        logger.exception("flota_registro_fallo | %s", accion)


async def _limite(redis, clave: str, maximo: int, ventana_s: int) -> bool:
    try:
        n = await redis.incr(clave)
        if n == 1:
            await redis.expire(clave, ventana_s)
        return int(n) > maximo
    except Exception:
        return False  # sin Redis no se bloquea: el código de un uso ya protege


@router.post("/enrolar")
async def enrolar(request: Request):
    db, ip = request.app.state.db_pool, _ip(request)
    if await _limite(
        request.app.state.redis, f"flota:enrolar:{ip}", ENROLAR_POR_HORA_IP, 3600
    ):
        return _error(
            429,
            "demasiados_intentos",
            "Demasiados intentos desde esta red. Reintenta en una hora.",
        )
    b = await _cuerpo(request)
    codigo = credenciales.normalizar_codigo(b.get("codigo"))
    guid = _uuid(b.get("machine_guid"))
    nombre = _texto(b.get("equipo"), 63).upper()
    if not codigo or not guid or not nombre:
        return _error(
            400,
            "datos_invalidos",
            "Faltan el código, el identificador o el nombre del equipo.",
        )
    windows, app_v = _texto(b.get("windows"), 120), _texto(b.get("app"), 20)

    async with db.acquire() as c, c.transaction():
        cod = await c.fetchrow(
            "SELECT id, etiqueta, usado_en, anulado_en, caduca_en <= NOW() AS caducado "
            "FROM flota_codigos WHERE codigo_hash = $1 FOR UPDATE",
            credenciales.huella(codigo),
        )
        if cod is None:
            await anotar(
                c,
                actor=f"equipo:{nombre}",
                accion="enrolar_codigo_desconocido",
                detalle={"machine_guid": guid},
                ip=ip,
            )
            return _error(404, "codigo_desconocido", "Código de alta desconocido.")
        if cod["usado_en"] or cod["anulado_en"] or cod["caducado"]:
            return _error(
                410,
                "codigo_usado_o_caducado",
                "El código ya se usó, se anuló o caducó. Pide otro a Tecnología.",
            )
        secreto = credenciales.nuevo_secreto()
        previo = await c.fetchrow(
            "SELECT equipo_id, estado FROM flota_equipos WHERE machine_guid = $1", guid
        )
        if previo:
            equipo_id = str(previo["equipo_id"])
            await c.execute(
                "UPDATE flota_equipos SET nombre=$2, secreto_hash=$3, estado='activo', windows=$4, version_app=$5, "
                "codigo_id=$6, etiqueta=CASE WHEN $7 <> '' THEN $7 ELSE etiqueta END, reenrolado_en=NOW(), "
                "retirado_en=NULL, retirado_por='', motivo_retiro='', ultima_ip=$8 WHERE equipo_id=$1",
                previo["equipo_id"],
                nombre,
                credenciales.huella(secreto),
                windows,
                app_v,
                cod["id"],
                cod["etiqueta"],
                ip,
            )
        else:
            equipo_id = str(uuid.uuid4())
            await c.execute(
                "INSERT INTO flota_equipos (equipo_id, machine_guid, nombre, etiqueta, secreto_hash, windows, "
                "version_app, codigo_id, ultima_ip) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9)",
                equipo_id,
                guid,
                nombre,
                cod["etiqueta"],
                credenciales.huella(secreto),
                windows,
                app_v,
                cod["id"],
                ip,
            )
        await c.execute(
            "UPDATE flota_codigos SET usado_en=NOW(), equipo_id=$2, ip_uso=$3 WHERE id=$1",
            cod["id"],
            equipo_id,
            ip,
        )
        await anotar(
            c,
            actor=f"equipo:{nombre}",
            accion="reenrolado" if previo else "enrolado",
            equipo_id=equipo_id,
            detalle={
                "codigo_id": cod["id"],
                "machine_guid": guid,
                "app": app_v,
                "windows": windows,
                "estado_anterior": previo["estado"] if previo else None,
            },
            ip=ip,
        )
    logger.info(
        "flota_enrolado | equipo=%s | id=%s | nuevo=%s", nombre, equipo_id, not previo
    )
    return {
        "equipo_id": equipo_id,
        "secreto": secreto,
        "nuevo": not previo,
        "sondeo_s": SONDEO_S,
    }


async def _equipo(
    request: Request, equipo_id_crudo
) -> tuple[dict | None, JSONResponse | None]:
    equipo_id = _uuid(equipo_id_crudo)
    if not equipo_id:
        return None, _error(400, "datos_invalidos", "equipo_id con formato incorrecto.")
    fila = await request.app.state.db_pool.fetchrow(
        "SELECT equipo_id::text AS equipo_id, nombre, secreto_hash, estado FROM flota_equipos WHERE equipo_id = $1",
        equipo_id,
    )
    if not fila or not credenciales.secreto_valido(
        request.headers.get("X-Flota-Secreto", ""), fila["secreto_hash"]
    ):
        logger.warning(
            "flota_credenciales_invalidas | id=%s | ip=%s", equipo_id, _ip(request)
        )
        return None, _error(
            401, "credenciales_invalidas", "Equipo no enrolado o secreto incorrecto."
        )
    if fila["estado"] != "activo":
        return None, _error(
            403, "equipo_retirado", "Este equipo fue retirado de la flota."
        )
    return dict(fila), None


@router.get("/ordenes")
async def ordenes(request: Request):
    eq, err = await _equipo(request, request.query_params.get("equipo_id"))
    if err:
        return err
    db, ip = request.app.state.db_pool, _ip(request)
    version = _texto(request.headers.get("X-Maquita-App"), 20)
    await db.execute(
        "UPDATE flota_equipos SET ultimo_sondeo=NOW(), ultima_ip=$2, "
        "version_app=CASE WHEN $3 <> '' THEN $3 ELSE version_app END WHERE equipo_id=$1",
        eq["equipo_id"],
        ip,
        version,
    )
    filas = await db.fetch(
        "UPDATE flota_ordenes SET estado='entregada', entregas=entregas+1, entregada_en=COALESCE(entregada_en, NOW()) "
        "WHERE orden_id IN (SELECT orden_id FROM flota_ordenes WHERE equipo_id=$1 AND estado IN ('pendiente','entregada') "
        "AND caduca_en > NOW() ORDER BY emitida_en LIMIT 20) "
        "RETURNING orden_id::text AS orden_id, kid, carga, firma, entregas, emitida_en",
        eq["equipo_id"],
    )
    filas = sorted(filas, key=lambda f: f["emitida_en"])
    for f in filas:
        if f["entregas"] == 1:
            await anotar(
                db,
                actor="servidor",
                accion="orden_entregada",
                equipo_id=eq["equipo_id"],
                orden_id=f["orden_id"],
                ip=ip,
            )
    return {
        "equipo_id": eq["equipo_id"],
        "hora_servidor": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "sondeo_s": SONDEO_S,
        "ordenes": [
            {
                "orden_id": f["orden_id"],
                "kid": f["kid"],
                "carga": f["carga"],
                "firma": f["firma"],
            }
            for f in filas
        ],
    }


@router.post("/resultado")
async def resultado(request: Request):
    b = await _cuerpo(request)
    eq, err = await _equipo(request, b.get("equipo_id"))
    if err:
        return err
    orden_id, estado = _uuid(b.get("orden_id")), str(b.get("estado") or "")
    if not orden_id or estado not in ESTADOS_AGENTE:
        return _error(
            400,
            "datos_invalidos",
            f"orden_id inválido o estado fuera de {list(ESTADOS_AGENTE)}.",
        )
    registro = str(b.get("registro") or "")[:MAX_REGISTRO]
    datos = b.get("datos")
    datos_json = json.dumps(datos, ensure_ascii=False) if datos is not None else None
    if datos_json and len(datos_json) > MAX_DATOS:
        return _error(400, "datos_invalidos", "«datos» supera 256 KB.")
    db, ip = request.app.state.db_pool, _ip(request)

    async with db.acquire() as c, c.transaction():
        o = await c.fetchrow(
            "SELECT tipo, estado FROM flota_ordenes WHERE orden_id=$1 AND equipo_id=$2 FOR UPDATE",
            orden_id,
            eq["equipo_id"],
        )
        if o is None:
            return _error(
                404, "orden_desconocida", "Esa orden no existe para este equipo."
            )
        if o["estado"] in FINALES:
            if o["estado"] == estado:
                return {
                    "ok": True,
                    "estado": estado,
                }  # reintento del agente tras un corte de red
            return _error(
                409, "orden_cerrada", f"La orden ya está cerrada ({o['estado']})."
            )
        await c.execute(
            "UPDATE flota_ordenes SET estado=$2, resultado_en=NOW(), "
            "registro=right(registro || CASE WHEN $3 = '' THEN '' ELSE $3 || E'\\n' END, $5), "
            "datos=COALESCE($4::jsonb, datos) WHERE orden_id=$1",
            orden_id,
            estado,
            registro,
            datos_json,
            MAX_REGISTRO,
        )
        if estado == "ok" and o["tipo"] == "inventario" and isinstance(datos, dict):
            await c.execute(
                "UPDATE flota_equipos SET inventario=$2::jsonb, inventario_en=NOW() WHERE equipo_id=$1",
                eq["equipo_id"],
                datos_json,
            )
        await anotar(
            c,
            actor=f"equipo:{eq['nombre']}",
            accion=f"resultado_{estado}",
            equipo_id=eq["equipo_id"],
            orden_id=orden_id,
            detalle={"tipo": o["tipo"], "registro": registro[:2000]},
            ip=ip,
        )
    return {"ok": True, "estado": estado}
