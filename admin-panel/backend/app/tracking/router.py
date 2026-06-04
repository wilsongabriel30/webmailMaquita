from fastapi import APIRouter, Request, Depends, Query
from app.auth.dependencies import get_current_admin

router = APIRouter(prefix="/api/tracking", tags=["tracking"])


@router.get("")
async def get_tracking(
    request: Request,
    search: str = Query(None, description="Buscar por email, dominio o queue_id"),
    limit: int = Query(200, ge=10, le=1000),
    admin: dict = Depends(get_current_admin),
):
    """Rastreo de mensajes desde la tabla mail_trace (datos reales del log ingestor)."""
    pool = request.app.state.db

    if search:
        s = f"%{search.lower()}%"
        rows = await pool.fetch(
            """SELECT queue_id, message_id, sender, recipient, status, size_bytes,
                      relay, dsn, delay_seconds, direction, source_ip,
                      spf_result, dkim_result, dmarc_result, rspamd_score,
                      tls_version, created_at
               FROM mail_trace
               WHERE LOWER(sender) LIKE $1
                  OR LOWER(recipient) LIKE $1
                  OR LOWER(queue_id) LIKE $1
                  OR LOWER(COALESCE(message_id,'')) LIKE $1
               ORDER BY created_at DESC
               LIMIT $2""",
            s, limit,
        )
    else:
        rows = await pool.fetch(
            """SELECT queue_id, message_id, sender, recipient, status, size_bytes,
                      relay, dsn, delay_seconds, direction, source_ip,
                      spf_result, dkim_result, dmarc_result, rspamd_score,
                      tls_version, created_at
               FROM mail_trace
               ORDER BY created_at DESC
               LIMIT $1""",
            limit,
        )

    entries = []
    for r in rows:
        entries.append({
            "queue_id": r["queue_id"] or "",
            "date": r["created_at"].isoformat() if r["created_at"] else "",
            "from": r["sender"] or "",
            "to": [r["recipient"]] if r["recipient"] else [],
            "status": r["status"] or "",
            "size": r["size_bytes"] or 0,
            "relay": r["relay"] or "",
            "delay": str(r["delay_seconds"] or ""),
            "dsn": r["dsn"] or "",
            "direction": r["direction"] or "",
            "source_ip": r["source_ip"] or "",
            "spf": r["spf_result"] or "",
            "dkim": r["dkim_result"] or "",
            "dmarc": r["dmarc_result"] or "",
            "rspamd_score": float(r["rspamd_score"]) if r["rspamd_score"] else None,
            "tls": r["tls_version"] or "",
        })

    # Summary counts from full dataset (with or without filter)
    if search:
        s = f"%{search.lower()}%"
        summary = await pool.fetchrow(
            """SELECT
                 count(*) AS total,
                 count(*) FILTER (WHERE status = 'sent') AS sent,
                 count(*) FILTER (WHERE status = 'bounced') AS bounced,
                 count(*) FILTER (WHERE status = 'deferred') AS deferred,
                 count(*) FILTER (WHERE status IN ('reject','rejected')) AS rejected
               FROM mail_trace
               WHERE LOWER(sender) LIKE $1
                  OR LOWER(recipient) LIKE $1
                  OR LOWER(queue_id) LIKE $1
                  OR LOWER(COALESCE(message_id,'')) LIKE $1""",
            s,
        )
    else:
        summary = await pool.fetchrow(
            """SELECT
                 count(*) AS total,
                 count(*) FILTER (WHERE status = 'sent') AS sent,
                 count(*) FILTER (WHERE status = 'bounced') AS bounced,
                 count(*) FILTER (WHERE status = 'deferred') AS deferred,
                 count(*) FILTER (WHERE status IN ('reject','rejected')) AS rejected
               FROM mail_trace"""
        )

    return {
        "summary": {
            "total": summary["total"],
            "sent": summary["sent"],
            "bounced": summary["bounced"],
            "deferred": summary["deferred"],
            "rejected": summary["rejected"],
        },
        "entries": entries,
    }


@router.get("/search/{email}")
async def track_email(
    request: Request,
    email: str,
    admin: dict = Depends(get_current_admin),
):
    """Rastrear un email especifico."""
    pool = request.app.state.db
    s = f"%{email.lower()}%"
    rows = await pool.fetch(
        """SELECT queue_id, message_id, sender, recipient, status, size_bytes,
                  relay, dsn, delay_seconds, direction, source_ip, created_at
           FROM mail_trace
           WHERE LOWER(sender) LIKE $1 OR LOWER(recipient) LIKE $1
           ORDER BY created_at DESC
           LIMIT 500""",
        s,
    )
    entries = [
        {
            "queue_id": r["queue_id"] or "",
            "date": r["created_at"].isoformat() if r["created_at"] else "",
            "from": r["sender"] or "",
            "to": [r["recipient"]] if r["recipient"] else [],
            "status": r["status"] or "",
            "size": r["size_bytes"] or 0,
            "relay": r["relay"] or "",
            "delay": str(r["delay_seconds"] or ""),
            "dsn": r["dsn"] or "",
        }
        for r in rows
    ]
    return {"email": email, "entries": entries}
