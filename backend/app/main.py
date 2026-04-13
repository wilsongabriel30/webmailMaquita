"""Maquita Webmail API — main entrypoint v0.5.0."""
import asyncio
import json
import os
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
import logging

from app.config import get_settings
from app.database import create_db_pool
from app.redis_client import create_redis
from app.core.logging import setup_logging, RequestIdMiddleware

from app.auth.router import router as auth_router
from app.auth.password import router as password_router
from app.admin.router import router as admin_router
from app.mail.routers.folders import router as folders_router
from app.mail.routers.messages import router as messages_router
from app.mail.routers.compose import router as compose_router
from app.mail.routers.attachments import router as attachments_router
from app.mail.routers.threads import router as threads_router
from app.mail.routers.recall import router as recall_router
from app.mail.routers.stats import router as stats_router
from app.mail.routers.labels import router as labels_router
from app.mail.routers.snooze import router as snooze_router, check_snoozed
from app.mail.routers.priority import router as priority_router
from app.mail.routers.spam_guard import router as spam_router
from app.mail.routers.onlyoffice import router as onlyoffice_router
from app.settings.routers.preferences import router as settings_router
from app.contacts.routers import router as contacts_router
from app.sieve.router import router as sieve_router
from app.identities.router import router as identities_router
from app.websocket.router import router as ws_router, start_redis_subscriber
from app.mail.routers.export import router as export_router
from app.auth.totp import router as totp_router
from app.calendar.router import router as calendar_router
from app.mail.routers.shared import router as shared_mail_router
from app.webhooks.router import router as webhooks_router
from app.apikeys.router import router as apikeys_router
from app.import_export.router import router as import_router
from app.smime.router import router as smime_router
from app.sso.router import router as sso_router
from app.meetings.router import router as meetings_router
from app.security.router import router as security_router
from app.mobile.router import router as mobile_router
from app.ai.router import router as ai_router
from app.retention.router import router as retention_router
from app.gal.router import router as gal_router
from app.rooms.router import router as rooms_router
from app.tasks.router import router as tasks_router
from app.presence.router import router as presence_router
from app.nextcloud.router import router as nextcloud_router
from app.tasks.models import ensure_tables as ensure_task_tables
from app.calendar.attachments import router as cal_attachments_router


logger = logging.getLogger("scheduler")


async def _process_scheduled_emails(db_pool, redis):
    """Background task: check and send scheduled emails every 30s."""
    while True:
        try:
            await asyncio.sleep(30)
            # Check if table exists
            try:
                rows = await db_pool.fetch("""
                    SELECT id, username, to_list, cc_list, bcc_list, subject,
                           html_body, text_body, in_reply_to, "references",
                           request_read_receipt, request_delivery_receipt
                    FROM scheduled_emails
                    WHERE status = 'pending' AND scheduled_at <= NOW()
                    ORDER BY scheduled_at ASC
                    LIMIT 10
                """)
            except Exception:
                # Table might not exist yet
                continue

            for row in rows:
                try:
                    username = row["username"]
                    password = await redis.get(f"imap_pass:{username}")
                    if not password:
                        logger.warning(f"Scheduled email {row['id']}: no session for {username}")
                        continue

                    from app.mail.clients.imap_client import get_imap_connection
                    from app.mail.services.send_service import send_and_save

                    imap = await get_imap_connection(username, password)
                    try:
                        # Get display name
                        display_name = ""
                        pref = await db_pool.fetchrow(
                            "SELECT display_name FROM user_preferences WHERE username = $1",
                            username,
                        )
                        if pref and pref["display_name"]:
                            display_name = pref["display_name"]

                        to_list = json.loads(row["to_list"]) if isinstance(row["to_list"], str) else row["to_list"]
                        cc_list = json.loads(row["cc_list"]) if isinstance(row["cc_list"], str) else row["cc_list"]
                        bcc_list = json.loads(row["bcc_list"]) if isinstance(row["bcc_list"], str) else row["bcc_list"]

                        await send_and_save(
                            imap=imap,
                            password=password,
                            from_addr=username,
                            to=to_list,
                            subject=row["subject"],
                            text_body=row["text_body"],
                            html_body=row["html_body"],
                            cc=cc_list,
                            bcc=bcc_list,
                            in_reply_to=row["in_reply_to"],
                            references=row["references"],
                            display_name=display_name,
                            request_read_receipt=row["request_read_receipt"],
                            request_delivery_receipt=row["request_delivery_receipt"],
                        )

                        await db_pool.execute(
                            "UPDATE scheduled_emails SET status = 'sent' WHERE id = $1",
                            row["id"],
                        )
                        logger.info(f"Scheduled email {row['id']} sent successfully")
                    finally:
                        try:
                            await imap.logout()
                        except Exception:
                            pass

                except Exception as exc:
                    logger.error(f"Scheduled email {row['id']} failed: {exc}")
                    await db_pool.execute(
                        "UPDATE scheduled_emails SET status = 'failed' WHERE id = $1",
                        row["id"],
                    )

        except asyncio.CancelledError:
            break
        except Exception as exc:
            logger.error(f"Scheduler loop error: {exc}")
            await asyncio.sleep(30)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    setup_logging()
    app.state.db_pool = await create_db_pool()
    app.state.redis = await create_redis()
    await ensure_task_tables(app.state.db_pool)
    # Start scheduled email background task
    scheduler_task = asyncio.create_task(
        _process_scheduled_emails(app.state.db_pool, app.state.redis)
    )
    # Start WebSocket Redis subscriber for real-time notifications
    ws_subscriber_task = await start_redis_subscriber(app.state)
    snooze_task = asyncio.create_task(check_snoozed(app))
    yield
    scheduler_task.cancel()
    ws_subscriber_task.cancel()
    snooze_task.cancel()
    try:
        await scheduler_task
    except asyncio.CancelledError:
        pass
    await app.state.db_pool.close()
    await app.state.redis.close()



