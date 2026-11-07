"""Descargar un archivo que viene DENTRO de un correo adjunto (.eml), 06/11/2026.

Cuando alguien reenvía «como adjunto» (Outlook lo hace a menudo), los archivos del
correo original quedan dentro del .eml. La vista previa (adjunto_correo.py) solo los
nombraba y nadie podía bajarlos: «dicen que comparten un listado y no tengo los adjuntos».
Aquí se entrega cada uno por su nombre, siempre como descarga (nunca se pinta en la página).
"""

import email
from email import policy

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import Response

from app.auth.dependencies import get_current_user
from app.core.session import get_imap_login_user, get_user_password
from app.mail.clients.imap_client import fetch_attachment, get_imap_connection
from app.mail.routers.adjunto_correo import MAX_BYTES
from app.mail.routers.attachments import _content_disposition, _validate_folder

router = APIRouter(prefix="/api/mail", tags=["mail-attachments"])

# Tipos que un navegador podría ejecutar o pintar: se entregan como binario genérico.
_PELIGROSOS = {
    "text/html",
    "image/svg+xml",
    "application/xhtml+xml",
    "text/xml",
    "application/xml",
}


def archivo_del_correo(crudo: bytes, nombre: str) -> tuple[bytes, str]:
    """Contenido y tipo del primer archivo con ese nombre dentro del correo. Sin E/S."""
    if len(crudo) > MAX_BYTES:
        raise HTTPException(
            status_code=413, detail="El correo adjunto es demasiado grande"
        )
    mensaje = email.message_from_bytes(bytes(crudo), policy=policy.compat32)
    for parte in mensaje.walk():
        if parte.is_multipart() or parte.get_filename() != nombre:
            continue
        datos = parte.get_payload(decode=True)
        if datos is None:
            continue
        tipo = parte.get_content_type()
        if tipo in _PELIGROSOS or tipo.startswith("text/"):
            tipo = "application/octet-stream"
        return datos, tipo
    raise HTTPException(
        status_code=404, detail="No se encontró ese archivo en el correo adjunto"
    )


@router.get("/attachment-message/{folder}/{uid}/{part_number}/archivo")
async def descargar_archivo_de_correo_adjunto(
    folder: str,
    uid: int,
    part_number: str,
    request: Request,
    nombre: str = Query(..., min_length=1, max_length=500),
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
    datos, tipo = archivo_del_correo(crudo, nombre)
    return Response(
        content=datos,
        media_type=tipo,
        headers={
            "Content-Disposition": _content_disposition(nombre),
            "X-Content-Type-Options": "nosniff",
            "Cache-Control": "private, no-store",
        },
    )
