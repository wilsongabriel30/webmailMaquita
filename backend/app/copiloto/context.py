"""Reúne un snapshot REAL de seguridad para fundamentar (grounding) al Copilot.

Cada consulta está aislada: si una tabla falta, esa señal queda vacía, no rompe.
"""


async def gather(db, days: int = 7) -> dict:
    iv = f"{int(days)} days"

    async def cnt(sql, *a):
        try:
            return await db.fetchval(sql, *a) or 0
        except Exception:
            return 0

    async def rows(sql, *a):
        try:
            return [dict(r) for r in await db.fetch(sql, *a)]
        except Exception:
            return []

    total = await cnt("SELECT count(*) FROM mailbox WHERE active")
    mfa = await cnt("SELECT count(*) FROM user_totp WHERE enabled")
    return {
        "periodo_dias": days,
        "buzones_activos": total,
        "con_2fa": mfa,
        "pct_2fa": round(100 * mfa / total) if total else 0,
        "config": {
            "dlp_activo": bool(await cnt("SELECT enabled FROM dlp_config WHERE id=1")),
            "safelinks_activo": bool(await cnt("SELECT enabled FROM safelinks_config WHERE id=1")),
            "auto_contencion": bool(await cnt("SELECT auto_disable_on_compromise FROM threat_config WHERE id=1")),
            "politicas_retencion": await cnt("SELECT count(*) FROM retention_policies WHERE is_active"),
        },
        "logins_riesgo_alto": await cnt(
            "SELECT count(*) FROM risky_logins WHERE created_at>now()-($1)::interval AND lower(risk)='high'", iv),
        "top_logins_riesgo": await rows(
            "SELECT username, coalesce(country,'?') pais, count(*) n FROM risky_logins "
            "WHERE created_at>now()-($1)::interval AND lower(risk)='high' GROUP BY 1,2 ORDER BY n DESC LIMIT 5", iv),
        "violaciones_dlp": await cnt(
            "SELECT count(*) FROM dlp_violations WHERE created_at>now()-($1)::interval", iv),
        "top_dlp": await rows(
            "SELECT username, count(*) n FROM dlp_violations WHERE created_at>now()-($1)::interval "
            "GROUP BY 1 ORDER BY n DESC LIMIT 5", iv),
        "clics_peligrosos": await cnt(
            "SELECT count(*) FROM safelinks_clicks WHERE created_at>now()-($1)::interval "
            "AND lower(coalesce(verdict,'')) IN ('suspicious','malicious','blocked')", iv),
        "adjuntos_riesgosos": await cnt(
            "SELECT count(*) FROM safeattach_results WHERE verdict IN ('malicious','suspicious') "
            "AND created_at>now()-($1)::interval", iv),
        "incidentes_air": await rows(
            "SELECT action, target, left(coalesce(detail,''),120) detalle FROM threat_actions "
            "WHERE actor='AIR' AND created_at>now()-($1)::interval ORDER BY created_at DESC LIMIT 8", iv),
    }
