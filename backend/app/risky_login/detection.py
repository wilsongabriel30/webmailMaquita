"""Detección de inicios de sesión riesgosos (cuenta comprometida).

Tras cada login exitoso (en segundo plano), geolocaliza la IP y la clasifica:
- País sede (confiable)      -> sin alerta
- País de viaje ocasional    -> riesgo MEDIO (verificar, no bloquea)
- Cualquier otro país        -> riesgo ALTO
- Viaje imposible            -> riesgo ALTO (siempre)
Si es riesgoso crea alerta y (opcional) deshabilita el buzón automáticamente.
"""
from __future__ import annotations

import json
import math
from datetime import datetime, timezone

from . import geoip


def _haversine(lat1, lon1, lat2, lon2) -> float:
    R = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _list(v):
    if isinstance(v, str):
        try:
            return json.loads(v)
        except ValueError:
            return []
    return v or []


async def _config(db) -> dict:
    row = await db.fetchrow(
        "SELECT enabled, auto_block, trusted_countries, occasional_countries FROM risky_login_config WHERE id=1")
    if not row:
        return {"enabled": True, "auto_block": False, "trusted_countries": ["Ecuador"], "occasional_countries": []}
    return {"enabled": row["enabled"], "auto_block": row["auto_block"],
            "trusted_countries": _list(row["trusted_countries"]),
            "occasional_countries": _list(row["occasional_countries"])}


async def analyze(db, redis, username: str, ip: str, user_agent: str = "") -> None:
    try:
        geo = await geoip.geolocate(redis, ip)
        internal = bool(geo.get("internal"))
        country = geo.get("country", "") or ""
        city = geo.get("city", "") or ""
        lat, lon = geo.get("lat"), geo.get("lon")
        if internal:
            # Anclar los logins internos a la sede para poder detectar saltos LAN->exterior
            country, city, lat, lon = "Ecuador", "Sede/Interna", -0.1807, -78.4678

        prev = []
        if not internal:
            prev = await db.fetch(
                "SELECT country, lat, lon, created_at FROM login_events "
                "WHERE username=$1 AND lat IS NOT NULL "
                "ORDER BY created_at DESC LIMIT 30", username)

        await db.execute(
            "INSERT INTO login_events (username, ip, is_internal, country, city, lat, lon, user_agent) "
            "VALUES ($1,$2,$3,$4,$5,$6,$7,$8)",
            username, ip or "", internal, country, city, lat, lon, (user_agent or "")[:400])

        if internal or lat is None or lon is None:
            return

        cfg = await _config(db)
        if not cfg["enabled"]:
            return

        trusted = cfg["trusted_countries"]
        occasional = cfg["occasional_countries"]
        reasons, risk, dist_km = [], "low", None

        # Clasificación por país (3 niveles)
        if country and trusted:
            if country in trusted:
                pass  # país sede -> sin alerta por país
            elif country in occasional:
                reasons.append(f"País de viaje ocasional: {country} — conviene verificar con la persona")
                risk = "medium"
            else:
                reasons.append(f"País NO autorizado: {country} (la institución no opera ni viaja ahí)")
                risk = "high"

        # Viaje imposible vs el login público más reciente -> ALTO siempre
        if prev:
            last = prev[0]
            if last["lat"] is not None:
                hours = (datetime.now(timezone.utc) - last["created_at"]).total_seconds() / 3600.0
                dist_km = int(_haversine(lat, lon, last["lat"], last["lon"]))
                if hours > 0 and dist_km > 500 and (dist_km / hours) > 900:
                    reasons.append(f"Viaje imposible: {dist_km} km en {hours:.1f}h (de {last['country']} a {country})")
                    risk = "high"

        if not reasons:
            return

        await db.execute(
            "INSERT INTO risky_logins (username, ip, country, city, reason, risk, distance_km) "
            "VALUES ($1,$2,$3,$4,$5,$6,$7)",
            username, ip or "", country, city, " · ".join(reasons), risk, dist_km)

        try:
            await db.execute(
                "INSERT INTO fraud_alerts (alert_type, severity, username, description, details, status) "
                "VALUES ('risky_login',$1,$2,$3,$4::jsonb,'open')",
                "high" if risk == "high" else "medium", username,
                f"Login riesgoso desde {city or country} ({ip}): {' · '.join(reasons)}",
                json.dumps({"ip": ip, "country": country, "city": city}))
        except Exception:
            pass

        try:
            from app.conditional_access.service import evaluate_and_apply
            await evaluate_and_apply(db, username, risk, country, reasons, (cfg.get("trusted_countries") or []) + (cfg.get("occasional_countries") or []))
        except Exception:
            pass

        if risk == "high" and cfg["auto_block"]:
            try:
                await db.execute("UPDATE mailbox SET active=false, modified=now() WHERE username=$1", username)
                await db.execute(
                    "INSERT INTO threat_actions (action, target, detail, actor, auto) "
                    "VALUES ('disable_mailbox',$1,$2,'sistema',true)",
                    username, f"Auto-deshabilitado por login riesgoso ({country})")
            except Exception:
                pass
    except Exception:
        pass
