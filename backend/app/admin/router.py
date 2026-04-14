from fastapi import APIRouter, Request, HTTPException, Depends, Query
from fastapi.responses import StreamingResponse

from app.auth.dependencies import require_admin
from app.admin import domains_service, mailboxes_service, aliases_service
from app.admin import queue_service, audit_service, stats_service

import csv
import io
import json

router = APIRouter(prefix="/api/admin", tags=["admin"])


def _get_db(request: Request):
    return request.app.state.db_pool


def _get_ip(request: Request) -> str:
    return request.headers.get("X-Real-IP", request.client.host if request.client else "unknown")


async def _audit(request: Request, admin: str, action: str, target: str = None, details: dict = None):
    await audit_service.log_action(
        _get_db(request), admin, action, target, details, _get_ip(request)
    )


# -- Dashboard --

@router.get("/dashboard")
async def dashboard(request: Request, admin: str = Depends(require_admin)):
    db = _get_db(request)
    stats = await stats_service.get_dashboard_stats(db)
    services = await stats_service.get_service_status()
    return {"stats": stats, "services": services}


@router.get("/dashboard/mail-stats")
async def mail_stats(request: Request, hours: int = 24, admin: str = Depends(require_admin)):
    db = _get_db(request)
    return await stats_service.get_mail_log_stats(db, hours)


# -- Domains --

@router.get("/domains")
async def list_domains(request: Request, admin: str = Depends(require_admin)):
    return await domains_service.list_domains(_get_db(request))


@router.get("/domains/{domain}")
async def get_domain(domain: str, request: Request, admin: str = Depends(require_admin)):
    result = await domains_service.get_domain(_get_db(request), domain)
    if not result:
        raise HTTPException(404, "Domain not found")
    return result


@router.post("/domains", status_code=201)
async def create_domain(request: Request, admin: str = Depends(require_admin)):
    data = await request.json()
    domain_name = data.get("domain", "").strip().lower()
    if not domain_name:
        raise HTTPException(400, "Domain name required")

    try:
        result = await domains_service.create_domain(
            _get_db(request),
            domain=domain_name,
            description=data.get("description", ""),
            aliases=data.get("aliases", 0),
            mailboxes=data.get("mailboxes", 0),
            maxquota=data.get("maxquota", 0),
            quota=data.get("quota", 0),
            active=data.get("active", True),
        )
    except Exception as e:
        raise HTTPException(400, str(e))

    await _audit(request, admin, "domain_create", domain_name)
    return result


@router.put("/domains/{domain}")
async def update_domain(domain: str, request: Request, admin: str = Depends(require_admin)):
    data = await request.json()
    result = await domains_service.update_domain(
        _get_db(request),
        domain=domain,
        description=data.get("description"),
        aliases=data.get("aliases"),
        mailboxes=data.get("mailboxes"),
        maxquota=data.get("maxquota"),
        quota=data.get("quota"),
        active=data.get("active"),
    )
    if not result:
        raise HTTPException(404, "Domain not found")

    await _audit(request, admin, "domain_update", domain, data)
    return result


@router.delete("/domains/{domain}")
async def delete_domain(domain: str, request: Request, admin: str = Depends(require_admin)):
    try:
        ok = await domains_service.delete_domain(_get_db(request), domain)
    except ValueError as e:
        raise HTTPException(400, str(e))
    if not ok:
        raise HTTPException(404, "Domain not found")

    await _audit(request, admin, "domain_delete", domain)
    return {"ok": True}


# -- Mailboxes --

@router.get("/mailboxes")
async def list_mailboxes(request: Request, domain: str = None, admin: str = Depends(require_admin)):
    return await mailboxes_service.list_mailboxes(_get_db(request), domain)


@router.get("/mailboxes/{username:path}")
async def get_mailbox(username: str, request: Request, admin: str = Depends(require_admin)):
    result = await mailboxes_service.get_mailbox(_get_db(request), username)
    if not result:
        raise HTTPException(404, "Mailbox not found")
    return result


@router.post("/mailboxes", status_code=201)
async def create_mailbox(request: Request, admin: str = Depends(require_admin)):
    data = await request.json()
    username = data.get("username", "").strip().lower()
    password = data.get("password", "")
    if not username or not password:
        raise HTTPException(400, "Username and password required")
    if "@" not in username:
        raise HTTPException(400, "Username must be in user@domain format")

    try:
        result = await mailboxes_service.create_mailbox(
            _get_db(request),
            username=username,
            password=password,
            name=data.get("name", ""),
            quota=data.get("quota", 0),
            active=data.get("active", True),
        )
    except Exception as e:
        raise HTTPException(400, str(e))

    await _audit(request, admin, "mailbox_create", username)
    return result


