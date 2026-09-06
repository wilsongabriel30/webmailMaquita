"""Maquita Webmail API — main entrypoint v0.5.0."""
import asyncio
import json
import logging
import os
from contextlib import asynccontextmanager

from aiosmtplib import SMTPAuthenticationError
from fastapi import Depends, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.admin.firewall_router import router as firewall_router
from app.admin.mailguard_router import router as mailguard_router
from app.admin.router import router as admin_router
from app.agents.router import router as agents_router
from app.ai.router import router as ai_router
from app.air.router import router as air_router
from app.apikeys.router import router as apikeys_router
from app.auth.dependencies import get_current_user
from app.auth.oidc import router as oidc_router
from app.auth.password import router as password_router
from app.auth.router import router as auth_router
from app.auth.totp import router as totp_router
from app.auth.totp_policy import router as totp_policy_router
from app.autodiscover_router import router as autodiscover_router
from app.branding.router import router as branding_router
from app.branding.service import precargar as precargar_marca
from app.calendar.router import router as calendar_router
from app.chatcfg.router import router as chatcfg_router
from app.compliance.audit_middleware import UserActivityAuditMiddleware
from app.compliance.fraud_detector import start_fraud_detector
from app.compliance.router import router as compliance_router
from app.config import get_settings
from app.contacts.routers import router as contacts_router
from app.copiloto.router import router as copiloto_router
from app.core.logging import RequestIdMiddleware, setup_logging
from app.database import create_db_pool
from app.dlp.router import router as dlp_router
from app.gal.router import router as gal_router
from app.hold_ack.router import router as hold_ack_router
from app.identities.router import router as identities_router
from app.import_export.router import router as import_router
from app.log_ingestor.mail_log_ingestor import start_log_ingestor
from app.mail.errors import CredencialIMAPInvalida
from app.mail.routers.attachments import router as attachments_router
from app.mail.routers.calendar_invite import router as calendar_invite_router
from app.mail.routers.compose import router as compose_router
from app.mail.routers.export import router as export_router
from app.mail.routers.folders import router as folders_router
from app.mail.routers.labels import router as labels_router
from app.mail.routers.messages import router as messages_router
from app.mail.routers.onlyoffice import router as onlyoffice_router
from app.mail.routers.priority import router as priority_router
from app.mail.routers.recall import router as recall_router
from app.mail.routers.remitente import router as remitente_router
from app.mail.routers.shared import router as shared_mail_router
from app.mail.routers.snooze import check_snoozed
from app.mail.routers.snooze import router as snooze_router
from app.mail.routers.spam_guard import router as spam_router
from app.mail.routers.stats import router as stats_router
from app.mail.routers.threads import router as threads_router
from app.mail.routers.transcribe import router as transcribe_router
from app.meetings.router import router as meetings_router
from app.mobile.router import router as mobile_router
from app.nextcloud.router import router as nextcloud_router
from app.onboarding.router import router as onboarding_router
from app.phishsim.router import router as phishsim_router
from app.presence.router import router as presence_router
from app.push.router import router as push_router
from app.push.service import asegurar_tabla as asegurar_tabla_push
from app.rag.router import router as rag_router
from app.redis_client import create_redis
from app.retention.router import router as retention_router
from app.rooms.router import router as rooms_router
from app.safelinks.router import router as safelinks_router
from app.secure_message.router import auth_router as secure_auth_router
from app.secure_message.router import public_router as secure_public_router
from app.security.router import router as security_router
from app.settings.routers.preferences import router as settings_router
from app.sieve.router import router as sieve_router
from app.smime.router import router as smime_router
from app.sso.router import router as sso_router
from app.tareas.modelos import asegurar_tablas as asegurar_tablas_tareas
from app.tareas.router import router as tareas_router
from app.tasks.router import router as tasks_router
from app.telemetria.router import asegurar_tabla as asegurar_tabla_telemetria
from app.telemetria.router import router as telemetria_router
from app.webhooks.router import router as webhooks_router
from app.websocket.router import router as ws_router
from app.websocket.router import start_redis_subscriber


# Handler global de excepciones — evita que nginx devuelva HTML en errores 500
async def _global_exception_handler(request: Request, exc: Exception):
    import traceback
    logging.getLogger("uvicorn.error").error(
        "Unhandled exception: %s\n%s", str(exc), traceback.format_exc()
    )
    return JSONResponse(
        status_code=500,
        content={"detail": "Error interno del servidor"},
    )
from app.tasks.models import ensure_tables as ensure_task_tables

