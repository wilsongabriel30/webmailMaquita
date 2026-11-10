"""Firmar un PDF adjunto sin salir del correo (09/11/2026).

Pedido: «en los PDF que llegan al correo, poder firmarlos directamente desde allí, sin
descargar y subir a Raíces; solo firmar, no editar; también desde el celular».

Flujo: el frontend pide `GET /mail/firma-pdf/certificados` (qué certificados tiene la persona
en Raíces) y luego `POST /mail/firma-pdf/firmar` con la ubicación del adjunto (carpeta, uid,
parte) y las opciones. Aquí se lee el adjunto del IMAP con la sesión de la persona y se manda a
Raíces (`services/firma_raices.py`), que lo firma con su certificado y lo devuelve. El PDF
firmado vuelve al navegador, que lo descarga o lo adjunta a una respuesta / reenvío.
La identidad ante Raíces es el correo con el que la persona inició sesión.
"""

from __future__ import annotations

import logging

import httpx
from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import JSONResponse, Response

from app.auth.dependencies import get_current_user
from app.core.session import get_imap_login_user, get_user_password
from app.mail.clients.imap_client import fetch_attachment, get_imap_connection
from app.mail.routers.attachments import _content_disposition, _validate_folder
from app.mail.services import firma_raices, pdf_paginas

log = logging.getLogger("maquita.webmail.firma_pdf")

router = APIRouter(
    prefix="/api/mail/firma-pdf", tags=["firma-pdf"]
)  # mismo prefijo /api/mail que attachments.py

# «manual» = rectángulo dibujado por la persona (x, y, ancho, alto en puntos PDF, origen abajo-izquierda).
POSICIONES = {
    "manual",
    "abajo-derecha",
    "abajo-izquierda",
    "abajo-centro",
    "arriba-derecha",
    "arriba-izquierda",
    "invisible",
}
MAX_P12_BYTES = 64 * 1024


async def _leer_pdf_adjunto(
    request: Request, username: str, folder: str, uid: int, part_number: str
) -> bytes:
    """Lee el adjunto del IMAP con la sesión de la persona y comprueba que sea un PDF."""
    _validate_folder(folder)
    contrasena_imap = await get_user_password(request, username)
    login_user = await get_imap_login_user(request, username)
    imap = await get_imap_connection(login_user, contrasena_imap)
    try:
        pdf = await fetch_attachment(imap, folder, uid, part_number)
    finally:
        try:
            await imap.logout()
        except Exception:
            pass
    if pdf is None:
        raise HTTPException(status_code=404, detail="No se encontró el adjunto")
    if not pdf.startswith(b"%PDF"):
        raise HTTPException(status_code=400, detail="El adjunto no es un PDF")
    return pdf


MAX_PDF_SUBIDO = 40 * 1024 * 1024


async def _leer_pdf_subido(archivo: UploadFile) -> bytes:
    """PDF que manda el navegador (la versión ya firmada, para seguir firmando sobre ella)."""
    pdf = await archivo.read()
    if not pdf.startswith(b"%PDF"):
        raise HTTPException(status_code=400, detail="El archivo no es un PDF")
    if len(pdf) > MAX_PDF_SUBIDO:
        raise HTTPException(status_code=400, detail="El PDF es demasiado grande")
    return pdf


@router.get("/pagina")
async def pagina(
    request: Request,
    folder: str,
    uid: int,
    part_number: str,
    pagina: int = -1,
    ancho: int = 900,
    username: str = Depends(get_current_user),
):
    """Una página del PDF adjunto como PNG, para dibujar encima el área de la firma.

    Cabeceras: X-Pagina (la dibujada), X-Paginas (total), X-Ancho-Pt / X-Alto-Pt (tamaño en puntos).
    """
    pdf = await _leer_pdf_adjunto(request, username, folder, uid, part_number)
    return await _respuesta_pagina(pdf, pagina, ancho, folder, uid)


@router.post("/pagina")
async def pagina_de_pdf_subido(
    archivo: UploadFile = File(...),
    pagina: int = Form(-1),
    ancho: int = Form(900),
    username: str = Depends(get_current_user),
):
    """Igual que GET /pagina, pero sobre un PDF que manda el navegador: la versión ya firmada,
    para dibujar la segunda, tercera… firma (varias firmas o la misma en varias hojas).
    """
    pdf = await _leer_pdf_subido(archivo)
    return await _respuesta_pagina(pdf, pagina, ancho, "subido", 0)


