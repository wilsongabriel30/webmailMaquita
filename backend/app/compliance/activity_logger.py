"""User Activity Logger — Auditoría de actividad de usuarios para compliance/antifraude.

Registra acciones críticas: login, password, 2FA, sieve, reenvíos, envío,
eliminación, exportación, impersonación, eDiscovery.
"""

import json
import logging
from datetime import datetime

logger = logging.getLogger("compliance.activity")

# Acciones y su nivel de riesgo
ACTION_RISK = {
    # Auth
    "login_success": "low",
    "login_failed": "medium",
    "logout": "low",
    "password_change": "high",
    "password_reset": "high",
    "totp_setup": "high",
    "totp_disable": "critical",
    # Email
    "email_send": "low",
    "email_delete": "medium",
    "email_expunge": "high",
    "email_bulk_delete": "high",
    "email_move": "low",
    "email_export": "high",
    "email_export_bulk": "critical",
    "attachment_download": "low",
    "attachment_download_bulk": "high",
    # Sieve / Filters
    "sieve_create": "medium",
    "sieve_modify": "medium",
    "sieve_delete": "medium",
    "forward_create": "critical",
    "forward_modify": "critical",
    "forward_delete": "high",
    "autoresponder_change": "low",
    # Admin / Compliance
    "impersonate": "critical",
    "ediscovery_search": "high",
    "ediscovery_export": "critical",
    "ediscovery_preview": "high",
    "legal_hold_enable": "critical",
    "legal_hold_release": "critical",
    # Security
    "api_key_create": "high",
    "api_key_delete": "medium",
    "session_revoke": "medium",
}

CATEGORY_MAP = {
    "login_success": "auth",
    "login_failed": "auth",
    "logout": "auth",
    "password_change": "auth",
    "password_reset": "auth",
    "totp_setup": "security",
    "totp_disable": "security",
    "email_send": "email",
    "email_delete": "email",
    "email_expunge": "email",
    "email_bulk_delete": "email",
    "email_move": "email",
    "email_export": "email",
    "email_export_bulk": "email",
    "attachment_download": "email",
    "attachment_download_bulk": "email",
    "sieve_create": "sieve",
    "sieve_modify": "sieve",
    "sieve_delete": "sieve",
    "forward_create": "sieve",
    "forward_modify": "sieve",
    "forward_delete": "sieve",
    "autoresponder_change": "sieve",
    "impersonate": "admin",
    "ediscovery_search": "compliance",
    "ediscovery_export": "compliance",
    "ediscovery_preview": "compliance",
    "legal_hold_enable": "compliance",
    "legal_hold_release": "compliance",
    "api_key_create": "security",
    "api_key_delete": "security",
    "session_revoke": "security",
}


async def log_user_activity(
    db,
    username: str,
    action: str,
    *,
    message_id: str = None,
    mailbox: str = None,
    folder: str = None,
    target: str = None,
    ip_address: str = None,
    user_agent: str = None,
    details: dict = None,
):
    """Registra una acción de usuario en user_activity_log."""
    risk = ACTION_RISK.get(action, "low")
    category = CATEGORY_MAP.get(action, "general")

    try:
        await db.execute(
            """INSERT INTO user_activity_log
               (username, action, category, message_id, mailbox, folder, target,
                ip_address, user_agent, details, risk_level)
               VALUES ($1, $2, $3, $4, $5, $6, $7, $8::inet, $9, $10::jsonb, $11)""",
            username,
            action,
            category,
            message_id,
            mailbox,
            folder,
            target,
            ip_address,
            user_agent,
            json.dumps(details) if details else None,
            risk,
        )
    except Exception as exc:
        logger.error("Error registrando actividad: %s — %s %s", exc, username, action)

    # Log de alto riesgo también a archivo
    if risk in ("high", "critical"):
        logger.warning(
            "ACTIVITY user=%s action=%s risk=%s target=%s ip=%s",
            username,
            action,
            risk,
            target or "",
            ip_address or "",
        )


async def get_user_activities(
    db,
    *,
    username: str = None,
    action: str = None,
    category: str = None,
    risk_level: str = None,
    date_from: str = None,
    date_to: str = None,
    page: int = 1,
    per_page: int = 50,
) -> dict:
    """Consulta actividades con filtros."""
    conditions = []
    params = []
    idx = 1

    if username:
        conditions.append(f"username = ${idx}")
        params.append(username)
        idx += 1
    if action:
        conditions.append(f"action = ${idx}")
        params.append(action)
        idx += 1
    if category:
        conditions.append(f"category = ${idx}")
        params.append(category)
        idx += 1
    if risk_level:
        conditions.append(f"risk_level = ${idx}")
        params.append(risk_level)
        idx += 1
    if date_from:
        conditions.append(f"created_at >= ${idx}::timestamptz")
        params.append(date_from)
        idx += 1
    if date_to:
        conditions.append(f"created_at <= ${idx}::timestamptz")
        params.append(date_to)
        idx += 1

    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""

    total = await db.fetchval(
        f"SELECT count(*) FROM user_activity_log {where}", *params
    )

    offset = (page - 1) * per_page
    rows = await db.fetch(
        f"""SELECT id, username, action, category, message_id, mailbox, folder,
                   target, ip_address, user_agent, details, risk_level, created_at
            FROM user_activity_log {where}
            ORDER BY created_at DESC
            LIMIT ${idx} OFFSET ${idx + 1}""",
        *params,
        per_page,
        offset,
    )

    return {
        "entries": [
            {
                **dict(r),
                "ip_address": str(r["ip_address"]) if r["ip_address"] else None,
                "created_at": r["created_at"].isoformat() if r["created_at"] else None,
            }
            for r in rows
        ],
        "total": total,
        "page": page,
        "per_page": per_page,
    }


async def get_activity_stats(db, days: int = 30) -> dict:
    """Estadísticas de actividad para dashboard."""
    stats = {}

    stats["total"] = await db.fetchval(
        "SELECT count(*) FROM user_activity_log WHERE created_at >= NOW() - make_interval(days => $1)",
        days,
    )

    rows = await db.fetch(
        """SELECT risk_level, count(*) as total FROM user_activity_log
           WHERE created_at >= NOW() - make_interval(days => $1)
           GROUP BY risk_level ORDER BY total DESC""",
        days,
    )
    stats["by_risk"] = {r["risk_level"]: r["total"] for r in rows}

    rows = await db.fetch(
        """SELECT category, count(*) as total FROM user_activity_log
           WHERE created_at >= NOW() - make_interval(days => $1)
           GROUP BY category ORDER BY total DESC""",
        days,
    )
    stats["by_category"] = {r["category"]: r["total"] for r in rows}

    rows = await db.fetch(
        """SELECT action, count(*) as total FROM user_activity_log
           WHERE created_at >= NOW() - make_interval(days => $1)
           GROUP BY action ORDER BY total DESC LIMIT 15""",
        days,
    )
    stats["top_actions"] = [dict(r) for r in rows]

    rows = await db.fetch(
        """SELECT username, count(*) as total FROM user_activity_log
           WHERE created_at >= NOW() - make_interval(days => $1)
           AND risk_level IN ('high', 'critical')
           GROUP BY username ORDER BY total DESC LIMIT 10""",
        days,
    )
    stats["high_risk_users"] = [dict(r) for r in rows]

    return stats
