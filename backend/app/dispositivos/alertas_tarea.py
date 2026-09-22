"""Trabajo programado de la telemetría de los teléfonos (cada 15 min por systemd timer).

    cd /opt/maquita-webmail/backend && venv/bin/python -m app.dispositivos.alertas_tarea [--simular]

Hace, en este orden:
1. Recalcula el resumen diario (hoy y ayer) y depura latidos y códigos vencidos.
2. Evalúa las reglas (`alertas_reglas`) contra los umbrales de `disp_config.alertas`; abre las alertas
   nuevas, cierra las que ya no se cumplen y avisa por correo a Tecnología SOLO de las nuevas.
3. A la hora configurada manda el resumen diario a dirección (una vez por día).

Regla de autonomía: el sistema avisa solo, nunca silencio. Si el correo falla, la alerta queda abierta
en el portal y se reintenta el aviso en la siguiente corrida (`avisada_en` sigue en NULL).
Con --simular no escribe ni envía: solo imprime lo que haría.
"""

import asyncio
import json
import logging
import os
import sys
from datetime import datetime
from zoneinfo import ZoneInfo

import asyncpg

from app.dispositivos import alertas_correo, alertas_reglas, resumen_diario

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("dispositivos")
ZONA = ZoneInfo("America/Guayaquil")

_EQUIPO = "e.nombre, e.fabricante, e.modelo, e.custodio_nombre, e.custodio_email"


async def _config(db, clave: str) -> dict:
    v = await db.fetchval("SELECT valor FROM disp_config WHERE clave = $1", clave)
    return (json.loads(v) if isinstance(v, str) else v) or {}


async def _depurar(db, politica: dict) -> None:
    await db.execute("DELETE FROM disp_latidos WHERE recibido_en < NOW() - make_interval(days => $1)",
                     int(politica.get("retencion_latidos_dias", 30)))
    # Código caducado o anulado: su copia cifrada ya no sirve para nada (AE-04).
    await db.execute("UPDATE disp_codigos SET codigo_cifrado = NULL WHERE codigo_cifrado IS NOT NULL "
                     "AND (revocado_en IS NOT NULL OR usos >= usos_max OR (caduca_en IS NOT NULL AND caduca_en < NOW()))")


async def _sincronizar(db, condiciones: list[dict], simular: bool) -> list[dict]:
    """Abre las alertas nuevas y cierra las que ya no se cumplen. Devuelve las nuevas (con datos del equipo)."""
    abiertas = {(a["equipo_id"], a["tipo"]): a["id"] for a in await db.fetch("SELECT id, equipo_id, tipo FROM disp_alertas WHERE hasta IS NULL")}
    actuales = {(c["equipo_id"], c["tipo"]) for c in condiciones}
    nuevas_ids = []
    for c in condiciones:
        if (c["equipo_id"], c["tipo"]) in abiertas:
            if not simular:
                await db.execute("UPDATE disp_alertas SET detalle = $2::jsonb WHERE id = $1",
                                 abiertas[(c["equipo_id"], c["tipo"])], json.dumps(c["detalle"], default=str))
            continue
        logger.info("alerta_nueva | equipo=%s | tipo=%s | %s", c["equipo_id"], c["tipo"], c["detalle"])
        if not simular:
            nuevas_ids.append(await db.fetchval(
                "INSERT INTO disp_alertas (equipo_id, tipo, detalle) VALUES ($1, $2, $3::jsonb) RETURNING id",
                c["equipo_id"], c["tipo"], json.dumps(c["detalle"], default=str)))
    for clave, aid in abiertas.items():
        if clave not in actuales:
            logger.info("alerta_cerrada | equipo=%s | tipo=%s", *clave)
            if not simular:
                await db.execute("UPDATE disp_alertas SET hasta = NOW() WHERE id = $1", aid)
    if simular:
        return []
    # Pendientes de aviso: las nuevas y las que quedaron sin avisar por un fallo de correo anterior.
    return [dict(f) for f in await db.fetch(
        f"SELECT a.id, a.equipo_id, a.tipo, a.detalle, a.desde, {_EQUIPO} FROM disp_alertas a JOIN disp_equipos e ON e.id = a.equipo_id "
        "WHERE a.hasta IS NULL AND a.avisada_en IS NULL ORDER BY a.desde")]