# Registrar handler global (se ejecuta después de crear app)
_REGISTER_EXCEPTION_HANDLER = True  # Flag para registrar en lifespan
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
                    # Reclamo atómico: solo UN worker envía cada correo programado
                    claimed = await db_pool.fetchrow(
                        "UPDATE scheduled_emails SET status = 'sending' "
                        "WHERE id = $1 AND status = 'pending' RETURNING id",
                        row["id"],
                    )
                    if not claimed:
                        continue
                    username = row["username"]
                    raw_pass = await redis.get(f"imap_pass:{username}")
                    if not raw_pass:
                        logger.warning(f"Scheduled email {row['id']}: no session for {username}")
                        await db_pool.execute(
                            "UPDATE scheduled_emails SET status = 'pending' WHERE id = $1",
                            row["id"],
                        )
                        continue

                    # Descifrar contraseña Fernet (las passwords en Redis están cifradas)
                    from app.core.session import decrypt_password
                    try:
                        password = decrypt_password(raw_pass)
                    except Exception:
                        password = raw_pass  # fallback legacy sin cifrar

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




def _validate_mime_on_startup():
    """Verifica que smtp_client.py construye MIME correcto al arrancar.
    
    Si falla, el backend NO arranca — protege contra cambios accidentales
    que enviarían correos a spam. Ver: 09-AUDITORIA-ENTREGABILIDAD-20260414.md
    """
    from app.mail.clients.smtp_client import OutgoingEmail, build_mime_message
    msg = build_mime_message(OutgoingEmail(
        from_addr="test@ejemplo.com", to=["x@x.com"], subject="startup-check",
        html_body="<p>test</p>"
    ))
    parts = [p.get_content_type() for p in msg.walk()
             if not p.get_content_type().startswith("multipart")]
    raw = msg.as_string()
    
    errors = []
    if "text/plain" not in parts:
        errors.append("FALTA text/plain — causa MIME_HTML_ONLY en spam")
    if "text/html" not in parts:
        errors.append("FALTA text/html")
    
    for p in msg.walk():
        if p.get_content_type() == "text/plain":
            txt = p.get_payload(decode=True).decode()
            if not txt.strip():
                errors.append("text/plain VACÍO — causa MPART_ALT_DIFF en spam")
        if p.get_content_type() == "text/html":
            html = p.get_payload(decode=True).decode()
            if "<!DOCTYPE" not in html:
                errors.append("HTML sin DOCTYPE — causa HTML_MIME_NO_HTML_TAG en spam")
    
    for bad_h in ("X-Priority", "X-MSMail-Priority", "Importance"):
        if bad_h in raw:
            errors.append(f"Header {bad_h} presente — spam trigger")
    
    if errors:
        raise RuntimeError(
            "MIME VALIDATION FAILED — backend NO arranca para proteger entregabilidad:\n"
            + "\n".join(f"  - {e}" for e in errors)
            + "\nEjecutar: python3 backend/tests/test_mime_deliverability.py"
        )
    logging.getLogger("uvicorn").warning("MIME validation OK — correos seguros")


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    setup_logging()
    app.state.db_pool = await create_db_pool()
    app.state.redis = await create_redis()
    # Marca: se rellena la cache de proceso una sola vez, para los puntos que no
    # tienen la base a mano (cliente SMTP, recordatorios, calendario). Si falla,
    # se sigue con los valores por defecto: la marca nunca impide arrancar.
    await precargar_marca(app.state.db_pool)
    # DDL serializado entre workers (evita deadlocks de arranque)
    async with app.state.db_pool.acquire() as _ddl_conn:
        await _ddl_conn.execute("SELECT pg_advisory_lock(815000)")
        try:
            await ensure_task_tables(app.state.db_pool)
            await asegurar_tablas_tareas(app.state.db_pool)   # T-34
            await asegurar_tabla_telemetria(app.state.db_pool)   # telemetría de la app
            await asegurar_tabla_push(app.state.db_pool)   # suscripciones web push (#17)
        finally:
            await _ddl_conn.execute("SELECT pg_advisory_unlock(815000)")
    # ── Validación MIME al arranque (protección anti-spam) ──
    _validate_mime_on_startup()
    # Start scheduled email background task
    scheduler_task = asyncio.create_task(
        _process_scheduled_emails(app.state.db_pool, app.state.redis)
    )
    # Start WebSocket Redis subscriber for real-time notifications
    ws_subscriber_task = await start_redis_subscriber(app.state)
    snooze_task = asyncio.create_task(check_snoozed(app))
    from app.reminders_scheduler import check_reminders
    reminders_task = asyncio.create_task(check_reminders(app))
    # Start compliance services
    app.state.log_ingestor = await start_log_ingestor(app.state.db_pool)
    from app.safelinks import threatfeeds as _tfeeds
    app.state.tintel_task = asyncio.create_task(_tfeeds.loop(app))
    app.state.fraud_detector = await start_fraud_detector(app.state.db_pool)
    # Start IMAP pool cleanup
    from app.mail.clients.imap_pool import start_cleanup_task
    start_cleanup_task()

    yield

    # Shutdown IMAP pool
    from app.mail.clients.imap_pool import close_all_pools
    await close_all_pools()
    # Stop compliance services
    app.state.log_ingestor.stop()
    app.state.fraud_detector.stop()
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




