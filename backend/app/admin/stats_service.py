import asyncio
from asyncio.subprocess import PIPE

import asyncpg


async def get_dashboard_stats(db: asyncpg.Pool) -> dict:
    domain_count = await db.fetchval(
        "SELECT count(*) FROM domain WHERE domain != 'ALL'"
    )
    mailbox_count = await db.fetchval("SELECT count(*) FROM mailbox")
    active_mailbox_count = await db.fetchval(
        "SELECT count(*) FROM mailbox WHERE active = true"
    )
    alias_count = await db.fetchval("SELECT count(*) FROM alias WHERE address != goto")

    return {
        "domains": domain_count,
        "mailboxes": mailbox_count,
        "active_mailboxes": active_mailbox_count,
        "aliases": alias_count,
    }


async def get_service_status() -> dict:
    services = ["postfix", "dovecot", "rspamd", "redis-server", "postgresql", "nginx"]
    statuses = {}

    for service in services:
        try:
            proc = await asyncio.create_subprocess_exec(
                "systemctl",
                "is-active",
                service,
                stdout=PIPE,
                stderr=PIPE,
            )
            stdout, _ = await proc.communicate()
            statuses[service] = stdout.decode().strip()
        except Exception:
            statuses[service] = "unknown"

    return statuses


async def get_mail_log_stats(db: asyncpg.Pool, hours: int = 24) -> dict:
    rows = await db.fetch(
        """SELECT status, count(*) as cnt
           FROM mail_log
           WHERE timestamp > NOW() - make_interval(hours => $1)
           GROUP BY status""",
        hours,
    )
    stats = {r["status"]: r["cnt"] for r in rows}

    total = await db.fetchval(
        """SELECT count(*) FROM mail_log
           WHERE timestamp > NOW() - make_interval(hours => $1)""",
        hours,
    )

    return {"total": total or 0, "by_status": stats}