# Security audit logging
security_logger = logging.getLogger("security")
_security_log_path = get_settings().security_log_path
try:
    os.makedirs(os.path.dirname(_security_log_path), exist_ok=True)
    _sec_handler = logging.FileHandler(_security_log_path)
except (OSError, PermissionError):
    _sec_handler = logging.StreamHandler()  # fallback to stdout
_sec_handler.setFormatter(logging.Formatter("%(asctime)s %(message)s"))
security_logger.addHandler(_sec_handler)
security_logger.setLevel(logging.WARNING)

_SECURITY_EVENTS = {
    ("/api/auth/login", 429): "rate_limit_hit",
    ("/api/auth/totp/setup", 200): "totp_setup",
    ("/api/auth/totp/disable", 200): "totp_disabled",
    ("/api/identities", 201): "identity_created",
    ("/api/mail/compose", 200): "email_sent",
    ("/api/sieve/filters", 201): "sieve_filter_created",
    ("/api/sieve/vacation", 200): "vacation_changed",
}


class SecurityAuditMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        response = await call_next(request)
        key = (request.url.path, response.status_code)
        event = _SECURITY_EVENTS.get(key)
        if event:
            ip = request.headers.get("x-real-ip", request.client.host if request.client else "?")
            security_logger.warning(
                f"SECURITY_EVENT={event} ip={ip} path={request.url.path}"
            )
        # Log all 401/403/429 responses
        if response.status_code in (401, 403, 429):
            ip = request.headers.get("x-real-ip", request.client.host if request.client else "?")
            security_logger.warning(
                f"SECURITY_BLOCK status={response.status_code} ip={ip} "
                f"method={request.method} path={request.url.path}"
            )
        return response


app = FastAPI(title="Maquita Webmail API", version="0.5.0", lifespan=lifespan)

settings = get_settings()
app.add_middleware(SecurityAuditMiddleware)

# Strip allow-credentials header for non-matching origins (CORS hardening)
class StripCredentialsMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        response = await call_next(request)
        origin = request.headers.get("origin", "")
        if origin and settings.cookie_domain not in origin:
            if "access-control-allow-credentials" in response.headers:
                del response.headers["access-control-allow-credentials"]
        return response


app.add_middleware(StripCredentialsMiddleware)

app.add_middleware(RequestIdMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins.split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)



