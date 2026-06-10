"""Safe Links — servicio: configuración, lista negra, decisión final y registro."""
from . import checker


async def get_config(db) -> dict:
    try:
        row = await db.fetchrow(
            "SELECT enabled, rewrite_enabled, warn_suspicious, block_listed FROM safelinks_config WHERE id = 1")
    except Exception:
        return {"enabled": False, "rewrite_enabled": True, "warn_suspicious": True, "block_listed": True}
    if not row:
        return {"enabled": True, "rewrite_enabled": True, "warn_suspicious": True, "block_listed": True}
    return dict(row)


async def get_blocklist(db) -> list[tuple[str, str]]:
    try:
        rows = await db.fetch("SELECT pattern, kind FROM safelinks_blocklist")
        return [((r["pattern"] or "").lower(), r["kind"]) for r in rows]
    except Exception:
        return []


async def check_url(db, url: str, redis=None) -> dict:
    cfg = await get_config(db)
    res = checker.analyze(url)
    host = res["host"]
    low = (url or "").lower()
    if cfg["block_listed"]:
        for pat, kind in await get_blocklist(db):
            if not pat:
                continue
            if kind == "domain" and host and (host == pat or host.endswith("." + pat)):
                return {"verdict": "blocked", "reason": f"Dominio en lista negra ({pat})", "host": host}
            if kind == "url" and pat in low:
                return {"verdict": "blocked", "reason": "Dirección en lista negra", "host": host}
            if kind == "keyword" and pat in low:
                return {"verdict": "blocked", "reason": f"Contiene un término bloqueado ({pat})", "host": host}
    if res["verdict"] == "suspicious" and not cfg["warn_suspicious"]:
        return {"verdict": "safe", "reason": "", "host": host}
    if redis is not None:
        try:
            from . import threatfeeds
            reg = checker._registrable(host) if host else ""
            ti = await threatfeeds.classify(redis, host, reg)
            if ti:
                return {"verdict": ti[0], "reason": ti[1], "host": host}
        except Exception:
            pass
    return res


async def log_click(db, username: str, url: str, host: str, verdict: str,
                    proceeded: bool, ip: str) -> None:
    try:
        await db.execute(
            "INSERT INTO safelinks_clicks (username,url,host,verdict,proceeded,ip) "
            "VALUES ($1,$2,$3,$4,$5,$6)",
            username or "", (url or "")[:2000], host or "", verdict, proceeded, ip or "")
    except Exception:
        pass
