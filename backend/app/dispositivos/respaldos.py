"""Respaldos de los teléfonos (fase 3): incrementales, por contenido y cifrados en reposo.

Flujo: abrir instantánea → enviar el manifiesto (ruta, tamaño, SHA-256) → el servidor responde qué
contenidos le faltan → subirlos por trozos reanudables → cerrar. Lo que no cambió no se vuelve a
enviar. Restaurar: el mismo equipo lee sus instantáneas; otro equipo solo con una autorización
vigente creada en el panel (teléfono nuevo tras un robo o una reasignación).
"""

import asyncio
import json
import logging
import re
from datetime import datetime, timezone
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field, field_validator

from app.dispositivos import objetos
from app.dispositivos.respaldos_mantenimiento import depurar
from app.dispositivos.seguridad import equipo_actual, limitar

logger = logging.getLogger("dispositivos")
router = APIRouter(prefix="/api/dispositivos/respaldos", tags=["dispositivos"])

TROZO_SUGERIDO = 8 * objetos.TRAMA
TROZO_MAXIMO = 32 * objetos.TRAMA
CATEGORIAS = ("fotos", "videos", "documentos", "descargas", "contactos", "llamadas", "sms", "whatsapp", "apps", "ajustes", "otros")
_SHA = r"^[0-9a-f]{64}$"
_CONTROL = re.compile(r"[\x00-\x1f\x7f]")


class Inicio(BaseModel):
    tipo: Literal["programado", "manual", "cierre"] = "programado"
    version_app: Optional[str] = Field(None, max_length=40)


class ArchivoManifiesto(BaseModel):
    ruta: str = Field(..., min_length=1, max_length=1024)
    categoria: str = Field("otros", max_length=20)
    tamano: int = Field(..., ge=0, le=20 * 1024**3)
    sha256: str = Field(..., pattern=_SHA)
    mtime: Optional[str] = Field(None, max_length=40)

    @field_validator("ruta")
    @classmethod
    def _ruta_sana(cls, v: str) -> str:
        if _CONTROL.search(v) or v.startswith("/") or ".." in v.split("/"):
            raise ValueError("ruta no admitida")
        return v


class Manifiesto(BaseModel):
    archivos: list[ArchivoManifiesto] = Field(..., min_length=1, max_length=2000)


class Cierre(BaseModel):
    errores: list[str] = Field(default_factory=list, max_length=50)


def _fecha(v: Optional[str]):
    try:
        t = datetime.fromisoformat((v or "").replace("Z", "+00:00"))
        return t if t.tzinfo else t.replace(tzinfo=timezone.utc)
    except ValueError:
        return None


async def _respaldo_abierto(db, equipo: dict, rid: int):
    r = await db.fetchrow("SELECT id, tipo, estado, iniciado_en FROM disp_respaldos WHERE id = $1 AND equipo_id = $2", rid, equipo["id"])
    if r is None:
        raise HTTPException(404, "Respaldo no encontrado para este equipo")
    if r["estado"] != "abierto":
        raise HTTPException(409, "Ese respaldo ya está cerrado")
    return r


async def _origenes(db, equipo: dict) -> list[int]:
    """Equipos cuyas instantáneas puede leer este teléfono: él mismo y los autorizados desde el panel."""
    filas = await db.fetch(
        "SELECT origen_id FROM disp_restauraciones WHERE destino_id = $1 AND anulada_en IS NULL AND caduca_en > NOW()", equipo["id"])
    return [equipo["id"]] + [f["origen_id"] for f in filas]


