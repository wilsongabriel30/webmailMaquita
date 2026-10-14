"""Panel · «Cuentas sin clave válida» (/api/admin/password-audit).

Antes esta pantalla llamaba a una ruta que solo existe en el backend del correo
(puerto 8000, sesión de webmail) y el panel (puerto 8001) respondía 404.
Hallazgo C06 del anexo de revisión de configuración de correo (13/10/2026).
"""

import json
import secrets

from fastapi import APIRouter, Depends, HTTPException, Request

from app.auth.dependencies import get_current_admin, require_role
from app.password_audit import service
from app.wrappers.doveadm import generate_password_hash, verify_password

router = APIRouter(prefix="/api/admin", tags=["password-audit"])


def _db(r: Request):
    return r.app.state.db


async def _audit(
    r: Request, a: dict, action: str, target: str, details: dict | None = None
):
    await _db(r).execute(
        "INSERT INTO admin_audit (admin_id, admin_username, action, target, details, ip_address) "
        "VALUES ($1,$2,$3,$4,$5::jsonb,$6)",
        a["id"],
        a["username"],
        action,
        target,
        json.dumps(details) if details else None,
        r.headers.get("X-Real-IP", r.client.host if r.client else ""),
    )


@router.get("/password-audit")
async def password_audit(request: Request, admin: dict = Depends(get_current_admin)):
    """Solo lectura: cualquier rol del panel puede consultarla (el viewer incluido)."""
    return await service.audit(_db(request))


@router.post("/password-audit/reset")
async def password_audit_reset(
    request: Request, admin: dict = Depends(require_role("superadmin"))
):
    """Asigna una clave temporal aleatoria y reactiva el buzón.

    La clave se comprueba contra Dovecot antes de responder (misma garantía
    anti-desincronización que el resto del panel).
    """
    data = await request.json()
    username = (data.get("username") or "").strip().lower()
    if "@" not in username or len(username) > 255:
        raise HTTPException(400, "username requerido")
    db = _db(request)
    cur = await db.fetchrow(
        "SELECT username FROM mailbox WHERE username = $1", username
    )
    if not cur:
        raise HTTPException(404, "Buzón no encontrado")
    temp = secrets.token_urlsafe(12)
    pw_hash = await generate_password_hash(temp)
    await db.execute(
        "UPDATE mailbox SET password=$2, active=true, modified=NOW() WHERE username=$1",
        username,
        pw_hash,
    )
    if not await verify_password(username, temp):
        raise HTTPException(
            500, "La clave temporal no se aplicó correctamente. Intente nuevamente."
        )
    await _audit(
        request, admin, "password_reset_temp", username, {"origen": "password-audit"}
    )
    return {"username": username, "temp_password": temp}