@router.put("/mailboxes/{username:path}")
async def update_mailbox(username: str, request: Request, admin: str = Depends(require_admin)):
    data = await request.json()
    result = await mailboxes_service.update_mailbox(
        _get_db(request),
        username=username,
        name=data.get("name"),
        password=data.get("password"),
        quota=data.get("quota"),
        active=data.get("active"),
        phone=data.get("phone"),
        email_other=data.get("email_other"),
    )
    if not result:
        raise HTTPException(404, "Mailbox not found")

    await _audit(request, admin, "mailbox_update", username, {k: v for k, v in data.items() if k != "password"})
    return result


@router.delete("/mailboxes/{username:path}")
async def delete_mailbox(username: str, request: Request, admin: str = Depends(require_admin)):
    ok = await mailboxes_service.delete_mailbox(_get_db(request), username)
    if not ok:
        raise HTTPException(404, "Mailbox not found")

    await _audit(request, admin, "mailbox_delete", username)
    return {"ok": True}


@router.post("/mailboxes/{username:path}/toggle-active")
async def toggle_mailbox_active(username: str, request: Request, admin: str = Depends(require_admin)):
    result = await mailboxes_service.toggle_active(_get_db(request), username)
    if not result:
        raise HTTPException(404, "Mailbox not found")

    await _audit(request, admin, "mailbox_toggle_active", username, {"active": result["active"]})
    return result


# -- Aliases --

@router.get("/aliases")
async def list_aliases(request: Request, domain: str = None, admin: str = Depends(require_admin)):
    return await aliases_service.list_aliases(_get_db(request), domain)


@router.post("/aliases", status_code=201)
async def create_alias(request: Request, admin: str = Depends(require_admin)):
    data = await request.json()
    address = data.get("address", "").strip().lower()
    goto = data.get("goto", "").strip().lower()
    if not address or not goto:
        raise HTTPException(400, "Address and goto required")

    try:
        result = await aliases_service.create_alias(
            _get_db(request), address=address, goto=goto, active=data.get("active", True)
        )
    except Exception as e:
        raise HTTPException(400, str(e))

    await _audit(request, admin, "alias_create", address, {"goto": goto})
    return result


@router.put("/aliases/{address:path}")
async def update_alias(address: str, request: Request, admin: str = Depends(require_admin)):
    data = await request.json()
    result = await aliases_service.update_alias(
        _get_db(request), address=address, goto=data.get("goto"), active=data.get("active")
    )
    if not result:
        raise HTTPException(404, "Alias not found")

    await _audit(request, admin, "alias_update", address, data)
    return result


@router.delete("/aliases/{address:path}")
async def delete_alias(address: str, request: Request, admin: str = Depends(require_admin)):
    ok = await aliases_service.delete_alias(_get_db(request), address)
    if not ok:
        raise HTTPException(404, "Alias not found")

    await _audit(request, admin, "alias_delete", address)
    return {"ok": True}


# -- Queue --

@router.get("/queue")
async def get_queue(request: Request, admin: str = Depends(require_admin)):
    return await queue_service.get_queue()


@router.post("/queue/action")
async def queue_action(request: Request, admin: str = Depends(require_admin)):
    data = await request.json()
    action = data.get("action", "")
    queue_id = data.get("queue_id")

    try:
        ok = await queue_service.queue_action(action, queue_id)
    except ValueError as e:
        raise HTTPException(400, str(e))
    except RuntimeError as e:
        raise HTTPException(500, str(e))

    await _audit(request, admin, f"queue_{action}", queue_id)
    return {"ok": ok}


# -- Audit Log --

@router.get("/audit-log")
async def get_audit_log(
    request: Request,
    page: int = 1,
    per_page: int = 50,
    admin_user: str = None,
    action: str = None,
    target: str = None,
    date_from: str = None,
    date_to: str = None,
    admin: str = Depends(require_admin),
):
    return await audit_service.get_audit_log(
        _get_db(request), page, per_page, admin_user, action, target, date_from, date_to
    )


@router.get("/audit-log/export")
async def export_audit_log(
    request: Request,
    admin_user: str = None,
    action: str = None,
    date_from: str = None,
    date_to: str = None,
    admin: str = Depends(require_admin),
):
    """Export audit log as CSV for compliance."""
    rows = await audit_service.get_audit_export(
        _get_db(request), admin_user, action, date_from, date_to
    )

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["id", "admin_user", "action", "target", "details", "ip_address", "created_at"])
    for row in rows:
        writer.writerow([
            row["id"],
            row["admin_user"],
            row["action"],
            row["target"],
            json.dumps(row["details"]) if row["details"] else "",
            str(row["ip_address"]) if row["ip_address"] else "",
            row["created_at"].isoformat() if row["created_at"] else "",
        ])

    output.seek(0)
    await _audit(request, admin, "audit_export", None, {"filters": {"admin_user": admin_user, "action": action, "date_from": date_from, "date_to": date_to}})

    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=audit-log.csv"},
    )


