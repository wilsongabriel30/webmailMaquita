import asyncio
import csv
import io
import json

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse

from app.admin import (
    aliases_service,
    audit_service,
    domains_service,
    login_health_service,
    mailboxes_service,
    outbound_service,
    queue_service,
    stats_service,
)
from app.auth.bootstrap import clave_inicial_aleatoria, marcar_cambio_obligatorio
from app.auth.dependencies import require_admin
from app.auth.sesiones import revocar_todo

router = APIRouter(prefix="/api/admin", tags=["admin"])


def _get_db(request: Request):
    return request.app.state.db_pool


def _get_ip(request: Request) -> str:
    return request.headers.get(
        "X-Real-IP", request.client.host if request.client else "unknown"
    )


async def _audit(
    request: Request, admin: str, action: str, target: str = None, details: dict = None
):
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
async def mail_stats(
    request: Request, hours: int = 24, admin: str = Depends(require_admin)
):
    db = _get_db(request)
    return await stats_service.get_mail_log_stats(db, hours)


# -- Domains --


# ---- Auditoria de claves (seguridad de migracion) ----
@router.get("/password-audit")
async def password_audit(request: Request, admin: str = Depends(require_admin)):
    from app.admin import password_audit_service

    return await password_audit_service.audit(_get_db(request))


@router.post("/password-audit/reset")
async def password_audit_reset(request: Request, admin: str = Depends(require_admin)):
    data = await request.json()
    username = (data.get("username") or "").strip().lower()
    if "@" not in username:
        raise HTTPException(400, "username requerido")
    temp = clave_inicial_aleatoria()
    try:
        result = await mailboxes_service.update_mailbox(
            _get_db(request), username=username, password=temp, active=True
        )
    except ValueError as e:
        raise HTTPException(400, str(e))
    if not result:
        raise HTTPException(404, "Mailbox not found")
    # F-01: la clave temporal invalida todas las sesiones del usuario.
    await revocar_todo(
        _get_db(request), request.app.state.redis, username, "reset_admin"
    )
    await marcar_cambio_obligatorio(
        _get_db(request), request.app.state.redis, username, True
    )
    await _audit(request, admin, "password_reset_temp", username)
    return {"username": username, "temp_password": temp}


@router.get("/domains")
async def list_domains(request: Request, admin: str = Depends(require_admin)):
    return await domains_service.list_domains(_get_db(request))


@router.get("/domains/{domain}")
async def get_domain(
    domain: str, request: Request, admin: str = Depends(require_admin)
):
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
async def update_domain(
    domain: str, request: Request, admin: str = Depends(require_admin)
):
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
async def delete_domain(
    domain: str, request: Request, admin: str = Depends(require_admin)
):
    try:
        ok = await domains_service.delete_domain(_get_db(request), domain)
    except ValueError as e:
        raise HTTPException(400, str(e))
    if not ok:
        raise HTTPException(404, "Domain not found")

    await _audit(request, admin, "domain_delete", domain)
    return {"ok": True}


# -- Mailboxes --


@router.get("/login-health")
async def login_health(
    request: Request, hours: int = 24, admin: str = Depends(require_admin)
):
    return await asyncio.to_thread(login_health_service.login_health, hours)


@router.get("/mailboxes")
async def list_mailboxes(
    request: Request, domain: str = None, admin: str = Depends(require_admin)
):
    return await mailboxes_service.list_mailboxes(_get_db(request), domain)


@router.get("/mailboxes/{username:path}")
async def get_mailbox(
    username: str, request: Request, admin: str = Depends(require_admin)
):
    result = await mailboxes_service.get_mailbox(_get_db(request), username)
    if not result:
        raise HTTPException(404, "Mailbox not found")
    return result


@router.post("/mailboxes", status_code=201)
async def create_mailbox(request: Request, admin: str = Depends(require_admin)):
    data = await request.json()
    username = data.get("username", "").strip().lower()
    # H-01: si el admin no da contraseña, se genera una aleatoria de un solo uso; en
    # ambos casos el buzón nace con cambio obligatorio.
    password = data.get("password", "")
    clave_generada = None
    if not password:
        password = clave_generada = clave_inicial_aleatoria()
    if not username:
        raise HTTPException(400, "Username required")
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

    await marcar_cambio_obligatorio(
        _get_db(request), request.app.state.redis, username, True
    )
    await _audit(request, admin, "mailbox_create", username)
    if clave_generada:
        result = dict(result or {})
        result["clave_inicial"] = clave_generada  # se muestra UNA vez
    return result


