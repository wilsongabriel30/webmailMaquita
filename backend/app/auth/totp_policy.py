"""
2FA obligatorio — política (2026-08-28).

Controlado desde el panel admin (security_config.totp_required / totp_deadline):
  totp_required = False -> el 2FA es opcional (comportamiento anterior).
  totp_required = True  -> todo usuario sin 2FA ve un aviso al entrar; a partir de
                           totp_deadline el aviso es bloqueante hasta que lo active.
Los administradores (tabla admin) se consideran siempre obligados cuando required=True.
Nota: el 2FA protege el webmail. Los clientes IMAP/SMTP (Outlook, móvil) siguen
usando solo la contraseña, protegidos por geobloqueo + Fail2ban.
"""
from __future__ import annotations
from datetime import date
from fastapi import APIRouter, Request, Depends

from app.auth.dependencies import get_current_user

router = APIRouter(prefix="/api/auth/2fa-policy", tags=["2fa"])


async def get_policy(db) -> dict:
    try:
        row = await db.fetchrow(
            "SELECT COALESCE(totp_required,false) AS req, totp_deadline FROM security_config WHERE id = 1")
    except Exception:
        row = None
    if not row:
        return {"required": False, "deadline": None}
    return {"required": bool(row["req"]),
            "deadline": row["totp_deadline"].isoformat() if row["totp_deadline"] else None}


@router.get("/status")
async def status(request: Request, username: str = Depends(get_current_user)):
    db = request.app.state.db_pool
    pol = await get_policy(db)
    try:
        r = await db.fetchrow("SELECT enabled FROM user_totp WHERE username = $1", username)
        enrolled = bool(r and r["enabled"])
    except Exception:
        enrolled = False
    blocked = False
    if pol["required"] and not enrolled:
        blocked = (pol["deadline"] is None) or (date.fromisoformat(pol["deadline"]) <= date.today())
    return {**pol, "enrolled": enrolled, "must_enroll": pol["required"] and not enrolled, "blocked": blocked}