@router.get("/audit-log/stats")
async def audit_stats(
    request: Request,
    days: int = 30,
    admin: str = Depends(require_admin),
):
    """Audit log statistics: actions per day, top admins, top actions."""
    return await audit_service.get_audit_stats(_get_db(request), days)


# ── Corporate Disclaimer / Footer ─────────────────────────

@router.get("/disclaimer")
async def get_disclaimer(request: Request, admin: str = Depends(require_admin)):
    """Get current corporate disclaimer settings."""
    db = request.app.state.db_pool
    await db.execute("""
        CREATE TABLE IF NOT EXISTS corporate_disclaimer (
            id SERIAL PRIMARY KEY,
            domain TEXT NOT NULL UNIQUE,
            html_footer TEXT NOT NULL DEFAULT '',
            text_footer TEXT NOT NULL DEFAULT '',
            is_active BOOLEAN NOT NULL DEFAULT TRUE,
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)
    rows = await db.fetch("SELECT * FROM corporate_disclaimer ORDER BY domain")
    return [dict(r) for r in rows]


@router.post("/disclaimer", status_code=201)
async def upsert_disclaimer(request: Request, admin: str = Depends(require_admin)):
    """Create or update corporate disclaimer for a domain."""
    data = await request.json()
    domain = data.get("domain", "").strip()
    html_footer = data.get("html_footer", "").strip()
    text_footer = data.get("text_footer", "").strip()
    is_active = data.get("is_active", True)
    if not domain:
        raise HTTPException(400, "Dominio requerido")
    db = request.app.state.db_pool
    await db.execute("""
        CREATE TABLE IF NOT EXISTS corporate_disclaimer (
            id SERIAL PRIMARY KEY,
            domain TEXT NOT NULL UNIQUE,
            html_footer TEXT NOT NULL DEFAULT '',
            text_footer TEXT NOT NULL DEFAULT '',
            is_active BOOLEAN NOT NULL DEFAULT TRUE,
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)
    row = await db.fetchrow("""
        INSERT INTO corporate_disclaimer (domain, html_footer, text_footer, is_active)
        VALUES (, , , )
        ON CONFLICT (domain) DO UPDATE SET
            html_footer = EXCLUDED.html_footer,
            text_footer = EXCLUDED.text_footer,
            is_active = EXCLUDED.is_active,
            updated_at = NOW()
        RETURNING *
    """, domain, html_footer, text_footer, is_active)
    await _audit(request, admin, "disclaimer_update", domain)
    return dict(row)


@router.delete("/disclaimer/{domain}")
async def delete_disclaimer(domain: str, request: Request, admin: str = Depends(require_admin)):
    """Delete disclaimer for a domain."""
    db = request.app.state.db_pool
    await db.execute("DELETE FROM corporate_disclaimer WHERE domain = ", domain)
    return {"ok": True}



# ── Message Tracking / Mail Trace ─────────────────────────

@router.get("/message-tracking")
async def track_message(
    request: Request,
    q: str = Query("", description="Message-ID, sender email, or recipient email"),
    hours: int = Query(24, description="Search last N hours"),
    admin: str = Depends(require_admin),
):
    """Search Postfix logs for message delivery tracking."""
    import subprocess
    import re
    from datetime import datetime, timedelta

    if not q or len(q) < 3:
        raise HTTPException(400, "Consulta muy corta (min 3 caracteres)")

    # Sanitize input
    q_safe = re.sub(r"[^a-zA-Z0-9@._\-<>]", "", q)

    # Search in Postfix logs
    try:
        result = subprocess.run(
            ["grep", "-i", q_safe, "/var/log/mail.log"],
            capture_output=True, text=True, timeout=30,
        )
        lines = result.stdout.strip().split("\n") if result.stdout.strip() else []

        # Parse log entries
        entries = []
        for line in lines[-200:]:  # Last 200 matches
            entry = {"raw": line}
            # Extract queue ID
            qid_match = re.search(r": ([A-F0-9]{10,}): ", line)
            if qid_match:
                entry["queue_id"] = qid_match.group(1)
            # Extract from=
            from_match = re.search(r"from=<([^>]*)>", line)
            if from_match:
                entry["from"] = from_match.group(1)
            # Extract to=
            to_match = re.search(r"to=<([^>]*)>", line)
            if to_match:
                entry["to"] = to_match.group(1)
            # Extract status
            status_match = re.search(r"status=(\w+)", line)
            if status_match:
                entry["status"] = status_match.group(1)
            # Extract dsn
            dsn_match = re.search(r"dsn=([0-9.]+)", line)
            if dsn_match:
                entry["dsn"] = dsn_match.group(1)
            # Extract timestamp (syslog format)
            ts_match = re.match(r"^(\w{3}\s+\d+\s+\d+:\d+:\d+)", line)
            if ts_match:
                entry["timestamp"] = ts_match.group(1)

            entries.append(entry)

        return {
            "query": q_safe,
            "results": len(entries),
            "entries": entries,
        }
    except subprocess.TimeoutExpired:
        raise HTTPException(504, "Búsqueda en logs timeout")
    except Exception as e:
        raise HTTPException(500, f"Error buscando en logs: {str(e)}")



# ═══════════════════════════════════════════════════════════════
# Seguridad de cuentas — protección anti-compromiso
# ═══════════════════════════════════════════════════════════════
from app.security.account_protection import (
    get_account_status, admin_unblock_account, admin_approve_forward
)


@router.get("/security/incidents")
async def get_security_incidents(
    request: Request,
    limit: int = 50,
    admin: str = Depends(require_admin),
):
    """Ver incidentes de seguridad recientes."""
    import json
    redis = request.app.state.redis
    raw = await redis.lrange("security_incidents", 0, limit - 1)
    incidents = [json.loads(r) for r in raw]
    return {"total": len(incidents), "incidents": incidents}


@router.get("/security/account/{username}")
async def get_account_security_status(
    request: Request,
    username: str,
    admin: str = Depends(require_admin),
):
    """Ver estado de seguridad de una cuenta específica."""
    return await get_account_status(request.app.state.redis, username)


@router.post("/security/unblock/{username}")
async def unblock_account(
    request: Request,
    username: str,
    admin: str = Depends(require_admin),
):
    """Desbloquear una cuenta bloqueada por actividad sospechosa."""
    await admin_unblock_account(request.app.state.redis, username)
    return {"status": "ok", "message": f"Cuenta {username} desbloqueada"}


@router.post("/security/approve-forward")
async def approve_forward(
    request: Request,
    body: dict,
    admin: str = Depends(require_admin),
):
    """Aprobar forwarding externo para un usuario.
    Body: {"username": "user@maquita.org", "forward_address": "user@gmail.com"}
    """
    username = body.get("username", "")
    forward_address = body.get("forward_address", "")
    if not username or not forward_address:
        raise HTTPException(400, "username y forward_address requeridos")

    await admin_approve_forward(
        request.app.state.redis, request.app.state.db_pool,
        username, forward_address, admin
    )
    return {"status": "ok", "message": f"Forward aprobado: {username} → {forward_address}"}


@router.get("/security/approved-forwards")
async def list_approved_forwards(
    request: Request,
    admin: str = Depends(require_admin),
):
    """Listar todos los forwards externos aprobados."""
    db = request.app.state.db_pool
    rows = await db.fetch(
        "SELECT username, forward_address, approved_by, created_at FROM approved_forwards WHERE is_active = TRUE ORDER BY created_at DESC"
    )
    return [dict(r) for r in rows]


@router.delete("/security/approved-forwards/{username}/{forward_address}")
async def revoke_forward(
    request: Request,
    username: str,
    forward_address: str,
    admin: str = Depends(require_admin),
):
    """Revocar un forward externo aprobado."""
    db = request.app.state.db_pool
    await db.execute(
        "UPDATE approved_forwards SET is_active = FALSE WHERE username = $1 AND forward_address = $2",
        username, forward_address
    )
    redis = request.app.state.redis
    await redis.srem(f"approved_forwards:{username}", forward_address.lower())
    return {"status": "ok", "message": f"Forward revocado: {username} → {forward_address}"}


@router.get("/security/blocked-accounts")
async def list_blocked_accounts(
    request: Request,
    admin: str = Depends(require_admin),
):
    """Listar cuentas actualmente bloqueadas por anomalía."""
    redis = request.app.state.redis
    # Scan for all account_blocked:* keys
    blocked = []
    cursor = 0
    while True:
        cursor, keys = await redis.scan(cursor, match="account_blocked:*", count=100)
        for key in keys:
            username = key.split(":", 1)[1] if isinstance(key, str) else key.decode().split(":", 1)[1]
            reason = await redis.get(key)
            ttl = await redis.ttl(key)
            blocked.append({
                "username": username,
                "reason": reason.decode() if isinstance(reason, bytes) else reason,
                "ttl_seconds": max(0, ttl),
            })
        if cursor == 0:
            break
    return {"blocked_accounts": blocked}
