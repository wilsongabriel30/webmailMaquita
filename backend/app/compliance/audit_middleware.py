"""User Activity Audit Middleware — intercepts and logs sensitive actions.

Captures: login, logout, mail send/delete/move/copy, sieve rules,
forwards, impersonation, eDiscovery, legal hold, exports.
"""

import logging
import time
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

logger = logging.getLogger("compliance.audit")

# Route → (action, category, risk_level)
# POST/PUT/DELETE routes that should be audited
_AUDIT_ROUTES = {
    # Auth events
    ("POST", "/api/auth/login"): ("login_attempt", "auth", "medium"),
    ("POST", "/api/auth/logout"): ("logout", "auth", "low"),
    ("POST", "/api/auth/refresh"): ("token_refresh", "auth", "low"),
    ("POST", "/api/auth/change-password"): ("password_change", "security", "high"),
    ("POST", "/api/auth/totp/setup"): ("totp_setup", "security", "high"),
    ("POST", "/api/auth/totp/verify"): ("totp_verify", "security", "medium"),
    ("POST", "/api/auth/totp/disable"): ("totp_disable", "security", "critical"),
    ("POST", "/api/auth/impersonate"): ("impersonation_start", "security", "critical"),
    # Mail events
    ("POST", "/api/mail/send"): ("email_send", "email", "medium"),
    ("POST", "/api/mail/send-multipart"): ("email_send", "email", "medium"),
    ("POST", "/api/mail/compose"): ("email_send", "email", "medium"),
    ("DELETE", "/api/mail/messages"): ("email_delete", "email", "medium"),
    ("POST", "/api/mail/messages/move"): ("email_move", "email", "low"),
    ("POST", "/api/mail/messages/copy"): ("email_copy", "email", "low"),
    ("POST", "/api/mail/messages/flag"): ("email_flag", "email", "low"),
    ("DELETE", "/api/mail/folders"): ("folder_delete", "email", "high"),
    # Sieve rules
    ("POST", "/api/sieve/filters"): ("sieve_rule_created", "sieve", "medium"),
    ("PUT", "/api/sieve/filters"): ("sieve_rule_updated", "sieve", "medium"),
    ("DELETE", "/api/sieve/filters"): ("sieve_rule_deleted", "sieve", "medium"),
    ("POST", "/api/sieve/vacation"): ("vacation_changed", "sieve", "low"),
    # Forwarding
    ("POST", "/api/admin/forwarding"): ("forward_created", "admin", "high"),
    ("PUT", "/api/admin/forwarding"): ("forward_updated", "admin", "high"),
    ("DELETE", "/api/admin/forwarding"): ("forward_deleted", "admin", "medium"),
    # Identity/signatures
    ("POST", "/api/identities"): ("identity_created", "security", "medium"),
    ("PUT", "/api/identities"): ("identity_updated", "security", "medium"),
    ("DELETE", "/api/identities"): ("identity_deleted", "security", "medium"),
    # Admin actions
    ("POST", "/api/admin/mailboxes"): ("mailbox_created", "admin", "high"),
    ("DELETE", "/api/admin/mailboxes"): ("mailbox_deleted", "admin", "critical"),
    ("PUT", "/api/admin/mailboxes"): ("mailbox_updated", "admin", "medium"),
    ("POST", "/api/admin/domains"): ("domain_created", "admin", "high"),
    ("DELETE", "/api/admin/domains"): ("domain_deleted", "admin", "critical"),
    # Compliance actions (self-audit)
    ("POST", "/api/compliance/cases"): ("case_created", "compliance", "high"),
    ("PUT", "/api/compliance/cases"): ("case_updated", "compliance", "medium"),
    ("POST", "/api/compliance/ediscovery/search"): (
        "ediscovery_search",
        "compliance",
        "high",
    ),
    ("POST", "/api/compliance/ediscovery/export"): (
        "ediscovery_export",
        "compliance",
        "critical",
    ),
    ("POST", "/api/compliance/holds"): ("legal_hold_enabled", "compliance", "critical"),
    ("DELETE", "/api/compliance/holds"): (
        "legal_hold_released",
        "compliance",
        "critical",
    ),
    ("PUT", "/api/compliance/alerts"): ("alert_acknowledged", "compliance", "medium"),
    # Import/Export
    ("POST", "/api/import"): ("bulk_import", "admin", "high"),
    ("POST", "/api/mail/export"): ("mail_export", "email", "high"),
}