async def _respuesta_pagina(
    pdf: bytes, pagina: int, ancho: int, folder: str, uid: int
) -> Response:
    try:
        hoja = await pdf_paginas.dibujar_pagina(pdf, pagina, ancho)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:  # PDF dañado o cifrado
        log.warning(
            "firma-pdf: no se pudo dibujar la página %s de %s/%s (%s)",
            pagina,
            folder,
            uid,
            e,
        )
        raise HTTPException(
            status_code=400, detail="No se pudo mostrar esta página del PDF"
        )
    return Response(
        content=hoja.png,
        media_type="image/png",
        headers={
            "Cache-Control": "private, max-age=600",
            "X-Pagina": str(hoja.pagina),
            "X-Paginas": str(hoja.paginas),
            "X-Ancho-Pt": f"{hoja.ancho_pt:.2f}",
            "X-Alto-Pt": f"{hoja.alto_pt:.2f}",
            "Access-Control-Expose-Headers": "X-Pagina, X-Paginas, X-Ancho-Pt, X-Alto-Pt",
        },
    )


def _respuesta_error(e: firma_raices.ErrorFirma) -> JSONResponse:
    cuerpo = dict(e.cuerpo)
    cuerpo.setdefault("exito", False)
    cuerpo.setdefault("mensaje", str(e))
    cuerpo["detail"] = cuerpo["mensaje"]
    cuerpo["url_raices"] = firma_raices.url_base() + str(
        cuerpo.get("url_raices") or "/herramientas/editor-pdf/"
    )
    return JSONResponse(
        status_code=e.status if 400 <= e.status < 600 else 502, content=cuerpo
    )


def _no_configurado() -> JSONResponse:
    return JSONResponse(
        status_code=503,
        content={
            "exito": False,
            "codigo": "NO_CONFIGURADO",
            "detail": "La firma desde el correo aún no está habilitada en este servidor.",
            "mensaje": "La firma desde el correo aún no está habilitada en este servidor.",
        },
    )


@router.get("/certificados")
async def certificados(username: str = Depends(get_current_user)):
    """Certificados guardados en Raíces de la persona conectada (solo metadatos)."""
    if not firma_raices.configurado():
        return _no_configurado()
    try:
        datos = await firma_raices.certificados(username)
    except firma_raices.ErrorFirma as e:
        return _respuesta_error(e)
    except httpx.HTTPError as e:
        log.warning("firma-pdf: Raíces no responde (%s)", e)
        raise HTTPException(
            status_code=502,
            detail="Raíces no responde en este momento. Intente de nuevo.",
        )
    datos["url_raices"] = firma_raices.url_base() + str(
        datos.get("url_raices") or "/herramientas/editor-pdf/"
    )
    return datos


