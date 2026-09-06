import json
from datetime import datetime

import asyncpg


async def log_action(
    db: asyncpg.Pool,
    admin_user: str,
    action: str,
    target: str | None = None,
    details: dict | None = None,
    ip_address: str | None = None,
) -> None:
    await db.execute(
        """INSERT INTO audit_log (admin_user, action, target, details, ip_address)
           VALUES ($1, $2, $3, $4::jsonb, $5::inet)""",
        admin_user,
        action,
        target,
        json.dumps(details) if details else None,
        ip_address,
    )


async def get_audit_log(
    db: asyncpg.Pool,
    page: int = 1,
    per_page: int = 50,
    admin_user: str | None = None,
    action: str | None = None,
    target: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
) -> dict:
    conditions = []
    params = []
    idx = 1

    if admin_user:
        conditions.append(f"admin_user = ${idx}")
        params.append(admin_user)
        idx += 1
    if action:
        conditions.append(f"action = ${idx}")
        params.append(action)
        idx += 1
    if target:
        conditions.append(f"target ILIKE ${idx}")
        params.append(f"%{target}%")
        idx += 1
    if date_from:
        conditions.append(f"created_at >= ${idx}::timestamptz")
        params.append(date_from)
        idx += 1
    if date_to:
        conditions.append(f"created_at <= ${idx}::timestamptz")
        params.append(date_to)
        idx += 1

    where = " AND ".join(conditions)
    where_clause = f"WHERE {where}" if where else ""

    total = await db.fetchval(f"SELECT count(*) FROM audit_log {where_clause}", *params)

    offset = (page - 1) * per_page
    rows = await db.fetch(
        f"""SELECT id, admin_user, action, target, details, ip_address, created_at
            FROM audit_log {where_clause}
            ORDER BY created_at DESC
            LIMIT ${idx} OFFSET ${idx + 1}""",
        *params,
        per_page,
        offset,
    )

    return {
        "entries": [dict(r) for r in rows],
        "total": total,
        "page": page,
        "per_page": per_page,
    }


async def get_audit_export(
    db: asyncpg.Pool,
    admin_user: str | None = None,
    action: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
) -> list[dict]:
    conditions = []
    params = []
    idx = 1

    if admin_user:
        conditions.append(f"admin_user = ${idx}")
        params.append(admin_user)
        idx += 1
    if action:
        conditions.append(f"action = ${idx}")
        params.append(action)
        idx += 1
    if date_from:
        conditions.append(f"created_at >= ${idx}::timestamptz")
        params.append(date_from)
        idx += 1
    if date_to:
        conditions.append(f"created_at <= ${idx}::timestamptz")
        params.append(date_to)
        idx += 1

    where = " AND ".join(conditions)
    where_clause = f"WHERE {where}" if where else ""

    rows = await db.fetch(
        f"""SELECT id, admin_user, action, target, details, ip_address, created_at
            FROM audit_log {where_clause}
            ORDER BY created_at DESC
            LIMIT 10000""",
        *params,
    )
    return [dict(r) for r in rows]


async def get_audit_stats(
    db: asyncpg.Pool,
    days: int = 30,
) -> dict:
    actions_per_day = await db.fetch(
        """SELECT date_trunc('day', created_at)::date AS day, count(*) AS total
            FROM audit_log
            WHERE created_at >= NOW() - make_interval(days => $1)
            GROUP BY day ORDER BY day DESC""",
        days,
    )

    top_admins = await db.fetch(
        """SELECT admin_user, count(*) AS total
            FROM audit_log
            WHERE created_at >= NOW() - make_interval(days => $1)
            GROUP BY admin_user ORDER BY total DESC LIMIT 10""",
        days,
    )

    top_actions = await db.fetch(
        """SELECT action, count(*) AS total
            FROM audit_log
            WHERE created_at >= NOW() - make_interval(days => $1)
            GROUP BY action ORDER BY total DESC LIMIT 10""",
        days,
    )

    total = await db.fetchval(
        "SELECT count(*) FROM audit_log WHERE created_at >= NOW() - make_interval(days => $1)",
        days,
    )

    return {
        "period_days": days,
        "total_actions": total,
        "actions_per_day": [dict(r) for r in actions_per_day],
        "top_admins": [dict(r) for r in top_admins],
        "top_actions": [dict(r) for r in top_actions],
    }