@router.put("/mailboxes/{username:path}")
async def update_mailbox(
    username: str, request: Request, admin: str = Depends(require_admin)
):
    data = await request.json()
    try:
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
    except ValueError as e:
        raise HTTPException(400, str(e))
    if not result:
        raise HTTPException(404, "Mailbox not found")

    await _audit(
        request,
        admin,
        "mailbox_update",
        username,
        {k: v for k, v in data.items() if k != "password"},
    )
    # CONSISTENCIA: si el admin cambio la clave, invalidar la sesion cacheada del usuario
    # (imap_pass/imap_master) para que el webmail re-autentique con la clave NUEVA. Sin esto,
    # la sesion activa seguiria usando la clave vieja cacheada (desync admin vs Dovecot).
    if data.get("password"):
        await revocar_todo(
            _get_db(request),
            request.app.state.redis,
            username,
            "clave_cambiada_por_admin",
        )
        await marcar_cambio_obligatorio(
            _get_db(request), request.app.state.redis, username, True
        )
    if data.get("active") is False:
        await revocar_todo(
            _get_db(request), request.app.state.redis, username, "cuenta_desactivada"
        )
    return result


@router.delete("/mailboxes/{username:path}")
async def delete_mailbox(
    username: str, request: Request, admin: str = Depends(require_admin)
):
    ok = await mailboxes_service.delete_mailbox(_get_db(request), username)
    if not ok:
        raise HTTPException(404, "Mailbox not found")

    await revocar_todo(
        _get_db(request), request.app.state.redis, username, "buzon_eliminado"
    )
    await _audit(request, admin, "mailbox_delete", username)
    return {"ok": True}


@router.post("/mailboxes/{username:path}/toggle-active")
async def toggle_mailbox_active(
    username: str, request: Request, admin: str = Depends(require_admin)
):
    result = await mailboxes_service.toggle_active(_get_db(request), username)
    if not result:
        raise HTTPException(404, "Mailbox not found")

    if not result.get("active"):
        await revocar_todo(
            _get_db(request), request.app.state.redis, username, "cuenta_desactivada"
        )
    await _audit(
        request, admin, "mailbox_toggle_active", username, {"active": result["active"]}
    )
    return result


@router.post("/mailboxes/{username:path}/unlock")
async def unlock_mailbox(
    username: str, request: Request, admin: str = Depends(require_admin)
):
    """Desbloquea una cuenta: limpia rate limits de login y bloqueos de seguridad."""
    redis = request.app.state.redis
    cleared = []
    # Rate limit de login por usuario
    if await redis.delete(f"login_rl:user:{username}"):
        cleared.append("login_rate_limit")
    # Bloqueo de cuenta (security module)
    if await redis.delete(f"account_blocked:{username}"):
        cleared.append("account_blocked")
    # Rate limit de envío
    if await redis.delete(f"send_history:{username}"):
        cleared.append("send_history")
    if await redis.delete(f"send_recipients:{username}"):
        cleared.append("send_recipients")
    await _audit(request, admin, "mailbox_unlock", username, {"cleared": cleared})
    return {"unlocked": True, "username": username, "cleared": cleared}


@router.get("/mailboxes/{username:path}/lock-status")
async def mailbox_lock_status(
    username: str, request: Request, admin: str = Depends(require_admin)
):
    """Verifica si una cuenta está bloqueada por rate limit o seguridad."""
    redis = request.app.state.redis
    login_rl = await redis.get(f"login_rl:user:{username}")
    login_rl_ttl = await redis.ttl(f"login_rl:user:{username}") if login_rl else -1
    account_blocked = await redis.exists(f"account_blocked:{username}")
    return {
        "username": username,
        "login_attempts": int(login_rl) if login_rl else 0,
        "login_blocked": int(login_rl or 0) > 10,
        "login_ttl_seconds": login_rl_ttl if login_rl_ttl > 0 else 0,
        "account_blocked": bool(account_blocked),
    }


# -- Aliases --


# ---- Proteccion de salida (anti cuenta comprometida) ----
@router.get("/outbound/limits")
async def outbound_limits(request: Request, admin: str = Depends(require_admin)):
    try:
        return await outbound_service.get_limits()
    except ValueError as e:
        raise HTTPException(500, str(e))


