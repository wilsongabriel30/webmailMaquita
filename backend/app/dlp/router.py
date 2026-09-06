"""
DLP — Router del webmail. El compositor llama a /api/mail/dlp/check ANTES de
enviar; si hay hallazgos con accion 'warn'/'block' muestra un aviso al usuario.
El bloqueo definitivo se refuerza tambien en el endpoint de envio (compose.py).
"""
from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel

from app.auth.dependencies import get_current_user

from . import policy as dlp_policy
from . import service as dlp_service

router = APIRouter(prefix="/api/mail/dlp", tags=["dlp"])


class DlpCheckRequest(BaseModel):
    subject: str = ""
    text_body: str = ""
    html_body: str = ""
    to: list[str] = []
    cc: list[str] = []
    bcc: list[str] = []


@router.post("/check")
async def dlp_check(body: DlpCheckRequest, request: Request,
                    username: str = Depends(get_current_user)):
    """Analiza el borrador y devuelve la accion recomendada y los hallazgos."""
    db = request.app.state.db_pool
    scan = await dlp_service.scan(db, body.subject, body.text_body, body.html_body)
    rcpts = list(body.to or []) + list(body.cc or []) + list(body.bcc or [])
    return await dlp_policy.decide(db, scan, rcpts, await dlp_policy.is_admin(db, username))
