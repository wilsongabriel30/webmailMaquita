"""Structured logging for Maquita Webmail.

Levels: info, warning, error, security.
"""

import logging
import time
import uuid
from contextvars import ContextVar

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

request_id_var: ContextVar[str] = ContextVar("request_id", default="")

logger = logging.getLogger("maquita.webmail")


def setup_logging() -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(
        logging.Formatter(
            "%(asctime)s [%(levelname)s] %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    )
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)


def log_event(
    level: str,
    action: str,
    module: str,
    user: str = "",
    latency_ms: float = 0,
    status: str = "ok",
    error_type: str = "",
    detail: str = "",
    **extra,
) -> None:
    rid = request_id_var.get("")
    parts = [f"rid={rid}", f"action={action}", f"module={module}"]
    if user:
        parts.append(f"user={user}")
    if latency_ms:
        parts.append(f"ms={latency_ms:.1f}")
    parts.append(f"status={status}")
    if error_type:
        parts.append(f"err={error_type}")
    if detail:
        parts.append(f"detail={detail}")
    for k, v in extra.items():
        parts.append(f"{k}={v}")

    msg = " | ".join(parts)
    level_map = {
        "info": logging.INFO,
        "warning": logging.WARNING,
        "error": logging.ERROR,
        "security": logging.WARNING,
    }
    logger.log(level_map.get(level, logging.INFO), msg)


class RequestIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        rid = str(uuid.uuid4())[:8]
        request_id_var.set(rid)
        request.state.request_id = rid
        start = time.monotonic()
        response: Response = await call_next(request)
        latency = (time.monotonic() - start) * 1000

        user = ""
        try:
            from app.auth.jwt import decode_access_token

            token = request.cookies.get("access_token")
            if token:
                payload = decode_access_token(token)
                if payload:
                    user = payload.get("sub", "")
        except Exception:
            pass

        log_event(
            "info",
            "http_request",
            "core",
            user=user,
            latency_ms=latency,
            status=str(response.status_code),
            method=request.method,
            path=request.url.path,
        )
        response.headers["X-Request-ID"] = rid
        return response
