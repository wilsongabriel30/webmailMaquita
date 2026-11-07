"""Último correo sin leer de una cuenta (remitente y asunto) para el aviso de la barra de cuentas.

06/11/2026: la barra (components/layout/BarraCuentas.tsx + lib/avisosOtrasCuentas.ts) solo conocía
conteos y avisaba «Correo nuevo en <cuenta>». Ahora, cuando sube el conteo de una cuenta, pide aquí
quién envió el último y su asunto. Solo se consulta en ese momento (no en cada sondeo), la bandeja se
abre con SELECT y la cabecera se lee con BODY.PEEK: nada queda marcado como leído.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from app.auth.dependencies import get_current_user
from app.config import get_settings
from app.core.session import get_imap_login_user, get_user_password
from app.mail.clients.imap_client import _decode_lines
from app.mail.clients.imap_pool import get_pooled_imap
from app.mail.services.cuentas_delegadas import credenciales_maestras, cuentas_de
from app.websocket.resumen_correo_nuevo import resumen_correo

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/mail", tags=["mail-cuentas"])


@router.get("/cuentas/ultimo-sin-leer")
async def ultimo_sin_leer(
    request: Request,
    cuenta: str = Query(...),
    username: str = Depends(get_current_user),
):
    cuenta = cuenta.strip().lower()
    if cuenta == username.lower():
        usuario = await get_imap_login_user(request, username)
        clave = await get_user_password(request, username)
    else:
        asignadas = {
            str(c["email"]).lower()
            for c in await cuentas_de(request.app.state.db_pool, username)
        }
        if cuenta not in asignadas:
            raise HTTPException(status_code=403, detail="Cuenta no asignada")
        usuario, clave = credenciales_maestras(cuenta, get_settings())
    try:
        async with get_pooled_imap(usuario, clave) as imap:
            await imap.select("INBOX")
            r = await imap.uid_search("UNSEEN")
            uid = None
            if getattr(r, "result", "") == "OK":
                for linea in _decode_lines(r.lines):
                    uids = [u for u in linea.split() if u.isdigit()]
                    if uids:
                        uid = int(uids[-1])
            resumen = await resumen_correo(imap, uid) if uid else {}
            return {"uid": uid, **resumen}
    except HTTPException:
        raise
    except Exception as e:
        log.warning("ultimo-sin-leer: %s para %s: %s", cuenta, username, e)
        return {"uid": None}