@router.put("/outbound/limits")
async def outbound_set_limits(request: Request, admin: str = Depends(require_admin)):
    data = await request.json()
    try:
        burst = int(data["burst"])
        rate = int(data["rate_per_min"])
    except (KeyError, TypeError, ValueError):
        raise HTTPException(400, "burst y rate_per_min deben ser enteros")
    try:
        await outbound_service.set_limits(burst, rate)
        if isinstance(data.get("whitelist"), list):
            await outbound_service.set_whitelist(
                [str(x).strip().lower() for x in data["whitelist"] if str(x).strip()]
            )
        if isinstance(data.get("dlp_exempt"), list):
            await outbound_service.set_dlp_exempt(
                [str(x).strip().lower() for x in data["dlp_exempt"] if str(x).strip()]
            )
    except ValueError as e:
        raise HTTPException(400, str(e))
    await _audit(
        request,
        admin,
        "outbound_set_limits",
        None,
        {
            "burst": burst,
            "rate_per_min": rate,
            "whitelist": data.get("whitelist"),
            "dlp_exempt": data.get("dlp_exempt"),
        },
    )
    return await outbound_service.get_limits()


@router.get("/outbound/activity")
async def outbound_activity(
    request: Request, hours: int = 1, admin: str = Depends(require_admin)
):
    try:
        return await outbound_service.activity(hours)
    except ValueError as e:
        raise HTTPException(500, str(e))


@router.post("/outbound/lock")
async def outbound_lock(request: Request, admin: str = Depends(require_admin)):
    email = ((await request.json()).get("email") or "").strip().lower()
    if "@" not in email:
        raise HTTPException(400, "email requerido")
    try:
        res = await outbound_service.lock(email)
    except ValueError as e:
        raise HTTPException(400, str(e))
    await _audit(request, admin, "outbound_lock", email)
    return res


@router.post("/outbound/unlock")
async def outbound_unlock(request: Request, admin: str = Depends(require_admin)):
    email = ((await request.json()).get("email") or "").strip().lower()
    if "@" not in email:
        raise HTTPException(400, "email requerido")
    try:
        res = await outbound_service.unlock(email)
    except ValueError as e:
        raise HTTPException(400, str(e))
    await _audit(request, admin, "outbound_unlock", email)
    return res


@router.get("/aliases")
async def list_aliases(
    request: Request, domain: str = None, admin: str = Depends(require_admin)
):
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
            _get_db(request),
            address=address,
            goto=goto,
            active=data.get("active", True),
        )
    except Exception as e:
        raise HTTPException(400, str(e))

    await _audit(request, admin, "alias_create", address, {"goto": goto})
    return result


@router.put("/aliases/{address:path}")
async def update_alias(
    address: str, request: Request, admin: str = Depends(require_admin)
):
    data = await request.json()
    result = await aliases_service.update_alias(
        _get_db(request),
        address=address,
        goto=data.get("goto"),
        active=data.get("active"),
    )
    if not result:
        raise HTTPException(404, "Alias not found")

    await _audit(request, admin, "alias_update", address, data)
    return result


@router.delete("/aliases/{address:path}")
async def delete_alias(
    address: str, request: Request, admin: str = Depends(require_admin)
):
    ok = await aliases_service.delete_alias(_get_db(request), address)
    if not ok:
        raise HTTPException(404, "Alias not found")

    await _audit(request, admin, "alias_delete", address)
    return {"ok": True}


# -- Distribution Groups --


@router.get("/groups")
async def list_groups(
    request: Request,
    domain: str = None,
    search: str = None,
    admin: str = Depends(require_admin),
):
    db = _get_db(request)
    clauses = []
    params = []
    idx = 1
    if domain:
        clauses.append(f"g.domain = ${idx}")
        params.append(domain)
        idx += 1
    if search:
        clauses.append(
            f"(g.address ILIKE ${idx} OR g.name ILIKE ${idx} OR g.description ILIKE ${idx})"
        )
        params.append(f"%{search}%")
        idx += 1
    where = "WHERE " + " AND ".join(clauses) if clauses else ""
    rows = await db.fetch(
        f"""
        SELECT g.*, (SELECT count(*) FROM mail_group_members gm WHERE gm.group_id = g.id) AS member_count
        FROM mail_groups g {where}
        ORDER BY g.name
    """,
        *params,
    )
    return [dict(r) for r in rows]


