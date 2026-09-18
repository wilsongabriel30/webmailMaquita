"""Retención de los respaldos de un equipo: se conservan las últimas instantáneas completas y las
dos últimas de cierre; los contenidos que ya no referencia ninguna instantánea se borran del disco."""

import asyncio
import logging

from app.dispositivos import objetos

logger = logging.getLogger("dispositivos")


async def depurar(db, equipo_id: int, instantaneas: int = 7, carpeta_eq: str | None = None) -> None:
    try:
        await db.execute(
            """DELETE FROM disp_respaldos WHERE equipo_id = $1 AND estado <> 'abierto' AND iniciado_en < NOW() - interval '1 day'
                 AND id NOT IN (SELECT id FROM disp_respaldos WHERE equipo_id = $1 AND estado = 'completo' AND tipo <> 'cierre'
                                ORDER BY iniciado_en DESC LIMIT $2)
                 AND id NOT IN (SELECT id FROM disp_respaldos WHERE equipo_id = $1 AND estado = 'completo' AND tipo = 'cierre'
                                ORDER BY iniciado_en DESC LIMIT 2)""", equipo_id, max(1, instantaneas))
        huerfanos = await db.fetch(
            """SELECT o.sha256 FROM disp_objetos o WHERE o.equipo_id = $1 AND o.creado_en < NOW() - interval '1 day' AND NOT EXISTS (
                   SELECT 1 FROM disp_respaldo_archivos a JOIN disp_respaldos r ON r.id = a.respaldo_id
                   WHERE r.equipo_id = $1 AND a.sha256 = o.sha256) LIMIT 5000""", equipo_id)
        carpeta_eq = carpeta_eq or str(equipo_id)
        for h in huerfanos:
            await asyncio.to_thread(objetos.borrar, carpeta_eq, h["sha256"])
        if huerfanos:
            await db.execute("DELETE FROM disp_objetos WHERE equipo_id = $1 AND sha256 = ANY($2::bpchar[])", equipo_id, [h["sha256"] for h in huerfanos])
            logger.info("respaldos_depurados | equipo=%s | contenidos=%d", equipo_id, len(huerfanos))
    except Exception:
        logger.exception("respaldos_depurar_fallo | equipo=%s", equipo_id)