class ApiRateLimitMiddleware(BaseHTTPMiddleware):
    """Per-user rate limiting for authenticated API requests using Redis.

    Limits (configurables via .env; 0 = tier deshabilitado):
      - Read endpoints (GET):     RATE_LIMIT_READ_PER_MIN  (default 300)
      - Write endpoints (POST/PUT/DELETE/PATCH): RATE_LIMIT_WRITE_PER_MIN (default 60)
      - Send/compose:             RATE_LIMIT_SEND_PER_MIN  (default 10)

    Skips: login, health, static assets, WebSocket upgrades.
    """

    SKIP_PATHS = frozenset({"/api/auth/login", "/api/auth/refresh", "/api/health", "/api/health/detailed"})
    SEND_PATHS = frozenset({"/api/mail/send", "/api/mail/send-multipart", "/api/mail/compose", "/api/auth/change-password", "/api/auth/totp/setup", "/api/auth/totp/verify", "/api/auth/totp/disable"})

    async def dispatch(self, request, call_next):
        path = request.url.path

        # Skip non-API, auth, health, websocket
        if not path.startswith("/api/") or path in self.SKIP_PATHS:
            return await call_next(request)
        if "upgrade" in request.headers.get("connection", "").lower():
            return await call_next(request)

        # Extract username from JWT cookie (lightweight — no DB call)
        token = request.cookies.get("access_token")
        if not token:
            return await call_next(request)

        try:
            from app.auth.jwt import decode_access_token
            payload = decode_access_token(token)
            user = payload.get("sub", "")
        except Exception:
            return await call_next(request)

        if not user:
            return await call_next(request)

        # Determine limit tier
        method = request.method.upper()
        rl = get_settings()
        if path in self.SEND_PATHS:
            limit, window, tier = rl.rate_limit_send_per_min, 60, "send"
        elif method == "GET":
            limit, window, tier = rl.rate_limit_read_per_min, 60, "read"
        else:
            limit, window, tier = rl.rate_limit_write_per_min, 60, "write"

        if limit <= 0:
            return await call_next(request)

        # Check Redis counter
        try:
            redis = request.app.state.redis
            key = f"rl:{tier}:{user}"
            count = await redis.incr(key)
            if count == 1:
                await redis.expire(key, window)

            if count > limit:
                from starlette.responses import JSONResponse
                ttl = await redis.ttl(key)
                if ttl < 0:
                    await redis.expire(key, window)
                    ttl = window
                return JSONResponse(
                    status_code=429,
                    content={"detail": f"Demasiadas solicitudes. Limite: {limit}/{window}s. Reintente en {ttl}s."},
                    headers={"Retry-After": str(ttl), "X-RateLimit-Limit": str(limit), "X-RateLimit-Remaining": "0"},
                )
        except Exception:
            pass  # Redis failure should not block requests

        response = await call_next(request)

        # Add rate limit headers on success
        try:
            remaining = max(0, limit - count)
            response.headers["X-RateLimit-Limit"] = str(limit)
            response.headers["X-RateLimit-Remaining"] = str(remaining)
        except Exception:
            pass

        return response


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


_es_dev = get_settings().environment.lower() in ("development", "dev", "local")
_docs = {} if _es_dev else {"docs_url": None, "redoc_url": None, "openapi_url": None}
app = FastAPI(title="Maquita Webmail API", version="0.5.0", lifespan=lifespan, **_docs)

settings = get_settings()
app.add_middleware(SecurityAuditMiddleware)
app.add_middleware(UserActivityAuditMiddleware)
app.add_middleware(ApiRateLimitMiddleware)

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
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "X-Requested-With", "Accept", "Origin"],
)