@router.post("")
async def iniciar(request: Request, body: Inicio, equipo: dict = Depends(equipo_actual)):
    if not equipo.get("respaldo_activo", True):
        raise HTTPException(403, "El respaldo está desactivado para este equipo")
    await limitar(request, f"resp:{equipo['id']}", 30, 86400)
    try:
        await asyncio.to_thread(objetos.comprobar)
    except objetos.AlmacenNoDisponible as e:
        logger.error("almacen_respaldos_no_disponible | %s", e)
        raise HTTPException(503, "El almacén de respaldos no está disponible; se reintentará más tarde")
    db = request.app.state.db_pool
    await db.execute("UPDATE disp_respaldos SET estado = 'incompleto', cerrado_en = NOW() WHERE equipo_id = $1 AND estado = 'abierto'", equipo["id"])
    rid = await db.fetchval("INSERT INTO disp_respaldos (equipo_id, tipo, version_app) VALUES ($1,$2,$3) RETURNING id",
                            equipo["id"], body.tipo, body.version_app)
    usado = await db.fetchval("SELECT COALESCE(SUM(tamano), 0) FROM disp_objetos WHERE equipo_id = $1", equipo["id"])
    return {"id": rid, "trozo_bytes": TROZO_SUGERIDO, "trama_bytes": objetos.TRAMA, "trozo_maximo_bytes": TROZO_MAXIMO,
            "cuota_bytes": equipo.get("cuota_respaldo_gb", 64) * 1024**3, "usado_bytes": int(usado)}


@router.post("/{rid}/manifiesto")
async def manifiesto(rid: int, request: Request, body: Manifiesto, equipo: dict = Depends(equipo_actual)):
    db = request.app.state.db_pool
    await _respaldo_abierto(db, equipo, rid)
    cuota = equipo.get("cuota_respaldo_gb", 64) * 1024**3
    contenidos = {a.sha256: a.tamano for a in body.archivos if a.sha256 != objetos.SHA_VACIO}
    async with db.acquire() as con, con.transaction():
        await con.executemany(
            "INSERT INTO disp_respaldo_archivos (respaldo_id, ruta, categoria, sha256, tamano, mtime) VALUES ($1,$2,$3,$4,$5,$6) "
            "ON CONFLICT (respaldo_id, ruta) DO UPDATE SET categoria = EXCLUDED.categoria, sha256 = EXCLUDED.sha256, "
            "tamano = EXCLUDED.tamano, mtime = EXCLUDED.mtime",
            [(rid, a.ruta, a.categoria if a.categoria in CATEGORIAS else "otros", a.sha256, a.tamano, _fecha(a.mtime)) for a in body.archivos])
        await con.executemany(
            "INSERT INTO disp_objetos (equipo_id, sha256, tamano) VALUES ($1,$2,$3) ON CONFLICT (equipo_id, sha256) DO NOTHING",
            [(equipo["id"], s, t) for s, t in contenidos.items()])
        total = await con.fetchval("SELECT COALESCE(SUM(tamano), 0) FROM disp_objetos WHERE equipo_id = $1", equipo["id"])
        if total > cuota:
            raise HTTPException(413, f"El respaldo supera la cuota del equipo ({equipo.get('cuota_respaldo_gb', 64)} GB). Avise a Tecnología.")
        filas = await con.fetch(
            "SELECT sha256, tamano, recibido FROM disp_objetos WHERE equipo_id = $1 AND sha256 = ANY($2::bpchar[]) AND estado <> 'completo'",
            equipo["id"], list(contenidos))
    return {"faltan": [{"sha256": f["sha256"], "tamano": f["tamano"], "recibido": f["recibido"]} for f in filas]}