@router.post("/groups", status_code=201)
async def create_group(request: Request, admin: str = Depends(require_admin)):
    data = await request.json()
    address = data.get("address", "").strip().lower()
    name = data.get("name", "").strip()
    description = data.get("description", "").strip()
    domain = data.get("domain", "").strip()
    if not address:
        raise HTTPException(400, "Address required")
    if not domain and "@" in address:
        domain = address.split("@")[1]
    db = _get_db(request)
    try:
        row = await db.fetchrow(
            """
            INSERT INTO mail_groups (address, name, description, domain, active, allow_external, created_at, modified_at)
            VALUES ($1, $2, $3, $4, $5, $6, NOW(), NOW())
            RETURNING *
        """,
            address,
            name or address.split("@")[0],
            description,
            domain,
            data.get("active", True),
            data.get("allow_external", False),
        )
    except Exception as e:
        if "duplicate" in str(e).lower():
            raise HTTPException(400, f"Group {address} already exists")
        raise HTTPException(400, str(e))
    await _audit(request, admin, "group_create", address, {"name": name})
    result = dict(row)
    result["member_count"] = 0
    return result


@router.put("/groups/{group_id}")
async def update_group(
    group_id: int, request: Request, admin: str = Depends(require_admin)
):
    data = await request.json()
    db = _get_db(request)
    sets = []
    params = []
    idx = 1
    for field in ("name", "description", "active", "allow_external", "allowed_senders"):
        if field in data:
            sets.append(f"{field} = ${idx}")
            params.append(data[field])
            idx += 1
    if not sets:
        raise HTTPException(400, "Nothing to update")
    sets.append(f"modified_at = NOW()")
    params.append(group_id)
    row = await db.fetchrow(
        f"""
        UPDATE mail_groups SET {', '.join(sets)} WHERE id = ${idx} RETURNING *
    """,
        *params,
    )
    if not row:
        raise HTTPException(404, "Group not found")
    await _audit(request, admin, "group_update", row["address"], data)
    result = dict(row)
    result["member_count"] = await db.fetchval(
        "SELECT count(*) FROM mail_group_members WHERE group_id = $1", group_id
    )
    return result


@router.delete("/groups/{group_id}")
async def delete_group(
    group_id: int, request: Request, admin: str = Depends(require_admin)
):
    db = _get_db(request)
    row = await db.fetchrow(
        "DELETE FROM mail_groups WHERE id = $1 RETURNING address", group_id
    )
    if not row:
        raise HTTPException(404, "Group not found")
    await _audit(request, admin, "group_delete", row["address"])
    return {"ok": True}


@router.get("/groups/{group_id}/members")
async def list_group_members(
    group_id: int, request: Request, admin: str = Depends(require_admin)
):
    db = _get_db(request)
    rows = await db.fetch(
        """
        SELECT * FROM mail_group_members WHERE group_id = $1 ORDER BY member_email
    """,
        group_id,
    )
    return [dict(r) for r in rows]


@router.post("/groups/{group_id}/members", status_code=201)
async def add_group_member(
    group_id: int, request: Request, admin: str = Depends(require_admin)
):
    data = await request.json()
    member_email = data.get("member_email", "").strip().lower()
    if not member_email:
        raise HTTPException(400, "member_email required")
    db = _get_db(request)
    group = await db.fetchrow("SELECT address FROM mail_groups WHERE id = $1", group_id)
    if not group:
        raise HTTPException(404, "Group not found")
    try:
        row = await db.fetchrow(
            """
            INSERT INTO mail_group_members (group_id, member_email, member_name, can_send, receive, added_at)
            VALUES ($1, $2, $3, true, true, NOW())
            RETURNING *
        """,
            group_id,
            member_email,
            data.get("member_name", member_email.split("@")[0]),
        )
    except Exception as e:
        if "duplicate" in str(e).lower():
            raise HTTPException(400, f"{member_email} already in group")
        raise HTTPException(400, str(e))
    await _audit(
        request, admin, "group_member_add", group["address"], {"member": member_email}
    )
    return dict(row)


