import asyncio
from fastapi import APIRouter, Request, Depends
from app.auth.dependencies import get_current_admin
from app.wrappers import rspamd, doveadm

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


def _db(r: Request):
    return r.app.state.db


@router.get("")
async def dashboard(request: Request, admin: dict = Depends(get_current_admin)):
    db = _db(request)

    stats_q = db.fetchrow("""
        SELECT
            (SELECT count(*) FROM domain WHERE domain != 'ALL') as domains,
            (SELECT count(*) FROM mailbox) as mailboxes,
            (SELECT count(*) FROM mailbox WHERE active = true) as active_mailboxes,
            (SELECT count(*) FROM alias WHERE address != goto) as aliases,
            (SELECT COALESCE(SUM(quota), 0) FROM mailbox) as total_quota
    """)

    services_q = _get_services()
    rspamd_q = _safe_rspamd_stat()
    connections_q = _safe_connections()

    stats, services, rspamd_stat, conns = await asyncio.gather(
        stats_q, services_q, rspamd_q, connections_q
    )

    return {
        "stats": dict(stats) if stats else {},
        "services": services,
        "rspamd": rspamd_stat,
        "active_connections": len(conns),
        "connections": conns[:10],
    }


@router.get("/mail-volume")
async def mail_volume(request: Request, hours: int = 24, admin: dict = Depends(get_current_admin)):
    """Estadisticas de volumen de correo por hora."""
    rspamd_hist = await rspamd.get_history(limit=200)
    # Group by hour
    from collections import defaultdict
    by_hour = defaultdict(lambda: {"total": 0, "spam": 0, "ham": 0, "reject": 0})
    for row in rspamd_hist:
        ts = row.get("time", "")
        hour = ts[:13] if len(ts) >= 13 else ts
        action = row.get("action", "")
        by_hour[hour]["total"] += 1
        if action in ("reject", "soft reject"):
            by_hour[hour]["reject"] += 1
            by_hour[hour]["spam"] += 1
        elif action == "add header":
            by_hour[hour]["spam"] += 1
        else:
            by_hour[hour]["ham"] += 1

    return {"hours": dict(by_hour), "total_scanned": len(rspamd_hist)}


@router.get("/storage")
async def storage_overview(request: Request, admin: dict = Depends(get_current_admin)):
    """Uso por dominio (CACHEADO; lo calcula deploy/tools/calc-storage.sh por cron con la quota de Dovecot, sin caminar 2TB)."""
    import json as _json
    try:
        data = await _db(request).fetchval("SELECT data FROM dashboard_cache WHERE key='storage'")
        if data:
            return _json.loads(data) if isinstance(data, str) else data
    except Exception:
        pass
    return {}


def _dir_size(path: str) -> int:
    import os
    total = 0
    for dirpath, _, filenames in os.walk(path):
        for f in filenames:
            fp = os.path.join(dirpath, f)
            try:
                total += os.path.getsize(fp)
            except OSError:
                pass
    return total


async def _get_services() -> dict:
    import asyncio as aio
    from asyncio.subprocess import PIPE
    services = ["postfix", "dovecot", "rspamd", "redis-server", "postgresql", "nginx", "clamav-daemon", "fail2ban"]
    statuses = {}
    for svc in services:
        try:
            proc = await aio.create_subprocess_exec("systemctl", "is-active", svc, stdout=PIPE, stderr=PIPE)
            out, _ = await proc.communicate()
            statuses[svc] = out.decode().strip()
        except Exception:
            statuses[svc] = "unknown"
    return statuses


async def _safe_rspamd_stat() -> dict:
    try:
        return await rspamd.get_stat()
    except Exception:
        return {}


async def _safe_connections() -> list:
    try:
        return await doveadm.get_who()
    except Exception:
        return []