@router.put("/objetos/{sha}")
async def subir_trozo(sha: str, request: Request, offset: int = Query(..., ge=0), total: int = Query(..., ge=1),
                      equipo: dict = Depends(equipo_actual)):
    if not re.fullmatch(_SHA, sha):
        raise HTTPException(400, "SHA-256 inválido")
    await limitar(request, f"trozo:{equipo['id']}", 30000, 3600)
    db = request.app.state.db_pool
    obj = await db.fetchrow("SELECT tamano, recibido, estado FROM disp_objetos WHERE equipo_id = $1 AND sha256 = $2", equipo["id"], sha)
    if obj is None or obj["tamano"] != total:
        raise HTTPException(409, "Ese contenido no figura en el manifiesto de este equipo (o cambió de tamaño): envíe antes el manifiesto")
    if obj["estado"] == "completo":
        return {"recibido": total, "completo": True}
    if offset != obj["recibido"]:
        return JSONResponse(status_code=409, content={"detail": "Desfase: continúe desde `recibido`", "recibido": obj["recibido"]})

    datos = bytearray()
    async for parte in request.stream():
        datos += parte
        if len(datos) > TROZO_MAXIMO:
            raise HTTPException(413, "Trozo demasiado grande")
    fin = offset + len(datos)
    if not datos or fin > total or (len(datos) % objetos.TRAMA and fin != total):
        raise HTTPException(400, "El trozo debe ser múltiplo de 1 MiB, salvo el último, y no pasar del tamaño declarado")

    candado = f"disp:obj:{equipo['id']}:{sha}"
    if not await request.app.state.redis.set(candado, "1", nx=True, ex=300):
        raise HTTPException(409, "Ya hay una subida en curso de ese contenido")
    try:
        try:
            await asyncio.to_thread(objetos.anexar, equipo["id"], sha, offset, bytes(datos))
        except objetos.Desfase:
            await asyncio.to_thread(objetos.borrar, equipo["id"], sha)
            await db.execute("UPDATE disp_objetos SET recibido = 0 WHERE equipo_id = $1 AND sha256 = $2", equipo["id"], sha)
            return JSONResponse(status_code=409, content={"detail": "El contenido guardado no cuadra: empiece de nuevo", "recibido": 0})
        if fin < total:
            await db.execute("UPDATE disp_objetos SET recibido = $3 WHERE equipo_id = $1 AND sha256 = $2", equipo["id"], sha, fin)
            return {"recibido": fin, "completo": False}
        if not await asyncio.to_thread(objetos.verificar, equipo["id"], sha, total):
            await asyncio.to_thread(objetos.borrar, equipo["id"], sha)
            await db.execute("UPDATE disp_objetos SET recibido = 0 WHERE equipo_id = $1 AND sha256 = $2", equipo["id"], sha)
            raise HTTPException(422, "El contenido recibido no coincide con su SHA-256: vuelva a subirlo")
        await db.execute("UPDATE disp_objetos SET recibido = $3, estado = 'completo', completado_en = NOW() WHERE equipo_id = $1 AND sha256 = $2",
                         equipo["id"], sha, total)
        return {"recibido": total, "completo": True}
    finally:
        await request.app.state.redis.delete(candado)


@router.post("/{rid}/cerrar")
async def cerrar(rid: int, request: Request, body: Cierre, equipo: dict = Depends(equipo_actual)):
    db = request.app.state.db_pool
    r = await _respaldo_abierto(db, equipo, rid)
    por_categoria = await db.fetch(
        "SELECT categoria, count(*) AS archivos, COALESCE(SUM(tamano), 0) AS bytes FROM disp_respaldo_archivos WHERE respaldo_id = $1 GROUP BY categoria", rid)
    faltantes = await db.fetchval(
        """SELECT count(*) FROM disp_respaldo_archivos a WHERE a.respaldo_id = $1 AND a.sha256 <> $3 AND NOT EXISTS (
               SELECT 1 FROM disp_objetos o WHERE o.equipo_id = $2 AND o.sha256 = a.sha256 AND o.estado = 'completo')""",
        rid, equipo["id"], objetos.SHA_VACIO)
    nuevos = await db.fetchrow(
        "SELECT count(*) AS n, COALESCE(SUM(tamano), 0) AS b FROM disp_objetos WHERE equipo_id = $1 AND completado_en >= $2", equipo["id"], r["iniciado_en"])
    estado = "completo" if faltantes == 0 else "incompleto"
    resumen = {c["categoria"]: {"archivos": c["archivos"], "bytes": int(c["bytes"])} for c in por_categoria}
    await db.execute(
        """UPDATE disp_respaldos SET estado = $2, cerrado_en = NOW(), archivos_total = $3, bytes_total = $4, archivos_nuevos = $5,
               bytes_nuevos = $6, faltantes = $7, resumen = $8::jsonb, errores = $9::jsonb WHERE id = $1""",
        rid, estado, sum(c["archivos"] for c in por_categoria), sum(int(c["bytes"]) for c in por_categoria), nuevos["n"], int(nuevos["b"]),
        faltantes, json.dumps(resumen), json.dumps([e[:300] for e in body.errores]))
    if estado == "completo" and r["tipo"] == "cierre":
        await db.execute("UPDATE disp_equipos SET respaldo_cierre_en = NOW() WHERE id = $1", equipo["id"])
    pol = await db.fetchval("SELECT valor -> 'respaldo' ->> 'instantaneas' FROM disp_config WHERE clave = 'politica'")
    await depurar(db, equipo["id"], int(pol or 7))
    logger.info("respaldo_cerrado | equipo=%s | id=%s | estado=%s | faltantes=%s", equipo["id"], rid, estado, faltantes)
    return {"estado": estado, "faltantes": faltantes, "resumen": resumen}