async def _resumen(db, u: dict, simular: bool) -> None:
    destinos = (u.get("resumen_diario_para") or "").strip()
    if not destinos:
        return
    ahora = datetime.now(ZONA)
    try:
        hh, mm = (u.get("resumen_hora") or "07:30").split(":")
        objetivo = ahora.replace(hour=int(hh), minute=int(mm), second=0, microsecond=0)
    except ValueError:
        objetivo = ahora.replace(hour=7, minute=30, second=0, microsecond=0)
    estado = await _config(db, "alertas_estado")
    if ahora < objetivo or estado.get("resumen_enviado_dia") == ahora.date().isoformat():
        return
    t = await db.fetchrow(
        """SELECT count(*) FILTER (WHERE estado IN ('activo','perdido')) AS total,
                  count(*) FILTER (WHERE estado IN ('activo','perdido') AND ultimo_contacto > NOW() - interval '24 hours') AS hoy,
                  count(*) FILTER (WHERE estado IN ('activo','perdido') AND (ultimo_contacto IS NULL OR ultimo_contacto < NOW() - interval '24 hours')) AS rojo,
                  (SELECT count(DISTINCT equipo_id) FROM disp_alertas WHERE hasta IS NULL) AS con_alertas
           FROM disp_equipos""")
    abiertas = [dict(f) for f in await db.fetch(
        f"SELECT a.id, a.equipo_id, a.tipo, a.detalle, a.desde, {_EQUIPO} FROM disp_alertas a JOIN disp_equipos e ON e.id = a.equipo_id "
        "WHERE a.hasta IS NULL ORDER BY e.nombre, a.desde")]
    for a in abiertas:
        a["detalle"] = json.loads(a["detalle"]) if isinstance(a["detalle"], str) else a["detalle"]
    logger.info("resumen_diario | para=%s | abiertas=%d", destinos, len(abiertas))
    if simular:
        return
    if await alertas_correo.resumen_diario(destinos, dict(t), abiertas):
        await db.execute(
            "INSERT INTO disp_config (clave, valor) VALUES ('alertas_estado', $1::jsonb) "
            "ON CONFLICT (clave) DO UPDATE SET valor = EXCLUDED.valor, actualizado_en = NOW()",
            json.dumps({"resumen_enviado_dia": ahora.date().isoformat()}))


async def correr(simular: bool = False) -> int:
    dsn = (os.environ.get("DATABASE_URL") or "").replace("postgresql+asyncpg://", "postgresql://")
    if not dsn:
        logger.error("Falta DATABASE_URL (cargar backend/.env)")
        return 2
    db = await asyncpg.connect(dsn)
    try:
        politica = await _config(db, "politica")
        u = {**alertas_reglas.UMBRALES_BASE, **await _config(db, "alertas")}
        if not simular:
            n = await resumen_diario.actualizar(db)
            await _depurar(db, politica)
            logger.info("resumen_diario_actualizado | filas=%s", n)
        if not u.get("activo", True):
            logger.info("alertas_desactivadas_en_config")
            return 0
        condiciones = await alertas_reglas.evaluar(db, u)
        pendientes = await _sincronizar(db, condiciones, simular)
        if simular:
            for c in condiciones:
                print(f"{c['tipo']:24} equipo {c['equipo_id']}: {c['detalle']}")
            print(f"{len(condiciones)} condición(es) activas")
            return 0
        if pendientes:
            for a in pendientes:
                a["detalle"] = json.loads(a["detalle"]) if isinstance(a["detalle"], str) else a["detalle"]
            if await alertas_correo.avisar_nuevas(u.get("correo_ti") or "", pendientes):
                await db.execute("UPDATE disp_alertas SET avisada_en = NOW() WHERE id = ANY($1::int[])", [a["id"] for a in pendientes])
        await _resumen(db, u, simular)
        logger.info("alertas_evaluadas | condiciones=%d | avisadas=%d", len(condiciones), len(pendientes))
        return 0
    finally:
        await db.close()


if __name__ == "__main__":
    sys.exit(asyncio.run(correr("--simular" in sys.argv)))
