from fastapi import APIRouter, Request, HTTPException, Depends

from app.auth.dependencies import require_admin
from app.admin import domains_service, mailboxes_service, aliases_service
from app.admin import queue_service, audit_service, stats_service

router = APIRouter(prefix="/api/admin", tags=["admin"])


def _get_db(request: Request):
    return request.app.state.db_pool


def _get_ip(request: Request) -> str:
    return request.headers.get("X-Real-IP", request.client.host if request.client else "unknown")


async def _audit(request: Request, admin: str, action: str, target: str = None, details: dict = None):
    await audit_service.log_action(
        _get_db(request), admin, action, target, details, _get_ip(request)
    )


# ── Dashboard ──────────────────────────────────────────────

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


# ── Domains ────────────────────────────────────────────────

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


# ── Mailboxes ──────────────────────────────────────────────

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


# ── Aliases ────────────────────────────────────────────────

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


# ── Queue ──────────────────────────────────────────────────

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


# ── Audit Log ──────────────────────────────────────────────

@router.get("/audit-log")
async def get_audit_log(
    request: Request,
    page: int = 1,
    per_page: int = 50,
    admin_user: str = None,
    action: str = None,
    target: str = None,
    admin: str = Depends(require_admin),
):
    return await audit_service.get_audit_log(
        _get_db(request), page, per_page, admin_user, action, target
    )
