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


async def registrar(con, equipo: dict, ip: str | None, puede_guardar: bool, bssid: str | None = None) -> dict | None:
    """Tras un latido: anota la sede reconocida y, si procede, guarda la posición por ancla.
    El punto de acceso wifi (BSSID) manda sobre la red IP: es más preciso."""
    ancla = await por_bssid(con, bssid) or await resolver(con, ip)
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
                "VALUES ($1, NOW(), $2, $3, $4, $6, 'ancla', $5)",
                equipo["id"], ancla["lat"], ancla["lon"], float(ancla["radio_m"]), ip, "wifi" if "valor" in ancla and ":" in str(ancla["valor"]) else "red",
            )
    return ancla


# ── Etapa 2: anclas por punto de acceso (BSSID) y triangulación por intensidad ───────────────────

async def _bssids(db) -> dict:
    if time.monotonic() - _cache.get("t_bssid", 0.0) > _CADA_SEG:
        filas = await db.fetch("SELECT valor, sede, nombre, lat, lon, radio_m FROM disp_anclas_red WHERE tipo = 'bssid' AND activa")
        _cache.update(t_bssid=time.monotonic(), bssids={f["valor"].lower(): dict(f) for f in filas})
    return _cache["bssids"]


async def por_bssid(db, bssid: str | None) -> dict | None:
    if not bssid:
        return None
    return (await _bssids(db)).get(bssid.strip().lower())


def _peso(rssi) -> float:
    """Más señal, más cerca: peso proporcional a la potencia recibida (escala logarítmica de dBm)."""
    try:
        return 10 ** ((float(rssi) + 100) / 20)
    except (TypeError, ValueError):
        return 1.0


async def triangular(db, wifis: list[dict]) -> dict | None:
    """Centroide ponderado por intensidad de los puntos de acceso conocidos entre los vistos.
    Devuelve {lat, lon, precision_m, sede, anclas} o None si no se reconoce ninguno."""
    conocidos = await _bssids(db)
    usados = []
    for w in wifis or []:
        a = conocidos.get(str(w.get("bssid") or "").lower())
        if a:
            usados.append((a, _peso(w.get("rssi"))))
    if not usados:
        return None
    total = sum(p for _, p in usados)
    lat = sum(a["lat"] * p for a, p in usados) / total
    lon = sum(a["lon"] * p for a, p in usados) / total
    radios = sorted(a["radio_m"] for a, _ in usados)
    precision = float(radios[0]) if len(usados) == 1 else max(10.0, float(radios[0]) / len(usados) ** 0.5)
    sedes = {a["sede"] for a, _ in usados}
    return {"lat": lat, "lon": lon, "precision_m": precision, "sede": sedes.pop() if len(sedes) == 1 else None, "anclas": len(usados)}


async def guardar_triangulacion(con, equipo: dict, wifis: list[dict], ip: str | None, puede_guardar: bool) -> dict | None:
    pos = await triangular(con, wifis)
    if pos is None or not puede_guardar:
        return pos
    await con.execute(
        "INSERT INTO disp_ubicaciones (equipo_id, tomada_en, lat, lon, precision_m, fuente, origen, ip) "
        "VALUES ($1, NOW(), $2, $3, $4, 'wifi', 'ancla', $5)",
        equipo["id"], pos["lat"], pos["lon"], pos["precision_m"], ip,
    )
    if pos["sede"]:
        await con.execute("UPDATE disp_equipos SET ancla_sede = $2, ancla_en = NOW() WHERE id = $1", equipo["id"], pos["sede"])
    return pos
