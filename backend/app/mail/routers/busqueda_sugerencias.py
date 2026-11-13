"""«¿Quiso decir…?» para la búsqueda del correo (ver services/quiso_decir.py)."""

from fastapi import APIRouter, Depends, Request

from app.auth.dependencies import get_current_user
from app.mail.services.quiso_decir import sugerencias

router = APIRouter(prefix="/api/mail/search", tags=["mail-search"])


@router.get("/sugerencias")
async def sugerencias_de_busqueda(
    request: Request, q: str = "", username: str = Depends(get_current_user)
):
    pool = getattr(request.app.state, "db_pool", None)
    return {"sugerencias": await sugerencias(pool, username, q[:200])}
