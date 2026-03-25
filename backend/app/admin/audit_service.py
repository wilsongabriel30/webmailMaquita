import asyncpg


async def log_action(
    db: asyncpg.Pool,
    admin_user: str,
    action: str,
    target: str | None = None,
    details: dict | None = None,
    ip_address: str | None = None,
) -> None:
    import json
    await db.execute(
        """INSERT INTO webmail.audit_log (admin_user, action, target, details, ip_address)
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

    where = " AND ".join(conditions)
    where_clause = f"WHERE {where}" if where else ""

    total = await db.fetchval(
        f"SELECT count(*) FROM webmail.audit_log {where_clause}", *params
    )

    offset = (page - 1) * per_page
    rows = await db.fetch(
        f"""SELECT id, admin_user, action, target, details, ip_address, created_at
            FROM webmail.audit_log {where_clause}
            ORDER BY created_at DESC
            LIMIT ${idx} OFFSET ${idx + 1}""",
        *params, per_page, offset,
    )

    return {
        "entries": [dict(r) for r in rows],
        "total": total,
        "page": page,
        "per_page": per_page,
    }
