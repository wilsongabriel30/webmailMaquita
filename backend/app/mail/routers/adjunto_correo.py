"""Vista previa de un correo adjunto (.eml / message/rfc822).

Un .eml es texto, pero es el correo crudo: cabeceras, partes en base64 o
quoted-printable, HTML... Mostrarlo tal cual no sirve a nadie. Se abre como un
correo más, con el mismo lector (`parse_full_message`) y las mismas defensas que
la bandeja (`sanitize_html` + `apply_render_policy`), 12/10/2026.

Las imágenes remotas van SIEMPRE bloqueadas: el remitente de un correo adjunto no
está verificado (cualquiera puede escribir un From de la casa dentro de un .eml).
"""

from fastapi import APIRouter, Depends, HTTPException, Request

from app.auth.dependencies import get_current_user
from app.core.session import get_imap_login_user, get_user_password
from app.mail.clients.imap_client import (
    bytes_a_correo,
    fetch_attachment,
    get_imap_connection,
)
from app.mail.parsers.html_sanitizer import sanitize_html
from app.mail.parsers.mime_parser import parse_full_message
from app.mail.rendering.policy import apply_render_policy
from app.mail.routers.attachments import _validate_folder

router = APIRouter(prefix="/api/mail", tags=["mail-attachments"])

# Un correo adjunto más grande que esto se descarga, no se previsualiza.
MAX_BYTES = 25 * 1024 * 1024


def correo_adjunto_a_vista(crudo: bytes) -> dict:
    """Convierte un .eml en lo que pinta el visor. Sin E/S: se prueba sola."""
    if len(crudo) > MAX_BYTES:
        raise HTTPException(
            status_code=413, detail="El correo adjunto es demasiado grande"
        )
    normalizado = parse_full_message(bytes_a_correo(crudo))

    html = ""
    imagenes_bloqueadas = 0
    if normalizado.html_body:
        render = apply_render_policy(
            sanitize_html(normalizado.html_body),
            block_remote_images=True,
            cid_map=normalizado.cid_map,
        )
        html = render["html"]
        imagenes_bloqueadas = render.get("blocked_image_count", 0)

    return {
        "from": normalizado.from_addr,
        "to": normalizado.to_addr,
        "cc": normalizado.cc_addr,
        "subject": normalizado.subject,
        "date": normalizado.date,
        "text_body": normalizado.text_body,
        "html_body": html,
        "blocked_image_count": imagenes_bloqueadas,
        "attachments": [
            {"filename": a.filename, "content_type": a.content_type, "size": a.size}
            for a in normalizado.attachments
            if not a.is_inline
        ],
    }


@router.get("/attachment-message/{folder}/{uid}/{part_number}")
async def vista_correo_adjunto(
    folder: str,
    uid: int,
    part_number: str,
    request: Request,
    username: str = Depends(get_current_user),
):
    _validate_folder(folder)
    password = await get_user_password(request, username)
    login_user = await get_imap_login_user(request, username)
    imap = await get_imap_connection(login_user, password)
    try:
        crudo = await fetch_attachment(imap, folder, uid, part_number)
    finally:
        try:
            await imap.logout()
        except Exception:
            pass
    if crudo is None:
        raise HTTPException(status_code=404, detail="Attachment not found")
    return correo_adjunto_a_vista(crudo)