@router.post("/firmar")
async def firmar(
    request: Request,
    folder: str = Form(""),
    uid: int = Form(0),
    part_number: str = Form(""),
    filename: str = Form("documento.pdf"),
    archivo: UploadFile | None = File(None),
    certificado_id: str = Form(""),
    password: str = Form(""),
    pagina: int = Form(-1),
    posicion: str = Form("abajo-derecha"),
    razon: str = Form(""),
    guardar: str = Form(""),
    guardar_password: str = Form(""),
    x: float | None = Form(None),
    y: float | None = Form(None),
    ancho: float | None = Form(None),
    alto: float | None = Form(None),
    certificado: UploadFile | None = File(None),
    username: str = Depends(get_current_user),
):
    """Firma el adjunto PDF indicado y devuelve el PDF firmado.

    Con `archivo` (PDF subido) se firma ese PDF en vez del adjunto: así se ponen varias firmas seguidas.
    `posicion=manual` lleva el rectángulo dibujado por la persona: `x`, `y` (esquina inferior
    izquierda, puntos PDF), `ancho`, `alto`. Con un .p12 subido, `guardar=1` lo deja guardado en
    Raíces para la próxima vez (solo si la firma salió bien) y `guardar_password=1` guarda también
    su contraseña cifrada allí."""
    if not firma_raices.configurado():
        return _no_configurado()
    if archivo is None:
        if not folder or not uid or not part_number:
            raise HTTPException(
                status_code=400,
                detail="Indique el adjunto (carpeta, uid y parte) o suba el PDF",
            )
        _validate_folder(folder)
    if posicion not in POSICIONES:
        raise HTTPException(status_code=400, detail="Posición del sello no válida")
    if posicion == "manual":
        if x is None or y is None or not ancho or not alto or ancho < 20 or alto < 10:
            raise HTTPException(
                status_code=400, detail="Dibuje en la página el área donde irá la firma"
            )
        if x < 0 or y < 0 or ancho > 5000 or alto > 5000:
            raise HTTPException(
                status_code=400, detail="El área de la firma está fuera de la página"
            )
    if not certificado_id and certificado is None:
        raise HTTPException(
            status_code=400,
            detail="Elija un certificado guardado o suba un archivo .p12",
        )

    p12 = None
    if certificado is not None:
        contenido = await certificado.read()
        if not contenido:
            raise HTTPException(status_code=400, detail="El archivo .p12 está vacío")
        if len(contenido) > MAX_P12_BYTES:
            raise HTTPException(
                status_code=400, detail="El archivo .p12 es demasiado grande"
            )
        p12 = (certificado.filename or "certificado.p12", contenido)

    # Primera firma: el adjunto del IMAP. Siguientes: el PDF ya firmado que manda el navegador
    # (Raíces firma de forma incremental; las firmas anteriores se conservan).
    if archivo is not None:
        pdf = await _leer_pdf_subido(archivo)
    else:
        pdf = await _leer_pdf_adjunto(request, username, folder, uid, part_number)

    campos = {
        "certificado_id": certificado_id,
        "password": password,
        "pagina": pagina,
        "posicion": posicion,
        "razon": razon,
        "guardar": "1" if guardar.lower() in ("1", "true", "on") else "",
        "guardar_password": (
            "1" if guardar_password.lower() in ("1", "true", "on") else ""
        ),
    }
    if posicion == "manual":
        # Raíces toma x/y como «manual» y estampa exactamente ahí (puntos PDF, origen abajo-izquierda).
        campos.update(
            {
                "x": f"{x:.2f}",
                "y": f"{y:.2f}",
                "ancho": f"{ancho:.2f}",
                "alto": f"{alto:.2f}",
            }
        )
    try:
        firmado, nombre, extras = await firma_raices.firmar(
            username, filename, pdf, campos, p12
        )
    except firma_raices.ErrorFirma as e:
        return _respuesta_error(e)
    except httpx.HTTPError as e:
        log.warning("firma-pdf: Raíces no responde al firmar (%s)", e)
        raise HTTPException(
            status_code=502,
            detail="Raíces no responde en este momento. Intente de nuevo.",
        )

    log.info(
        "firma-pdf: %s firmó «%s» (%s/%s parte %s, %d bytes, %s)",
        username,
        filename,
        folder,
        uid,
        part_number,
        len(firmado),
        posicion,
    )
    return Response(
        content=firmado,
        media_type="application/pdf",
        headers={
            "Content-Disposition": _content_disposition(nombre),
            "X-Content-Type-Options": "nosniff",
            "Cache-Control": "no-store",
            "X-Certificado-Guardado": extras.get("certificado_guardado", ""),
            "X-Certificado-Password-Guardada": (
                "1" if extras.get("password_guardada") else "0"
            ),
        },
    )


@router.post("/consentimiento")
async def consentimiento(
    request: Request,
    version: str = Form(""),
    acepta: str = Form(""),
    username: str = Depends(get_current_user),
):
    """Acepta desde el correo el aviso de privacidad / términos de la firma electrónica (queda en Raíces)."""
    if not firma_raices.configurado():
        return _no_configurado()
    if acepta.lower() not in ("1", "true", "on"):
        raise HTTPException(
            status_code=400, detail="Debe marcar que acepta los términos"
        )
    ip = request.client.host if request.client else ""
    try:
        datos = await firma_raices.aceptar_consentimiento(username, version, ip)
    except firma_raices.ErrorFirma as e:
        return _respuesta_error(e)
    except httpx.HTTPError as e:
        log.warning("firma-pdf: Raíces no responde al aceptar términos (%s)", e)
        raise HTTPException(
            status_code=502,
            detail="Raíces no responde en este momento. Intente de nuevo.",
        )
    log.info(
        "firma-pdf: %s aceptó los términos de la firma (versión %s)",
        username,
        datos.get("version"),
    )
    return datos
