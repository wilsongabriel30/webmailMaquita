"""Imágenes de las firmas guardadas en el servidor (`/api/firmas/imagen/<hash>.png`).

Las usa el webmail para mostrar la firma en el editor y en Configuración. En el correo que sale
no viajan como enlace sino incrustadas (`cid:`), así que el destinatario no llama aquí nunca.
"""

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse

from app.auth.dependencies import get_current_user
from app.mail import firmas_imagenes

router = APIRouter(prefix="/api/firmas", tags=["firmas"])


@router.get("/imagen/{nombre}")
async def imagen(nombre: str, _usuario: str = Depends(get_current_user)):
    ruta = firmas_imagenes.ruta_local(nombre)
    if not ruta:
        raise HTTPException(status_code=404, detail="Imagen no encontrada")
    return FileResponse(
        ruta,
        media_type="image/png",
        headers={"Cache-Control": "private, max-age=86400"},
    )
