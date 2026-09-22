"""Anclas de red por sede: ubicar un teléfono por la red desde la que reporta (etapa 1, 22/09/2026).

Si la IP del latido cae en una subred o bloque de una sede (`disp_anclas_red`, tipo `red`), el equipo
está en esa sede: se anota en `disp_equipos.ancla_sede` (siempre, es dato de red como la IP) y, solo si
la ubicación del equipo está autorizada o está perdido, se guarda una posición con origen `ancla`,
como mucho una cada 15 minutos por equipo y sede, con el radio del ancla como margen.
La etapa 2 (BSSID de los puntos de acceso que ve el teléfono, triangulación por intensidad) usará la
misma tabla con tipo `bssid`.
"""

import ipaddress
import logging
import time

logger = logging.getLogger("dispositivos")
_cache: dict = {"t": 0.0, "redes": []}
_CADA_SEG = 60
_MINUTOS_ENTRE_POSICIONES = 15


async def _redes(db) -> list[dict]:
    if time.monotonic() - _cache["t"] > _CADA_SEG:
        filas = await db.fetch(
            "SELECT id, valor, sede, nombre, lat, lon, radio_m FROM disp_anclas_red WHERE tipo = 'red' AND activa"
        )
        redes = []
        for f in filas:
            try:
                redes.append({**dict(f), "red": ipaddress.ip_network(f["valor"], strict=False)})
            except ValueError:
                logger.warning("ancla_red_invalida | id=%s | valor=%s", f["id"], f["valor"])
        # Las redes más pequeñas primero: si una IP cae en dos, gana la más específica.
        redes.sort(key=lambda r: -r["red"].prefixlen)
        _cache.update(t=time.monotonic(), redes=redes)
    return _cache["redes"]


async def resolver(db, ip: str | None) -> dict | None:
    """Ancla cuya red contiene la IP, o None."""
    if not ip:
        return None
    try:
        dir_ip = ipaddress.ip_address(ip.split("%")[0])
    except ValueError:
        return None
    for r in await _redes(db):
        if dir_ip in r["red"]:
            return r
    return None


async def registrar(con, equipo: dict, ip: str | None, puede_guardar: bool) -> dict | None:
    """Tras un latido: anota la sede reconocida y, si procede, guarda la posición por ancla."""
    ancla = await resolver(con, ip)
    if ancla is None:
        if equipo.get("ancla_sede"):
            await con.execute("UPDATE disp_equipos SET ancla_sede = NULL WHERE id = $1", equipo["id"])
        return None
    await con.execute(
        "UPDATE disp_equipos SET ancla_sede = $2, ancla_en = NOW() WHERE id = $1", equipo["id"], ancla["sede"]
    )
    if puede_guardar:
        reciente = await con.fetchval(
            "SELECT 1 FROM disp_ubicaciones WHERE equipo_id = $1 AND origen = 'ancla' "
            "AND recibida_en > NOW() - make_interval(mins => $2) AND lat = $3 AND lon = $4 LIMIT 1",
            equipo["id"], _MINUTOS_ENTRE_POSICIONES, ancla["lat"], ancla["lon"],
        )
        if not reciente:
            await con.execute(
                "INSERT INTO disp_ubicaciones (equipo_id, tomada_en, lat, lon, precision_m, fuente, origen, ip) "
                "VALUES ($1, NOW(), $2, $3, $4, 'red', 'ancla', $5)",
                equipo["id"], ancla["lat"], ancla["lon"], float(ancla["radio_m"]), ip,
            )
    return ancla
