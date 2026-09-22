"""Credenciales NTRIP (red REGME del IGM) para las mediciones de campo desde el teléfono (22/09/2026).

Dirección: la app se conecta sola al caster con credenciales precargadas, corrige en el momento y manda
al servidor la posición corregida junto con el lote crudo. El servidor entrega la configuración solo a
teléfonos enrolados con ubicación autorizada (o perdidos) y elige la estación por la sede reconocida
(ancla) o la más cercana a la última posición. Las credenciales viven en `disp_config.ntrip` con la
clave cifrada (DISP_CODIGO_CLAVE), nunca en claro en la base.

Estructura de `disp_config.ntrip`:
{"caster": "ntrip.igm.gob.ec", "puerto": 2101, "usuario": "REGME38393", "clave_cifrada": "...",
 "estaciones": [{"punto": "Quito-QUI1-IGM", "lat": -0.22, "lon": -78.49, "sede": "Maquita central"}, ...],
 "max_conexiones": 1, "nota": "una sola conexión por cuenta: solo durante la medición"}
"""

import json
import math

from app.dispositivos.codigo_cifrado import descifrar


async def configuracion(db) -> dict:
    v = await db.fetchval("SELECT valor FROM disp_config WHERE clave = 'ntrip'")
    return (json.loads(v) if isinstance(v, str) else v) or {}


def _estacion_para(cfg: dict, equipo: dict, lat: float | None, lon: float | None) -> dict | None:
    ests = cfg.get("estaciones") or []
    if not ests:
        return None
    sede = equipo.get("ancla_sede")
    if sede:
        for e in ests:
            if e.get("sede") == sede:
                return e
    if lat is not None and lon is not None:
        return min(ests, key=lambda e: math.hypot((e["lat"] - lat), (e["lon"] - lon) * math.cos(math.radians(lat))))
    return ests[0]


async def para_equipo(db, equipo: dict, permitido: bool) -> dict | None:
    """Configuración NTRIP lista para la app, o None si no procede."""
    if not permitido:
        return None
    cfg = await configuracion(db)
    if not cfg.get("caster"):
        return None
    pos = await db.fetchrow("SELECT lat, lon FROM disp_ubicaciones WHERE equipo_id = $1 ORDER BY tomada_en DESC LIMIT 1", equipo["id"])
    est = _estacion_para(cfg, equipo, pos["lat"] if pos else None, pos["lon"] if pos else None)
    salida = {
        "caster": cfg["caster"], "puerto": int(cfg.get("puerto") or 2101),
        "punto": est["punto"] if est else None, "estacion_lat": est["lat"] if est else None, "estacion_lon": est["lon"] if est else None,
        "estaciones": [e["punto"] for e in cfg.get("estaciones") or []],
        "protocolo": "ntrip1-con-gga", "max_conexiones": int(cfg.get("max_conexiones") or 1),
        "registro": cfg.get("registro") or "https://www.geoportaligm.gob.ec/ntrip/public/",
        "credenciales": "personales",   # decisión de dirección 22/09: cada técnico se registra en el IGM y usa su propia cuenta en la app
        "regla": "Conectar solo durante la medición de campo y cerrar al terminar; nunca reintentar en bucle (el caster bloquea la cuenta).",
    }
    # Solo si Tecnología lo activa expresamente se comparte la cuenta institucional (una conexión a la vez).
    if cfg.get("compartir_cuenta") and cfg.get("usuario") and cfg.get("clave_cifrada"):
        clave = descifrar(cfg["clave_cifrada"])
        if clave:
            salida.update(usuario=cfg["usuario"], clave=clave, credenciales="institucional")
    return salida
