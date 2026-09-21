"""Lo que la interfaz necesita saber de la búsqueda para no acotar de más.

Hoy una sola cosa: si la cuenta tiene índice de texto completo. Con él, buscar dentro del texto
en todo el buzón son segundos y el panel de búsqueda avanzada no acota a tres meses.
"""

from fastapi import APIRouter, Depends

from app.auth.dependencies import get_current_user
from app.mail.services.indice_texto import cuenta_indexada

router = APIRouter(prefix="/api/mail/search", tags=["mail-search"])


@router.get("/capacidades")
async def capacidades_de_busqueda(username: str = Depends(get_current_user)):
    return {"indice_texto": cuenta_indexada(username)}
