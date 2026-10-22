"""Lo que la interfaz necesita saber de la búsqueda para no acotar de más.

- `indice_texto`: la cuenta tiene índice de texto completo. Con él, buscar dentro del texto en todo
  el buzón son segundos y el panel de búsqueda avanzada no acota a tres meses.
- `adjuntos`: el índice incluye el texto de los adjuntos (PDF, Office, comprimidos…), así que la
  casilla «buscar también dentro del texto» busca también en ellos.
"""

from fastapi import APIRouter, Depends

from app.auth.dependencies import get_current_user
from app.mail.services.indice_texto import adjuntos_indexados, cuenta_indexada

router = APIRouter(prefix="/api/mail/search", tags=["mail-search"])


@router.get("/capacidades")
async def capacidades_de_busqueda(username: str = Depends(get_current_user)):
    con_indice = cuenta_indexada(username)
    return {"indice_texto": con_indice, "adjuntos": con_indice and adjuntos_indexados()}
