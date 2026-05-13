"""Audit Middleware — intercepta acciones críticas de usuarios y las registra.

Se instala como middleware FastAPI. Captura POST/PUT/DELETE en rutas sensibles
y registra automáticamente en user_activity_log.
"""
import logging
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger("compliance.audit")

# Mapeo de rutas → acción de auditoría
# (method, path_prefix, action, category)
AUDIT_ROUTES = [
    # Auth
    ("POST", "/api/auth/login", "login_success", None),
    ("POST", "/api/auth/change-password", "password_change", None),
    ("POST", "/api/auth/totp/setup", "totp_setup", None),
    ("POST", "/api/auth/totp/disable", "totp_disable", None),
    # Email
    ("POST", "/api/mail/send", "email_send", None),
    ("POST", "/api/mail/send-multipart", "email_send", None),
    ("POST", "/api/mail/compose", "email_send", None),
    ("DELETE", "/api/mail/messages/", "email_delete", None),
    ("POST", "/api/mail/messages/bulk", "email_bulk_delete", None),
    ("POST", "/api/mail/export", "email_export", None),
    # Sieve
    ("POST", "/api/sieve/filters", "sieve_create", None),
    ("PUT", "/api/sieve/filters", "sieve_modify", None),
    ("DELETE", "/api/sieve/filters", "sieve_delete", None),
    ("POST", "/api/sieve/vacation", "autoresponder_change", None),
    # Identities (reenvíos)
    ("POST", "/api/identities", "forward_create", None),
    ("PUT", "/api/identities", "forward_modify", None),
    # API Keys
    ("POST", "/api/apikeys", "api_key_create", None),
    ("DELETE", "/api/apikeys", "api_key_delete", None),
    # Admin
    ("POST", "/api/admin/impersonate", "impersonate", None),
    # Compliance
    ("POST", "/api/compliance/ediscovery/search", "ediscovery_search", None),
    ("POST", "/api/compliance/ediscovery/export", "ediscovery_export", None),
]


def _match_route(method: str, path: str):
    """Busca si la ruta coincide con alguna acción auditable."""
    for r_method, r_path, r_action, _ in AUDIT_ROUTES:
        if method == r_method and path.startswith(r_path):
            return r_action
    return None


class UserActivityAuditMiddleware(BaseHTTPMiddleware):
    """Middleware que registra actividad de usuarios en acciones críticas."""

    async def dispatch(self, request, call_next):
        response = await call_next(request)

        # Solo registrar respuestas exitosas (2xx)
        if response.status_code < 200 or response.status_code >= 300:
            # Excepción: login fallido (401)
            if request.url.path == "/api/auth/login" and request.method == "POST":
                if response.status_code in (401, 403):
                    await self._log_activity(request, "login_failed", response.status_code)
            return response

        action = _match_route(request.method, request.url.path)
        if action:
            await self._log_activity(request, action, response.status_code)

        return response

    async def _log_activity(self, request, action, status_code):
        """Registra la actividad en la base de datos."""
        try:
            from app.compliance.activity_logger import log_user_activity

            # Extraer usuario del JWT
            username = None
            token = request.cookies.get("access_token")
            if token:
                try:
                    from app.auth.jwt import decode_access_token
                    payload = decode_access_token(token)
                    username = payload.get("sub", "")
                except Exception:
                    pass

            if not username and action == "login_failed":
                username = "unknown"

            if not username:
                return

            ip = request.headers.get("x-real-ip", request.client.host if request.client else None)
            ua = request.headers.get("user-agent", "")[:500]

            details = {"status_code": status_code, "path": request.url.path}

            db = request.app.state.db_pool

            await log_user_activity(
                db,
                username,
                action,
                ip_address=ip,
                user_agent=ua,
                target=request.url.path,
                details=details,
            )
        except Exception as exc:
            logger.error("Audit middleware error: %s", exc)
