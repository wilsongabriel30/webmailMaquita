"""Vista previa de un adjunto ANTES de enviarlo: Word, Excel y PowerPoint (06/11/2026).

Pedido de Finanzas: «mandamos una carta equivocada y a la persona le llegaron errores». Al redactar
se puede abrir lo adjuntado para comprobarlo. Imágenes, PDF, texto y código se ven en el propio
navegador (components/compose/VistaPreviaAdjuntoLocal.tsx); los documentos de Office necesitan
OnlyOffice, que descarga el archivo desde el servidor: se guarda 15 minutos en Redis y OnlyOffice lo
pide con un vale firmado. Solo lectura, sin descarga ni edición.
"""

import base64
import mimetypes
import secrets
import time

import jwt
from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile
from fastapi.responses import Response

from app.auth.dependencies import get_current_user
from app.config import get_settings
from app.mail.routers.attachments import _content_disposition
from app.mail.routers.onlyoffice import _DOWNLOAD_SECRET, _oo_cfg

settings = get_settings()
router = APIRouter(prefix="/api/mail", tags=["mail-vista-previa-local"])

_VIGENCIA = 900  # 15 minutos
_MAXIMO = 30 * 1024 * 1024
_TIPOS = {
    "docx": "word",
    "doc": "word",
    "odt": "word",
    "rtf": "word",
    "xlsx": "cell",
    "xls": "cell",
    "ods": "cell",
    "pptx": "slide",
    "ppt": "slide",
    "odp": "slide",
}


def _clave(ident: str) -> str:
    return f"vista_previa_local:{ident}"


@router.post("/vista-previa-local")
async def preparar_vista_previa(
    request: Request,
    archivo: UploadFile = File(...),
    username: str = Depends(get_current_user),
):
    nombre = (archivo.filename or "documento").replace("/", "_").replace("\\", "_")
    ext = nombre.rsplit(".", 1)[-1].lower() if "." in nombre else ""
    if ext not in _TIPOS:
        raise HTTPException(status_code=400, detail="Tipo de archivo sin vista previa")
    datos = await archivo.read(_MAXIMO + 1)
    if len(datos) > _MAXIMO:
        raise HTTPException(
            status_code=413, detail="Archivo demasiado grande para la vista previa"
        )

    ident = secrets.token_urlsafe(18)
    await request.app.state.redis.set(
        _clave(ident), base64.b64encode(datos).decode("ascii"), ex=_VIGENCIA
    )
    vale = jwt.encode(
        {
            "vpl": ident,
            "sub": username,
            "fn": nombre,
            "exp": int(time.time()) + _VIGENCIA,
        },
        _DOWNLOAD_SECRET,
        algorithm="HS256",
    )
    base = settings.public_base_url.rstrip("/")
    config = {
        "document": {
            "fileType": ext,
            "key": f"vpl_{ident[:20]}",
            "title": nombre,
            "url": f"{base}/api/mail/vista-previa-local/archivo?token={vale}",
            "permissions": {
                "edit": False,
                "download": False,
                "print": True,
                "comment": False,
                "review": False,
            },
        },
        "documentType": _TIPOS[ext],
        "editorConfig": {
            "mode": "view",
            "lang": "es",
            "customization": {
                "compactToolbar": True,
                "hideRightMenu": True,
                "toolbarNoTabs": True,
                "chat": False,
                "comments": False,
                "help": False,
                "about": False,
            },
        },
    }
    _oo_url, oo_secreto = await _oo_cfg(request)
    config["token"] = jwt.encode(config, oo_secreto, algorithm="HS256")
    return config


@router.get("/vista-previa-local/archivo")
async def archivo_vista_previa(request: Request, token: str = Query(...)):
    """Lo pide OnlyOffice (sin cookie): se autoriza con el vale firmado."""
    try:
        datos_vale = jwt.decode(token, _DOWNLOAD_SECRET, algorithms=["HS256"])
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Vale no válido o vencido")
    if "vpl" not in datos_vale:
        raise HTTPException(status_code=401, detail="Vale no válido")
    guardado = await request.app.state.redis.get(_clave(datos_vale["vpl"]))
    if not guardado:
        raise HTTPException(status_code=404, detail="La vista previa caducó")
    if isinstance(guardado, (bytes, bytearray)):
        guardado = guardado.decode("ascii")
    nombre = datos_vale.get("fn") or "documento"
    tipo, _ = mimetypes.guess_type(nombre)
    return Response(
        content=base64.b64decode(guardado),
        media_type=tipo or "application/octet-stream",
        headers={"Content-Disposition": _content_disposition(nombre, "inline")},
    )
