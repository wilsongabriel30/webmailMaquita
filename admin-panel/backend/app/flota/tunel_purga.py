"""Retira de la base de datos la clave privada del túnel en cuanto la orden deja de entregarse.

La carga firmada completa (con la clave dentro) se guarda en `flota_ordenes.carga`, porque de ahí la
recoge el agente. El servidor solo entrega órdenes «pendiente» o «entregada» sin caducar; en cualquier
otro caso (el equipo ya contestó, se anuló o caducó) la clave ya no hace falta: se reescribe la carga
sin el campo `clave`, se marca en `parametros` y se deja constancia en `flota_registro`.

Se ejecuta cada minuto (ver `router_tunel.py`) y al consultar o anular órdenes de túnel. También revisa
las órdenes de túnel que no traen la marca `clave_en_orden` (las insertadas a mano antes de existir esta
pantalla): si llevaban clave, la retira igual.
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone

from app.flota import cargas
from app.flota.tunel_ajustes import ABRIR

logger = logging.getLogger(__name__)
CADA_S = 60

SQL_CANDIDATAS = (
    "SELECT orden_id::text AS orden_id, equipo_id::text AS equipo_id, carga, estado FROM flota_ordenes "
    f"WHERE tipo = '{ABRIR}' AND (parametros @> '{{\"clave_en_orden\": true}}'::jsonb OR NOT parametros ? 'clave_en_orden') "
    "AND (estado NOT IN ('pendiente', 'entregada') OR caduca_en <= NOW()) "
    "ORDER BY emitida_en LIMIT 200 FOR UPDATE SKIP LOCKED"
)
SQL_RETIRAR = (
    "UPDATE flota_ordenes SET carga = COALESCE($2, carga), "
    "parametros = (parametros - 'clave_en_orden') || $3::jsonb WHERE orden_id = $1"
)
SQL_ANOTAR = (
    "INSERT INTO flota_registro (equipo_id, orden_id, actor, accion, detalle, ip) "
    "VALUES ($1, $2, 'servidor', 'clave_tunel_eliminada', $3::jsonb, '')"
)


async def purgar(base) -> int:
    """Devuelve cuántas órdenes llevaban clave y se limpiaron."""
    limpiadas = 0
    async with base.acquire() as c, c.transaction():
        ahora = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        for f in await c.fetch(SQL_CANDIDATAS):
            sin_clave = cargas.sin_clave(f["carga"])
            marca = {"clave_en_orden": False}
            if sin_clave is not None:
                marca["clave_eliminada_en"] = ahora
            await c.execute(SQL_RETIRAR, f["orden_id"], sin_clave, json.dumps(marca))
            if sin_clave is not None:
                limpiadas += 1
                await c.execute(
                    SQL_ANOTAR,
                    f["equipo_id"],
                    f["orden_id"],
                    json.dumps({"estado": f["estado"]}),
                )
    return limpiadas


async def purgar_sin_fallar(base) -> int:
    try:
        return await purgar(base)
    except Exception:
        logger.exception("flota_tunel_purga_fallo")
        return 0


async def ciclo(base, cada_s: float = CADA_S) -> None:
    """Tarea de fondo del panel. Varias a la vez (un proceso por cada una) no se estorban."""
    while True:
        n = await purgar_sin_fallar(base)
        if n:
            logger.info("flota_tunel_claves_eliminadas | ordenes=%s", n)
        await asyncio.sleep(cada_s)