@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """Return JSON for unhandled exceptions instead of plain text."""
    import traceback
    security_logger.error(f"Unhandled exception: {exc}\n{traceback.format_exc()}")
    return JSONResponse(
        status_code=500,
        content={"detail": "Error interno del servidor"}
    )

app.include_router(auth_router)
app.include_router(password_router)
app.include_router(admin_router)
app.include_router(folders_router)
app.include_router(messages_router)
app.include_router(compose_router)
app.include_router(attachments_router)
app.include_router(threads_router)
app.include_router(onlyoffice_router)
app.include_router(recall_router)
app.include_router(stats_router)
app.include_router(labels_router)
app.include_router(snooze_router)
app.include_router(priority_router)
app.include_router(spam_router)
app.include_router(settings_router)
app.include_router(contacts_router)
app.include_router(sieve_router)
app.include_router(identities_router)
app.include_router(ws_router)
app.include_router(export_router)
app.include_router(totp_router)
app.include_router(calendar_router)
app.include_router(shared_mail_router)
app.include_router(webhooks_router)
app.include_router(apikeys_router)
app.include_router(import_router)
app.include_router(security_router)
app.include_router(mobile_router)
app.include_router(ai_router)
app.include_router(retention_router)
app.include_router(gal_router)
app.include_router(rooms_router)
app.include_router(cal_attachments_router)
app.include_router(smime_router)
app.include_router(sso_router)
app.include_router(meetings_router)
app.include_router(tasks_router, prefix="/api/tasks", tags=["tasks"])
app.include_router(presence_router)
app.include_router(nextcloud_router)


@app.post("/api/csp-report")
async def csp_report(request: Request):
    body = await request.body()
    import logging
    logging.getLogger("security.csp").warning(f"CSP violation: {body.decode('utf-8', errors='replace')[:2000]}")
    return {"status": "ok"}


@app.get("/api/health")
async def health_check(request: Request):
    """Health check for monitoring and load balancers"""
    checks = {"api": "ok"}

    # Check Redis
    try:
        pong = await request.app.state.redis.ping()
        checks["redis"] = "ok" if pong else "error: no pong"
    except Exception as e:
        checks["redis"] = f"error: {str(e)}"

    # Check PostgreSQL
    try:
        await request.app.state.db_pool.fetchval("SELECT 1")
        checks["database"] = "ok"
    except Exception as e:
        checks["database"] = f"error: {str(e)}"

    all_ok = all(v == "ok" for v in checks.values())

    return JSONResponse(
        content={"status": "healthy" if all_ok else "degraded", "checks": checks},
        status_code=200 if all_ok else 503
    )
import socket


@app.get("/api/health/detailed")
async def health_detailed(request: Request):
    """Extended health check: PostgreSQL, Redis, Dovecot IMAP, Postfix SMTP."""
    results = {}

    # PostgreSQL
    try:
        row = await request.app.state.db_pool.fetchval("SELECT 1")
        results["postgresql"] = {"status": "ok"}
    except Exception as e:
        results["postgresql"] = {"status": "error", "detail": str(e)}

    # Redis
    try:
        pong = await request.app.state.redis.ping()
        results["redis"] = {"status": "ok" if pong else "error"}
    except Exception as e:
        results["redis"] = {"status": "error", "detail": str(e)}

    # Dovecot IMAP (port 143)
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(3)
        s.connect(("127.0.0.1", 143))
        banner = s.recv(256).decode("utf-8", errors="replace")
        s.close()
        results["dovecot_imap"] = {"status": "ok", "banner": banner.strip()[:80]}
    except Exception as e:
        results["dovecot_imap"] = {"status": "error", "detail": str(e)}

    # Postfix SMTP (port 25)
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(3)
        s.connect(("127.0.0.1", 25))
        banner = s.recv(256).decode("utf-8", errors="replace")
        s.close()
        results["postfix_smtp"] = {"status": "ok", "banner": banner.strip()[:80]}
    except Exception as e:
        results["postfix_smtp"] = {"status": "error", "detail": str(e)}

    all_ok = all(v["status"] == "ok" for v in results.values())
    return {"status": "ok" if all_ok else "degraded", "services": results}