@app.exception_handler(SMTPAuthenticationError)
async def credencial_smtp_handler(request, exc):
    """Mismo caso que IMAP, pero al enviar: la credencial guardada ya no vale."""
    security_logger.info("Credencial de sesión rechazada por SMTP en %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=401,
        content={"detail": "Tu sesión de correo caducó. Vuelve a iniciar sesión.", "reautenticar": True},
    )


@app.exception_handler(CredencialIMAPInvalida)
async def credencial_caducada_handler(request, exc):
    """La credencial guardada ya no vale: 401 para que la interfaz mande a iniciar
    sesión, en vez de un 500 que parece caída del servidor."""
    security_logger.info("Credencial de sesión rechazada por IMAP en %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=401,
        content={"detail": "Tu sesión de correo caducó. Vuelve a iniciar sesión.", "reautenticar": True},
    )


@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """Return JSON for unhandled exceptions instead of plain text."""
    import traceback
    security_logger.error(f"Unhandled exception en {request.method} {request.url.path}: {exc}\n{traceback.format_exc()}")
    # T-39 (28/08/2026): el login y el resto de /api/auth JAMÁS responden 500: excepción interna capturada y anotada,
    # respuesta 503 con mensaje claro y marca «reintentar» para que el cliente lo trate como transitorio.
    if request.url.path.startswith("/api/auth/"):
        return JSONResponse(
            status_code=503,
            content={"detail": "El servidor de correo tuvo un problema momentáneo; vuelve a intentarlo en unos segundos.", "reintentar": True},
            headers={"Retry-After": "5"},
        )
    return JSONResponse(
        status_code=500,
        content={"detail": "Error interno del servidor", "reintentar": True}
    )



@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request, exc):
    """Return 400 with generic message instead of 422 with detailed validation errors."""
    return JSONResponse(
        status_code=400,
        content={"detail": "Solicitud inválida. Verifique el formato de los datos enviados."}
    )

app.include_router(auth_router)
app.include_router(push_router)
app.include_router(oidc_router)
app.include_router(air_router)
app.include_router(agents_router)
app.include_router(rag_router)
app.include_router(copiloto_router)
app.include_router(password_router)
app.include_router(admin_router)
app.include_router(onboarding_router)
app.include_router(folders_router)
app.include_router(messages_router)
app.include_router(compose_router)
app.include_router(dlp_router)
app.include_router(secure_auth_router)
app.include_router(secure_public_router)
app.include_router(safelinks_router)
app.include_router(phishsim_router)
app.include_router(hold_ack_router)
app.include_router(attachments_router)
app.include_router(threads_router)
app.include_router(onlyoffice_router)
app.include_router(recall_router)
app.include_router(stats_router)
app.include_router(labels_router)
app.include_router(snooze_router)
app.include_router(priority_router)
app.include_router(transcribe_router)
app.include_router(spam_router)
app.include_router(settings_router)
app.include_router(autodiscover_router)
app.include_router(contacts_router)
app.include_router(sieve_router)
app.include_router(identities_router)
app.include_router(ws_router)
app.include_router(export_router)
app.include_router(remitente_router)  # banner remitente externo
app.include_router(totp_router)
app.include_router(totp_policy_router)
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
app.include_router(tareas_router, prefix="/api/tareas", tags=["tareas"])  # T-34
app.include_router(telemetria_router, prefix="/api/telemetria", tags=["telemetria"])  # cliente Windows
app.include_router(presence_router)
app.include_router(nextcloud_router)
app.include_router(branding_router)
app.include_router(chatcfg_router)
app.include_router(calendar_invite_router)
app.include_router(compliance_router)
app.include_router(firewall_router)
app.include_router(mailguard_router)


@app.post("/api/csp-report")
async def csp_report(request: Request):
    content_type = request.headers.get("content-type", "")
    if "csp-report" not in content_type and "json" not in content_type:
        from fastapi.responses import Response
        return Response(status_code=400)
    body = await request.body()
    import logging
    logging.getLogger("security.csp").warning(f"CSP violation: {body.decode('utf-8', errors='replace')[:2000]}")
    return {"status": "ok"}


@app.get("/api/health")
async def health_check(request: Request):
    """Health check for monitoring and load balancers.
    Returns minimal info publicly, detailed info only from internal IPs."""
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
    status_code = 200 if all_ok else 503

    # Public endpoint: only return status without component names
    return JSONResponse(content={"status": "ok"}, status_code=status_code)
import socket


@app.get("/api/health/detailed")
async def health_detailed(request: Request, admin: str = Depends(get_current_user)):
    """Extended health check: PostgreSQL, Redis, Dovecot IMAP, Postfix SMTP. Requires auth."""
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
