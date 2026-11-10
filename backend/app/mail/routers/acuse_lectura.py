"""Responder (o declinar) la confirmación de lectura que pide un correo recibido (09/11/2026).

`POST /api/mail/acuse-lectura` {folder, uid, enviar}: con `enviar=true` arma y manda el acuse
estándar al remitente; en ambos casos marca el correo con `$MDNSent` para no volver a preguntar.
La decisión la toma la persona en el aviso del correo (o su preferencia «siempre / preguntar /
nunca» en Configuración → General).
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from app.auth.dependencies import get_current_user
from app.core.session import get_imap_login_user, get_user_password
from app.mail.clients.imap_client import fetch_full_message, uid_set_flags
from app.mail.clients.imap_pool import get_pooled_imap
from app.mail.routers.attachments import _validate_folder
from app.mail.services import acuse_lectura

log = logging.getLogger("maquita.webmail.acuse_lectura")

router = APIRouter(prefix="/api/mail/acuse-lectura", tags=["acuse-lectura"])


class PeticionAcuse(BaseModel):
    folder: str
    uid: int
    enviar: bool = True


async def _nombre_mostrar(request: Request, username: str) -> str:
    try:
        fila = await request.app.state.db_pool.fetchrow(
            "SELECT display_name FROM user_preferences WHERE username = $1", username
        )
        return (fila["display_name"] if fila else "") or ""
    except Exception:
        return ""


@router.post("")
async def responder_acuse(
    body: PeticionAcuse, request: Request, username: str = Depends(get_current_user)
):
    _validate_folder(body.folder)
    password = await get_user_password(request, username)
    login_user = await get_imap_login_user(request, username)
    async with get_pooled_imap(login_user, password) as imap:
        raw = await fetch_full_message(imap, body.folder, body.uid, mark_seen=False)
        if not raw:
            raise HTTPException(status_code=404, detail="No se encontró el correo")
        pedido = acuse_lectura.pedido_acuse(raw["raw_email"], raw.get("flags") or [])
        if pedido is None:
            # Ya se contestó o el correo no lo pide: no hay nada que enviar.
            return {"enviado": False, "destinatario": None, "motivo": "no_corresponde"}
        enviado = False
        if body.enviar:
            mdn = acuse_lectura.construir_mdn(
                raw["raw_email"], username, await _nombre_mostrar(request, username)
            )
            if mdn is None:
                raise HTTPException(
                    status_code=400, detail="El correo no pide confirmación de lectura"
                )
            try:
                await acuse_lectura.enviar_mdn(mdn, username, password)
            except Exception as e:
                log.warning(
                    "acuse de lectura: no se pudo enviar de %s a %s (%s)",
                    username,
                    pedido["to"],
                    e,
                )
                raise HTTPException(
                    status_code=502,
                    detail="No se pudo enviar la confirmación. Intente de nuevo.",
                )
            enviado = True
        await uid_set_flags(
            imap, body.folder, body.uid, acuse_lectura.MARCA_MDN, add=True
        )
    return {"enviado": enviado, "destinatario": pedido["to"]}