@router.delete("/groups/{group_id}/members/{member_id}")
async def remove_group_member(
    group_id: int, member_id: int, request: Request, admin: str = Depends(require_admin)
):
    db = _get_db(request)
    row = await db.fetchrow(
        """
        DELETE FROM mail_group_members WHERE id = $1 AND group_id = $2 RETURNING member_email
    """,
        member_id,
        group_id,
    )
    if not row:
        raise HTTPException(404, "Member not found")
    group = await db.fetchrow("SELECT address FROM mail_groups WHERE id = $1", group_id)
    await _audit(
        request,
        admin,
        "group_member_remove",
        group["address"] if group else str(group_id),
        {"member": row["member_email"]},
    )
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
    writer.writerow(
        ["id", "admin_user", "action", "target", "details", "ip_address", "created_at"]
    )
    for row in rows:
        writer.writerow(
            [
                row["id"],
                row["admin_user"],
                row["action"],
                row["target"],
                json.dumps(row["details"]) if row["details"] else "",
                str(row["ip_address"]) if row["ip_address"] else "",
                row["created_at"].isoformat() if row["created_at"] else "",
            ]
        )

    output.seek(0)
    await _audit(
        request,
        admin,
        "audit_export",
        None,
        {
            "filters": {
                "admin_user": admin_user,
                "action": action,
                "date_from": date_from,
                "date_to": date_to,
            }
        },
    )

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
    row = await db.fetchrow(
        """
        INSERT INTO corporate_disclaimer (domain, html_footer, text_footer, is_active)
        VALUES (, , , )
        ON CONFLICT (domain) DO UPDATE SET
            html_footer = EXCLUDED.html_footer,
            text_footer = EXCLUDED.text_footer,
            is_active = EXCLUDED.is_active,
            updated_at = NOW()
        RETURNING *
    """,
        domain,
        html_footer,
        text_footer,
        is_active,
    )
    await _audit(request, admin, "disclaimer_update", domain)
    return dict(row)