# ── Restauración ─────────────────────────────────────────────────────────────────────────

@router.get("")
async def listar(request: Request, equipo: dict = Depends(equipo_actual)):
    db = request.app.state.db_pool
    filas = await db.fetch(
        """SELECT r.id, r.equipo_id, e.nombre AS equipo_nombre, e.modelo, r.tipo, r.cerrado_en, r.archivos_total, r.bytes_total, r.resumen
           FROM disp_respaldos r JOIN disp_equipos e ON e.id = r.equipo_id
           WHERE r.equipo_id = ANY($1::int[]) AND r.estado = 'completo' ORDER BY r.cerrado_en DESC LIMIT 60""", await _origenes(db, equipo))
    return {"respaldos": [{**dict(f), "resumen": json.loads(f["resumen"]) if isinstance(f["resumen"], str) else f["resumen"],
                           "propio": f["equipo_id"] == equipo["id"]} for f in filas]}


async def _respaldo_legible(db, equipo: dict, rid: int):
    r = await db.fetchrow("SELECT id, equipo_id FROM disp_respaldos WHERE id = $1 AND estado = 'completo'", rid)
    if r is None or r["equipo_id"] not in await _origenes(db, equipo):
        raise HTTPException(404, "Respaldo no encontrado o sin autorización de restauración vigente")
    return r


@router.get("/{rid}/manifiesto")
async def leer_manifiesto(rid: int, request: Request, despues_de: str = "", limite: int = Query(2000, ge=1, le=2000),
                          equipo: dict = Depends(equipo_actual)):
    db = request.app.state.db_pool
    r = await _respaldo_legible(db, equipo, rid)
    if r["equipo_id"] != equipo["id"] and not despues_de:
        await db.execute("INSERT INTO disp_eventos (equipo_id, tipo, detalle) VALUES ($1, 'restauracion', $2::jsonb)",
                         r["equipo_id"], json.dumps({"restaurado_en_equipo": equipo["id"], "respaldo": rid}))
    filas = await db.fetch(
        "SELECT ruta, categoria, sha256, tamano, mtime FROM disp_respaldo_archivos WHERE respaldo_id = $1 AND ruta > $2 ORDER BY ruta LIMIT $3",
        rid, despues_de, limite)
    return {"equipo_origen": r["equipo_id"], "archivos": [dict(f) for f in filas], "hay_mas": len(filas) == limite}


@router.get("/objetos/{sha}")
async def descargar(sha: str, request: Request, equipo_origen: Optional[int] = None, desde: int = Query(0, ge=0),
                    equipo: dict = Depends(equipo_actual)):
    if not re.fullmatch(_SHA, sha) or desde % objetos.TRAMA:
        raise HTTPException(400, "Parámetros inválidos (`desde` debe ser múltiplo de 1 MiB)")
    db = request.app.state.db_pool
    origen = equipo_origen or equipo["id"]
    if origen not in await _origenes(db, equipo):
        raise HTTPException(404, "Sin autorización de restauración vigente para ese equipo")
    tamano = await db.fetchval("SELECT tamano FROM disp_objetos WHERE equipo_id = $1 AND sha256 = $2 AND estado = 'completo'", origen, sha)
    if tamano is None or desde > tamano:
        raise HTTPException(404, "Contenido no disponible")
    return StreamingResponse(objetos.leer(origen, sha, desde), media_type="application/octet-stream",
                             headers={"Content-Length": str(tamano - desde), "Cache-Control": "no-store"})
