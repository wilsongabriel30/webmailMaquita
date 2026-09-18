"""Ubicación de los teléfonos (fase 2): guardado con la regla de privacidad, lotes bajo demanda y
avistamientos de equipos perdidos por parte de otros teléfonos de la organización.

Regla de privacidad: una posición solo se guarda si el custodio firmó la política de uso
(`ubicacion_autorizada`) o si el equipo está declarado perdido. Si no, se descarta sin dejar rastro.
"""

import logging
import random
from datetime import datetime, timedelta, timezone
from typing import Literal, Optional

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field

from app.dispositivos.esquemas import Ubicacion
from app.dispositivos.seguridad import equipo_actual, ip_cliente, limitar

logger = logging.getLogger("dispositivos")
router = APIRouter(prefix="/api/dispositivos", tags=["dispositivos"])


class LoteUbicaciones(BaseModel):
    puntos: list[Ubicacion] = Field(..., min_length=1, max_length=100)
    origen: Literal["periodica", "comando", "perdido"] = "periodica"


class Avistamiento(BaseModel):
    baliza_id: str = Field(..., pattern=r"^[0-9a-f]{16}$")
    rssi: Optional[int] = Field(None, ge=-127, le=20)
    ubicacion: Ubicacion


class Avistamientos(BaseModel):
    vistos: list[Avistamiento] = Field(..., min_length=1, max_length=50)


def puede_guardar(equipo: dict) -> bool:
    return bool(equipo.get("ubicacion_autorizada")) or equipo.get("estado") == "perdido"


def _hora(p: Ubicacion) -> datetime:
    """Hora de la toma según el teléfono; si falta, es absurda o viene del futuro, la del servidor."""
    ahora = datetime.now(timezone.utc)
    try:
        t = datetime.fromisoformat((p.hora or "").replace("Z", "+00:00"))
        if t.tzinfo is None:
            t = t.replace(tzinfo=timezone.utc)
    except ValueError:
        return ahora
    if t > ahora + timedelta(minutes=10) or t < ahora - timedelta(days=30):
        return ahora
    return t


async def guardar(con, equipo: dict, puntos: list[Ubicacion], origen: str, ip: str, bateria: int | None = None) -> int:
    if not puntos or not puede_guardar(equipo):
        return 0
    if equipo.get("estado") == "perdido" and origen == "periodica":
        origen = "perdido"
    await con.executemany(
        "INSERT INTO disp_ubicaciones (equipo_id, tomada_en, lat, lon, precision_m, fuente, origen, bateria, ip) "
        "VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9)",
        [(equipo["id"], _hora(p), p.lat, p.lon, p.precision, p.fuente, origen, bateria, ip) for p in puntos],
    )
    return len(puntos)


async def limpieza_ocasional(db, politica: dict) -> None:
    """Una de cada ~300 llamadas borra lo que pasó de la retención (sin cron ni credenciales aparte)."""
    if random.randrange(300):
        return
    try:
        await db.execute("DELETE FROM disp_ubicaciones WHERE recibida_en < NOW() - make_interval(days => $1)",
                         int(politica.get("retencion_ubicaciones_dias", 90)))
        await db.execute("DELETE FROM disp_latidos WHERE recibido_en < NOW() - make_interval(days => $1)",
                         int(politica.get("retencion_latidos_dias", 30)))
    except Exception:
        logger.exception("limpieza_dispositivos_fallo")


@router.post("/ubicacion")
async def enviar_ubicaciones(request: Request, body: LoteUbicaciones, equipo: dict = Depends(equipo_actual)):
    """Posiciones fuera del latido: respuesta a «localizar», cola acumulada sin red, modo perdido."""
    await limitar(request, f"ubic:{equipo['id']}", 120, 3600)
    async with request.app.state.db_pool.acquire() as con:
        n = await guardar(con, equipo, body.puntos, body.origen, ip_cliente(request))
    return {"guardadas": n, "ubicacion_activa": puede_guardar(equipo)}


@router.post("/avistamientos")
async def avistamientos(request: Request, body: Avistamientos, equipo: dict = Depends(equipo_actual)):
    """Otro teléfono de la organización oyó la baliza Bluetooth de un equipo perdido."""
    await limitar(request, f"avist:{equipo['id']}", 60, 3600)
    db = request.app.state.db_pool
    ip = ip_cliente(request)
    n = 0
    for v in body.vistos:
        perdido = await db.fetchval(
            "SELECT id FROM disp_equipos WHERE baliza_id = $1 AND estado = 'perdido' AND id <> $2", v.baliza_id, equipo["id"])
        if perdido is None:
            continue
        await db.execute(
            "INSERT INTO disp_ubicaciones (equipo_id, tomada_en, lat, lon, precision_m, fuente, origen, visto_por, rssi, ip) "
            "VALUES ($1,$2,$3,$4,$5,$6,'avistamiento',$7,$8,$9)",
            perdido, _hora(v.ubicacion), v.ubicacion.lat, v.ubicacion.lon, v.ubicacion.precision,
            v.ubicacion.fuente, equipo["id"], v.rssi, ip)
        n += 1
        logger.warning("equipo_perdido_avistado | perdido=%s | por=%s | rssi=%s", perdido, equipo["id"], v.rssi)
    return {"registrados": n}
