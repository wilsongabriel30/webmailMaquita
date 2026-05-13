"""
Compliance Auth Module — Fail-fast + RBAC
Soporta JWT via cookie (webmail) y Bearer token (admin panel).
"""

import os
import logging
from functools import wraps

import jwt
from fastapi import Request, HTTPException

logger = logging.getLogger("compliance.auth")

# --- Fail-fast: el backend NO arranca sin este secreto ---
ADMIN_JWT_SECRET = os.getenv("ADMIN_JWT_SECRET")
if not ADMIN_JWT_SECRET:
    raise RuntimeError(
        "ADMIN_JWT_SECRET no configurado — el backend no puede arrancar sin este secreto"
    )

ADMIN_JWT_ALGORITHM = "HS256"

# ---------------------------------------------------------------------------
# RBAC — permisos por rol
# ---------------------------------------------------------------------------
COMPLIANCE_ROLES: dict[str, set[str]] = {
    "superadmin": {
        "compliance_read",
        "compliance_write",
        "compliance_export",
        "compliance_security",
        "compliance_admin",
    },
    "admin": {
        "compliance_read",
        "compliance_admin",
    },
    "compliance_manager": {
        "compliance_read",
        "compliance_write",
    },
    "compliance_auditor": {
        "compliance_read",
    },
    "compliance_exporter": {
        "compliance_read",
        "compliance_export",
    },
    "security_admin": {
        "compliance_read",
        "compliance_security",
    },
}


# ---------------------------------------------------------------------------
# Helpers internos
# ---------------------------------------------------------------------------


def _decode_admin_token(token: str) -> dict:
    """Decodifica un Bearer JWT del admin panel."""
    try:
        payload = jwt.decode(token, ADMIN_JWT_SECRET, algorithms=[ADMIN_JWT_ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expirado")
    except jwt.InvalidTokenError as exc:
        raise HTTPException(status_code=401, detail=f"Token invalido: {exc}")


def _decode_webmail_token(token: str) -> dict:
    """Decodifica un JWT de cookie del webmail usando SECRET_KEY de la app."""
    try:
        from app.config import get_settings

        secret = get_settings().secret_key
    except Exception:
        raise HTTPException(
            status_code=500, detail="No se pudo obtener SECRET_KEY del webmail"
        )

    try:
        payload = jwt.decode(token, secret, algorithms=["HS256"])
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token de webmail expirado")
    except jwt.InvalidTokenError as exc:
        raise HTTPException(status_code=401, detail=f"Token de webmail invalido: {exc}")


async def _get_user_and_role(request: Request) -> tuple[str, str]:
    """
    Extrae username y rol desde JWT.

    Orden de precedencia:
      1. Bearer token en header Authorization (admin panel)
      2. Cookie 'access_token' (webmail)

    Retorna (username, role).
    """

    # --- 1. Intentar Bearer token (admin panel) ---
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        raw_token = auth_header[7:].strip()
        if raw_token:
            payload = _decode_admin_token(raw_token)
            username = (
                payload.get("sub")
                or payload.get("username")
                or payload.get("email", "unknown")
            )
            role = payload.get("role", "admin")
            # Validar que el rol exista en nuestra tabla
            if role not in COMPLIANCE_ROLES:
                logger.warning(
                    "Rol desconocido '%s' para usuario '%s', asignando admin",
                    role,
                    username,
                )
                role = "admin"
            logger.info("Auth Bearer: usuario=%s rol=%s", username, role)
            return (str(username), role)

    # --- 2. Intentar cookie (webmail) ---
    cookie_token = request.cookies.get("access_token")
    if cookie_token:
        # Algunos frameworks ponen "Bearer " dentro de la cookie
        if cookie_token.startswith("Bearer "):
            cookie_token = cookie_token[7:].strip()
        if cookie_token:
            payload = _decode_webmail_token(cookie_token)
            username = (
                payload.get("sub")
                or payload.get("username")
                or payload.get("email", "unknown")
            )
            is_admin = payload.get("is_admin", False)
            # Webmail: si es admin, minimo compliance_auditor
            if is_admin:
                role = "compliance_auditor"
            else:
                raise HTTPException(
                    status_code=403,
                    detail="Acceso a compliance requiere privilegios de administrador",
                )
            logger.info("Auth Cookie: usuario=%s rol=%s", username, role)
            return (str(username), role)

    # --- Sin credenciales ---
    raise HTTPException(status_code=401, detail="No se encontro token de autenticacion")


# ---------------------------------------------------------------------------
# Funciones de autorizacion (se usan como dependencias de FastAPI)
# ---------------------------------------------------------------------------


async def require_compliance_admin(request: Request) -> str:
    """Backward compatible — requiere admin o superadmin."""
    username, role = await _get_user_and_role(request)
    perms = COMPLIANCE_ROLES.get(role, set())
    if "compliance_admin" not in perms:
        logger.warning(
            "Acceso denegado (compliance_admin): usuario=%s rol=%s", username, role
        )
        raise HTTPException(
            status_code=403,
            detail="Rol insuficiente para compliance (se requiere admin o superadmin)",
        )
    return username


async def require_compliance_read(request: Request) -> str:
    """Lectura de compliance — auditor, manager, exporter, security_admin, superadmin, admin."""
    username, role = await _get_user_and_role(request)
    perms = COMPLIANCE_ROLES.get(role, set())
    if "compliance_read" not in perms:
        logger.warning(
            "Acceso denegado (compliance_read): usuario=%s rol=%s", username, role
        )
        raise HTTPException(
            status_code=403, detail="Rol insuficiente para lectura de compliance"
        )
    return username


async def require_compliance_write(request: Request) -> str:
    """Escritura de compliance — manager, superadmin."""
    username, role = await _get_user_and_role(request)
    perms = COMPLIANCE_ROLES.get(role, set())
    if "compliance_write" not in perms:
        logger.warning(
            "Acceso denegado (compliance_write): usuario=%s rol=%s", username, role
        )
        raise HTTPException(
            status_code=403,
            detail="Rol insuficiente para escritura de compliance (se requiere compliance_manager o superadmin)",
        )
    return username


async def require_compliance_export(request: Request) -> str:
    """Exportacion de evidencia — exporter, superadmin."""
    username, role = await _get_user_and_role(request)
    perms = COMPLIANCE_ROLES.get(role, set())
    if "compliance_export" not in perms:
        logger.warning(
            "Acceso denegado (compliance_export): usuario=%s rol=%s", username, role
        )
        raise HTTPException(
            status_code=403,
            detail="Rol insuficiente para exportacion de compliance (se requiere compliance_exporter o superadmin)",
        )
    return username


async def require_compliance_security(request: Request) -> str:
    """Endpoints de seguridad — security_admin, superadmin."""
    username, role = await _get_user_and_role(request)
    perms = COMPLIANCE_ROLES.get(role, set())
    if "compliance_security" not in perms:
        logger.warning(
            "Acceso denegado (compliance_security): usuario=%s rol=%s", username, role
        )
        raise HTTPException(
            status_code=403,
            detail="Rol insuficiente para seguridad de compliance (se requiere security_admin o superadmin)",
        )
    return username