@router.delete("/disclaimer/{domain}")
async def delete_disclaimer(
    domain: str, request: Request, admin: str = Depends(require_admin)
):
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
    import re
    import subprocess
    from datetime import datetime, timedelta

    if not q or len(q) < 3:
        raise HTTPException(400, "Consulta muy corta (min 3 caracteres)")

    # Sanitize input
    q_safe = re.sub(r"[^a-zA-Z0-9@._\-<>]", "", q)

    # Search in Postfix logs
    try:
        result = subprocess.run(
            ["grep", "-i", q_safe, "/var/log/mail.log"],
            capture_output=True,
            text=True,
            timeout=30,
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
    admin_approve_forward,
    admin_unblock_account,
    get_account_status,
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
    Body: {"username": "user@ejemplo.com", "forward_address": "user@gmail.com"}
    """
    username = body.get("username", "")
    forward_address = body.get("forward_address", "")
    if not username or not forward_address:
        raise HTTPException(400, "username y forward_address requeridos")

    await admin_approve_forward(
        request.app.state.redis,
        request.app.state.db_pool,
        username,
        forward_address,
        admin,
    )
    return {
        "status": "ok",
        "message": f"Forward aprobado: {username} → {forward_address}",
    }


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
        username,
        forward_address,
    )
    redis = request.app.state.redis
    await redis.srem(f"approved_forwards:{username}", forward_address.lower())
    return {
        "status": "ok",
        "message": f"Forward revocado: {username} → {forward_address}",
    }


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
            username = (
                key.split(":", 1)[1]
                if isinstance(key, str)
                else key.decode().split(":", 1)[1]
            )
            reason = await redis.get(key)
            ttl = await redis.ttl(key)
            blocked.append(
                {
                    "username": username,
                    "reason": reason.decode() if isinstance(reason, bytes) else reason,
                    "ttl_seconds": max(0, ttl),
                }
            )
        if cursor == 0:
            break
    return {"blocked_accounts": blocked}


# =============================================
# CUARENTENA / FILTRO SPAM
# =============================================

from app.admin import quarantine_service


@router.get("/spam/junk")
async def list_junk_messages(
    request: Request,
    limit: int = 100,
    admin: str = Depends(require_admin),
):
    """Listar correos en carpeta Junk de todos los usuarios."""
    messages = await quarantine_service.get_all_junk_messages(limit=limit)
    return {"junk_messages": messages, "total": len(messages)}


@router.post("/spam/approve")
async def approve_spam_message(
    request: Request,
    admin: str = Depends(require_admin),
):
    """Mover correo de Junk a Inbox (falso positivo)."""
    body = await request.json()
    username = body.get("username")
    uid = body.get("uid")
    if not username or not uid:
        return {"error": "username y uid son requeridos"}
    ok = await quarantine_service.approve_message(username, uid)
    if ok:
        await _audit(request, admin, "spam_approve", username, {"uid": uid})
    return {"status": "ok" if ok else "error"}


@router.post("/spam/confirm")
async def confirm_spam_message(
    request: Request,
    admin: str = Depends(require_admin),
):
    """Confirmar que es spam (marcar como leido en Junk)."""
    body = await request.json()
    username = body.get("username")
    uid = body.get("uid")
    if not username or not uid:
        return {"error": "username y uid son requeridos"}
    ok = await quarantine_service.confirm_spam(username, uid)
    return {"status": "ok" if ok else "error"}


@router.post("/spam/delete")
async def delete_spam_message(
    request: Request,
    admin: str = Depends(require_admin),
):
    """Eliminar correo de Junk permanentemente."""
    body = await request.json()
    username = body.get("username")
    uid = body.get("uid")
    if not username or not uid:
        return {"error": "username y uid son requeridos"}
    ok = await quarantine_service.delete_spam(username, uid)
    if ok:
        await _audit(request, admin, "spam_delete", username, {"uid": uid})
    return {"status": "ok" if ok else "error"}


@router.get("/spam/log")
async def get_spam_log(
    request: Request,
    lines: int = 50,
    admin: str = Depends(require_admin),
):
    """Ver log del filtro anti-spam Python."""
    entries = await quarantine_service.get_spam_filter_log(lines=lines)
    return {"log": entries, "total": len(entries)}


@router.get("/spam/keywords")
async def get_spam_keywords(
    request: Request,
    admin: str = Depends(require_admin),
):
    """Obtener las keywords del filtro anti-spam."""
    content = await quarantine_service.get_keywords()
    return {"keywords": content}


@router.put("/spam/keywords")
async def update_spam_keywords(
    request: Request,
    admin: str = Depends(require_admin),
):
    """Actualizar las keywords del filtro anti-spam."""
    body = await request.json()
    content = body.get("keywords", "")
    ok = await quarantine_service.save_keywords(content)
    if ok:
        await _audit(
            request, admin, "spam_keywords_update", details={"length": len(content)}
        )
    return {"status": "ok" if ok else "error"}


@router.get("/spam/whitelist")
async def get_spam_whitelist(
    request: Request,
    admin: str = Depends(require_admin),
):
    """Obtener la whitelist de remitentes."""
    content = await quarantine_service.get_whitelist()
    return {"whitelist": content}


@router.put("/spam/whitelist")
async def update_spam_whitelist(
    request: Request,
    admin: str = Depends(require_admin),
):
    """Actualizar la whitelist de remitentes."""
    body = await request.json()
    content = body.get("whitelist", "")
    ok = await quarantine_service.save_whitelist(content)
    if ok:
        await _audit(
            request, admin, "spam_whitelist_update", details={"length": len(content)}
        )
    return {"status": "ok" if ok else "error"}


# =====================================================
# LISTAS NEGRAS PROPIAS
# =====================================================


@router.get("/spam/blacklist-domains")
async def get_blacklist_domains(
    request: Request,
    admin: str = Depends(require_admin),
):
    content = await quarantine_service.get_blacklist_domains()
    return {"content": content}


@router.put("/spam/blacklist-domains")
async def update_blacklist_domains(
    request: Request,
    admin: str = Depends(require_admin),
):
    body = await request.json()
    content = body.get("content", "")
    ok = await quarantine_service.save_blacklist_domains(content)
    if ok:
        await _audit(
            request, admin, "blacklist_domains_update", details={"length": len(content)}
        )
    return {"status": "ok" if ok else "error"}


@router.get("/spam/blacklist-ips")
async def get_blacklist_ips(
    request: Request,
    admin: str = Depends(require_admin),
):
    content = await quarantine_service.get_blacklist_ips()
    return {"content": content}


@router.put("/spam/blacklist-ips")
async def update_blacklist_ips(
    request: Request,
    admin: str = Depends(require_admin),
):
    body = await request.json()
    content = body.get("content", "")
    ok = await quarantine_service.save_blacklist_ips(content)
    if ok:
        await _audit(
            request, admin, "blacklist_ips_update", details={"length": len(content)}
        )
    return {"status": "ok" if ok else "error"}


@router.get("/spam/greylist-domains")
async def get_greylist_domains(
    request: Request,
    admin: str = Depends(require_admin),
):
    content = await quarantine_service.get_greylist_domains()
    return {"content": content}


@router.put("/spam/greylist-domains")
async def update_greylist_domains(
    request: Request,
    admin: str = Depends(require_admin),
):
    body = await request.json()
    content = body.get("content", "")
    ok = await quarantine_service.save_greylist_domains(content)
    if ok:
        await _audit(
            request, admin, "greylist_domains_update", details={"length": len(content)}
        )
    return {"status": "ok" if ok else "error"}