# Login result mapping based on response status
_LOGIN_RESULTS = {
    200: "login_success",
    401: "login_failed",
    403: "login_blocked",
    429: "login_rate_limited",
}


class UserActivityAuditMiddleware(BaseHTTPMiddleware):
    """Intercepts HTTP requests and logs sensitive actions to user_activity_log."""

    async def dispatch(self, request: Request, call_next):
        method = request.method.upper()
        path = request.url.path.rstrip("/")

        # Quick skip for non-auditable requests
        if method == "GET" or method == "OPTIONS":
            return await call_next(request)

        if not path.startswith("/api/"):
            return await call_next(request)

        start = time.time()
        response = await call_next(request)
        elapsed = time.time() - start

        # Check if this route should be audited
        route_key = (method, path)
        audit_info = _AUDIT_ROUTES.get(route_key)

        # Also check prefix matches for parameterized routes
        if not audit_info:
            for (m, p), info in _AUDIT_ROUTES.items():
                if m == method and path.startswith(p):
                    audit_info = info
                    break

        if not audit_info:
            return response

        action, category, risk_level = audit_info

        # Special handling for login — action depends on response code
        if path == "/api/auth/login" and method == "POST":
            action = _LOGIN_RESULTS.get(response.status_code, "login_attempt")
            if response.status_code != 200:
                risk_level = "high"

        # Extract username
        username = ""
        try:
            # From cookie JWT
            token = request.cookies.get("access_token")
            if token:
                from app.auth.jwt import decode_access_token

                payload = decode_access_token(token)
                username = payload.get("sub", "")
            # From Bearer token
            if not username:
                auth_header = request.headers.get("authorization", "")
                if auth_header.startswith("Bearer "):
                    import jwt as pyjwt
                    import os

                    secret = os.getenv("ADMIN_JWT_SECRET", "")
                    if secret:
                        payload = pyjwt.decode(
                            auth_header[7:], secret, algorithms=["HS256"]
                        )
                        username = payload.get("sub", payload.get("username", ""))
        except Exception:
            pass

        # For login attempts, try to extract username from request body
        if not username and path == "/api/auth/login":
            username = "(login_attempt)"

        ip = request.headers.get(
            "x-real-ip", request.client.host if request.client else ""
        )
        user_agent = request.headers.get("user-agent", "")[:500]

        # Log to database asynchronously
        try:
            db = getattr(request.app.state, "db_pool", None)
            if db and username:
                await db.execute(
                    """INSERT INTO user_activity_log
                       (username, action, category, risk_level, ip_address, user_agent, details)
                       VALUES ($1, $2, $3, $4, $5::inet, $6, $7::jsonb)""",
                    username,
                    action,
                    category,
                    risk_level,
                    ip if ip else None,
                    user_agent,
                    f'{{"path": "{path}", "method": "{method}", "status": {response.status_code}, "elapsed_ms": {int(elapsed*1000)}}}',
                )
                # Dual-write a audit_log (registro de compliance/eDiscovery)
                await db.execute(
                    """INSERT INTO audit_log (admin_user, action, target, details, ip_address)
                       VALUES ($1, $2, $3, $4::jsonb, $5::inet)""",
                    username,
                    action,
                    category,
                    f'{{"path": "{path}", "method": "{method}", "status": {response.status_code}, "risk": "{risk_level}"}}',
                    ip if ip else None,
                )
        except Exception as e:
            logger.warning("Audit log failed: %s", e)

        return response
