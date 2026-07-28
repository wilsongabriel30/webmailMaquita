"""Endpoints del panel para reenviar correos rebotados.

  GET  /api/resend/cuentas          -> cuentas con rebotes recientes (para el selector)
  GET  /api/resend/rebotes/{cuenta} -> rebotes de esa cuenta, listos para reenviar
  POST /api/resend/enviar           -> reenvia un correo a los destinatarios elegidos

Toda accion de reenvio queda registrada en la auditoria del panel.
"""
from fastapi import APIRouter, Request, HTTPException, Depends

from app.auth.dependencies import get_current_admin, require_role
from app.resend import bounce_scan, mailbox_read, reinject

router = APIRouter(prefix="/api/resend", tags=["resend"])


def _db(r: Request):
    return r.app.state.db


async def _audit(r: Request, admin: dict, action: str, target: str | None = None):
    """Deja constancia de quien reenvio que (misma tabla que el resto del panel)."""
    await _db(r).execute(
        "INSERT INTO admin_audit (admin_id, admin_username, action, target, ip_address)"
        " VALUES ($1,$2,$3,$4,$5)",
        admin["id"], admin["username"], action, target,
        r.headers.get("X-Real-IP", r.client.host if r.client else ""),
    )


@router.get("/cuentas")
async def cuentas(admin: dict = Depends(get_current_admin)):
    """Cuentas que recibieron rebotes ultimamente, con su numero de rebotes."""
    return await bounce_scan.cuentas_con_rebotes()


@router.get("/rebotes/{cuenta}")
async def rebotes(cuenta: str, dias: int = 15, admin: dict = Depends(get_current_admin)):
    """Rebotes de una cuenta: asunto, destinatarios que fallaron y motivo."""
    try:
        return await mailbox_read.listar_rebotes(cuenta, dias)
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        raise HTTPException(500, f"No se pudieron leer los rebotes: {e}")


@router.post("/enviar")
async def enviar(request: Request, admin: dict = Depends(require_role("superadmin", "admin"))):
    """Reenvia el correo original a los destinatarios indicados.

    Espera JSON: {"cuenta": "...", "uid_rebote": "123", "message_id": "...",
                  "destinatarios": ["..."]}
    Se reenvia SOLO a los destinatarios indicados (normalmente los que fallaron), para no
    duplicar el correo a quienes si lo recibieron.
    """
    datos = await request.json()
    cuenta = (datos.get("cuenta") or "").strip()
    message_id = (datos.get("message_id") or "").strip()
    uid_rebote = str(datos.get("uid_rebote") or "").strip()
    destinatarios = [d.strip() for d in (datos.get("destinatarios") or []) if d.strip()]

    if not cuenta or not destinatarios or not (uid_rebote or message_id):
        raise HTTPException(400, "Faltan cuenta, destinatarios y uid_rebote o message_id")

    original = ""
    try:
        # 1. Via preferente: el propio rebote suele traer el mensaje completo adjunto.
        if uid_rebote:
            dsn = await mailbox_read.obtener_rebote_crudo(cuenta, uid_rebote)
            original = mailbox_read.extraer_original_del_dsn(dsn)
        # 2. Si el rebote solo traia cabeceras, se busca el original en Enviados.
        if not original and message_id:
            original = await mailbox_read.obtener_original(cuenta, message_id)
    except ValueError as e:
        raise HTTPException(400, str(e))

    if not original:
        # Caso tipico: cuentas de sistema (ERP) que envian por SMTP sin guardar copia.
        raise HTTPException(
            404,
            "No se pudo recuperar el mensaje original: el rebote no trae copia y tampoco "
            "aparece en Enviados. Si la cuenta envia desde un sistema externo (por ejemplo "
            "el ERP), hay que regenerar el correo alli.",
        )

    try:
        await reinject.reinyectar(cuenta, destinatarios, original)
    except (ValueError, RuntimeError) as e:
        raise HTTPException(500, f"No se pudo reenviar: {e}")

    await _audit(request, admin, "resend_bounced", f"{cuenta} -> {', '.join(destinatarios)}")
    return {"ok": True, "reenviado_a": destinatarios}
