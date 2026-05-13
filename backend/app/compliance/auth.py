"""Compliance Auth — acepta tanto cookie del webmail como Bearer token del admin panel.

El admin panel (puerto 8443/8001) usa JWT con secret diferente al webmail.
Este módulo permite que los endpoints de compliance funcionen desde ambos paneles.
"""
import os
import logging

import jwt as pyjwt
from fastapi import HTTPException, Request, status

logger = logging.getLogger("compliance.auth")

# Admin panel JWT config (mismos valores que /opt/maquita-admin/backend/app/config.py)
ADMIN_JWT_SECRET = os.getenv("ADMIN_JWT_SECRET", "maquita-admin-secret-2026-xK9pL2mN")
ADMIN_JWT_ALGORITHM = "HS256"


async def require_compliance_admin(request: Request) -> str:
    """Valida admin desde cookie del webmail O Bearer token del admin panel."""

    # 1. Intentar cookie del webmail (access_token)
    token = request.cookies.get("access_token")
    if token:
        try:
            from app.auth.jwt import decode_access_token
            payload = decode_access_token(token)
            if payload:
                username = payload.get("sub", "")
                if username:
                    # Verificar que es admin
                    db = request.app.state.db_pool
                    row = await db.fetchrow(
                        "SELECT superadmin FROM admin WHERE username = $1 AND active = true",
                        username,
                    )
                    if row:
                        return username
        except Exception:
            pass

    # 2. Intentar Bearer token del admin panel
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        bearer_token = auth_header[7:]
        try:
            payload = pyjwt.decode(bearer_token, ADMIN_JWT_SECRET, algorithms=[ADMIN_JWT_ALGORITHM])
            username = payload.get("username", "")
            role = payload.get("role", "")
            if username and role in ("superadmin", "admin"):
                return username
        except pyjwt.ExpiredSignatureError:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token expirado")
        except pyjwt.InvalidTokenError:
            pass

    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="No autenticado")
