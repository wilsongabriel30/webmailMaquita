"""Panel · Flota Maquita: códigos de alta de un solo uso (= garantía de «solo equipos propios»).

Solo Tecnología los crea. Formato `MQF-XXXX-XXXX-XXXX` (Crockford base32, 60 bits), se muestran UNA vez
y en la base queda solo su SHA-256 (misma normalización que el backend del correo).
"""

from __future__ import annotations

import hashlib
import secrets

from fastapi import APIRouter, Body, Depends, HTTPException, Request

from app.auth.dependencies import require_operador
from app.flota.comun import anotar, auditar, db, texto

router = APIRouter(prefix="/api/flota/codigos", tags=["flota"])
_CROCKFORD = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"


def _nuevo() -> tuple[str, str, str]:
    """(código para mostrar, prefijo, huella)."""
    s = "".join(secrets.choice(_CROCKFORD) for _ in range(12))
    return f"MQF-{s[:4]}-{s[4:8]}-{s[8:]}", s[:4], hashlib.sha256(s.encode()).hexdigest()


@router.get("")
async def listar(request: Request, admin: dict = Depends(require_operador)):
    filas = await db(request).fetch(
        "SELECT c.id, c.prefijo, c.etiqueta, c.creado_por, c.creado_en, c.caduca_en, c.usado_en, c.ip_uso, "
        "c.anulado_en, c.anulado_por, c.equipo_id::text AS equipo_id, e.nombre AS equipo_nombre, "
        "CASE WHEN c.anulado_en IS NOT NULL THEN 'anulado' WHEN c.usado_en IS NOT NULL THEN 'usado' "
        "WHEN c.caduca_en <= NOW() THEN 'caducado' ELSE 'vigente' END AS estado "
        "FROM flota_codigos c LEFT JOIN flota_equipos e ON e.equipo_id = c.equipo_id "
        "ORDER BY c.creado_en DESC LIMIT 500")
    return {"codigos": [dict(f) for f in filas]}


@router.post("")
async def crear(request: Request, cuerpo: dict = Body(default={}), admin: dict = Depends(require_operador)):
    etiqueta = texto(cuerpo.get("etiqueta"), 120) or ""
    try:
        dias = int(cuerpo.get("dias_validez") or 7)
        cantidad = int(cuerpo.get("cantidad") or 1)
    except (TypeError, ValueError):
        raise HTTPException(400, "dias_validez y cantidad deben ser números")
    if not 1 <= dias <= 30 or not 1 <= cantidad <= 100:
        raise HTTPException(400, "Validez de 1 a 30 días y de 1 a 100 códigos por vez")
    nuevos = []
    async with db(request).acquire() as c, c.transaction():
        for _ in range(cantidad):
            codigo, prefijo, h = _nuevo()
            fila = await c.fetchrow(
                "INSERT INTO flota_codigos (codigo_hash, prefijo, etiqueta, creado_por, caduca_en) "
                "VALUES ($1,$2,$3,$4, NOW() + make_interval(days => $5)) RETURNING id, caduca_en",
                h, prefijo, etiqueta, admin["username"], dias)
            nuevos.append({"id": fila["id"], "codigo": codigo, "caduca_en": fila["caduca_en"]})
        await anotar(c, request, admin, "codigos_creados",
                     detalle={"cantidad": cantidad, "etiqueta": etiqueta, "dias": dias, "ids": [n["id"] for n in nuevos]})
    await auditar(request, admin, "flota_codigos_creados", etiqueta or "-", {"cantidad": cantidad, "dias": dias})
    return {"codigos": nuevos}


@router.delete("/{codigo_id}")
async def anular(codigo_id: int, request: Request, admin: dict = Depends(require_operador)):
    async with db(request).acquire() as c, c.transaction():
        ok = await c.fetchval(
            "UPDATE flota_codigos SET anulado_en=NOW(), anulado_por=$2 WHERE id=$1 AND anulado_en IS NULL "
            "AND usado_en IS NULL RETURNING id", codigo_id, admin["username"])
        if not ok:
            raise HTTPException(404, "Código no encontrado, ya usado o ya anulado")
        await anotar(c, request, admin, "codigo_anulado", detalle={"codigo_id": codigo_id})
    await auditar(request, admin, "flota_codigo_anulado", str(codigo_id))
    return {"ok": True}
