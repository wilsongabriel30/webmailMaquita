"""Panel · Flota Maquita: estado del túnel de soporte de un equipo y auditoría de todas las aperturas.

Las órdenes se emiten por `POST /api/flota/ordenes` (tipos `abrir_tunel_soporte` y `cerrar_tunel_soporte`).
Aquí solo se lee. Nada de lo que se devuelve contiene la clave privada: se lee la columna `parametros`,
nunca la carga firmada.
"""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager

from fastapi import APIRouter, Depends, Query, Request

from app.auth.dependencies import require_operador
from app.flota import tunel_ajustes as aj
from app.flota import tunel_estado, tunel_puertos, tunel_purga
from app.flota.comun import con_json, db, uuid_o_400


@asynccontextmanager
async def _purga_periodica(app):
    """Mientras el panel está en marcha, retira cada minuto las claves que ya no hacen falta."""
    tarea = asyncio.create_task(tunel_purga.ciclo(app.state.db))
    try:
        yield
    finally:
        tarea.cancel()


router = APIRouter(prefix="/api/flota/tunel", tags=["flota"], lifespan=_purga_periodica)

_CIERRE = (
    "SELECT c.orden_id::text AS cierre_orden_id, c.emitida_por AS cierre_por, c.emitida_en AS cierre_emitido_en, "
    "c.estado AS cierre_estado, c.resultado_en AS cierre_en, c.motivo AS cierre_motivo, "
    "(c.estado IN ('pendiente','entregada') AND c.caduca_en <= NOW()) AS cierre_caducado "
    f"FROM flota_ordenes c WHERE c.equipo_id = o.equipo_id AND c.tipo = '{aj.CERRAR}' AND c.estado <> 'anulada' "
    "AND c.emitida_en >= o.emitida_en AND c.emitida_en < COALESCE(sig.emitida_en, 'infinity') "
    "ORDER BY c.emitida_en LIMIT 1"
)
_SIGUIENTE = (
    "SELECT n.emitida_en, CASE WHEN n.estado = 'ok' THEN n.resultado_en END AS reemplazado_en "
    f"FROM flota_ordenes n WHERE n.equipo_id = o.equipo_id AND n.tipo = '{aj.ABRIR}' AND n.emitida_en > o.emitida_en "
    "ORDER BY n.emitida_en LIMIT 1"
)
SQL_APERTURAS = (
    "SELECT o.orden_id::text AS orden_id, o.equipo_id::text AS equipo_id, e.nombre, o.parametros, o.estado, o.motivo, "
    "o.emitida_por, o.emitida_en, o.caduca_en, o.entregada_en, o.resultado_en, o.datos, "
    "left(o.registro, 2000) AS registro, (o.estado IN ('pendiente','entregada') AND o.caduca_en <= NOW()) AS caducada, "
    "sig.reemplazado_en, c.*, r.ip AS ip_panel "
    "FROM flota_ordenes o JOIN flota_equipos e ON e.equipo_id = o.equipo_id "
    f"LEFT JOIN LATERAL ({_SIGUIENTE}) sig ON true LEFT JOIN LATERAL ({_CIERRE}) c ON true "
    "LEFT JOIN LATERAL (SELECT ip FROM flota_registro r WHERE r.orden_id = o.orden_id AND r.accion = 'orden_emitida' "
    "ORDER BY r.id LIMIT 1) r ON true "
    f"WHERE o.tipo = '{aj.ABRIR}' {{filtro}} ORDER BY o.emitida_en DESC LIMIT {{limite}}"
)


async def _aperturas(base, equipo_id: str | None, limite: int) -> list[dict]:
    await tunel_purga.purgar_sin_fallar(base)
    args: list = [equipo_id] if equipo_id else []
    args.append(limite)
    sql = SQL_APERTURAS.format(
        filtro="AND o.equipo_id = $1" if equipo_id else "", limite=f"${len(args)}"
    )
    return [tunel_estado.resumir(con_json(f)) for f in await base.fetch(sql, *args)]


@router.get("/auditoria")
async def auditoria(
    request: Request,
    admin: dict = Depends(require_operador),
    equipo_id: str | None = None,
    limite: int = Query(200, ge=1, le=1000),
):
    """Quién abrió un túnel, a qué equipo, cuándo, con qué resultado y cuánto duró."""
    equipo_id = uuid_o_400(equipo_id, "equipo_id") if equipo_id else None
    return {"tuneles": await _aperturas(db(request), equipo_id, limite)}


@router.get("/estado")
async def estado(
    request: Request, equipo_id: str, admin: dict = Depends(require_operador)
):
    """Última apertura del equipo (para la cuenta atrás) y el puerto que tiene o se le daría."""
    equipo_id = uuid_o_400(equipo_id, "equipo_id")
    base = db(request)
    ultimas = await _aperturas(base, equipo_id, 1)
    asignados = await tunel_puertos.mapa(base)
    propio = asignados.get(equipo_id, {}).get("puerto")
    return {
        "tunel": ultimas[0] if ultimas else None,
        "puerto_asignado": propio,
        "puerto_sugerido": propio
        or tunel_puertos.menor_libre(tunel_puertos.de_otros(asignados, equipo_id)),
        "ajustes": aj.para_panel(),
    }
