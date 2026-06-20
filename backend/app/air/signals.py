"""Recolección y correlación de señales de riesgo por usuario.

Cada consulta está aislada: si una tabla/columna falta, no rompe el resto.
"""
import logging

logger = logging.getLogger("air.signals")

# peso de cada señal en el score
WEIGHTS = {"risky_high": 4, "dlp": 2, "safelink_bad": 2}


async def _safe(db, sql, *args):
    try:
        return await db.fetch(sql, *args)
    except Exception as e:                      # tabla/columna ausente -> señal vacía
        logger.warning("señal omitida: %s", e)
        return []


async def collect(db, hours: int = 24) -> dict:
    """Devuelve {username: {risky_high, dlp, safelink_bad, score}}."""
    users: dict = {}

    def bump(u, key, n=1):
        if not u or not str(u).strip():
            return
        e = users.setdefault(u, {"risky_high": 0, "dlp": 0, "safelink_bad": 0})
        e[key] += n

    for r in await _safe(db,
        "SELECT username, count(*) c FROM risky_logins "
        "WHERE created_at > now() - ($1||' hours')::interval AND lower(risk)='high' "
        "GROUP BY username", str(hours)):
        bump(r["username"], "risky_high", r["c"])

    for r in await _safe(db,
        "SELECT username, count(*) c FROM dlp_violations "
        "WHERE created_at > now() - ($1||' hours')::interval GROUP BY username", str(hours)):
        bump(r["username"], "dlp", r["c"])

    for r in await _safe(db,
        "SELECT username, count(*) c FROM safelinks_clicks "
        "WHERE created_at > now() - ($1||' hours')::interval "
        "AND lower(coalesce(verdict,'')) IN ('suspicious','malicious','blocked') "
        "GROUP BY username", str(hours)):
        bump(r["username"], "safelink_bad", r["c"])


    for u, e in users.items():
        e["score"] = sum(WEIGHTS[k] * min(e[k], 10) for k in WEIGHTS)
    return users
