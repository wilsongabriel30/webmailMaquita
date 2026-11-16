"""Lo que la interfaz necesita saber de la búsqueda para no acotar de más ni ofrecer de más.

- `indice_texto`: la cuenta tiene índice de texto completo. Con él, buscar dentro del texto en todo
  el buzón son segundos y el panel de búsqueda avanzada no acota a tres meses.
- `adjuntos`: el índice incluye el texto de los adjuntos (PDF, Office, comprimidos…), así que la
  casilla «buscar también dentro del texto» busca también en ellos.
- `todas_las_carpetas`: el servidor tiene el buzón virtual `Virtual.Todo`. Sin él, la interfaz no
  ofrece «Todas las carpetas» y busca siempre en la carpeta abierta (services/buzon_virtual.py).
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, Request

from app.auth.dependencies import get_current_user
from app.core.session import get_imap_login_user, get_user_password
from app.mail.clients.imap_pool import get_pooled_imap
from app.mail.services import buzon_virtual
from app.mail.services.indice_texto import adjuntos_indexados, cuenta_indexada

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/mail/search", tags=["mail-search"])


async def _hay_buzon_virtual(request: Request, username: str) -> bool:
    """Si el servidor de correo no responde, cuenta como «no hay»."""
    try:
        redis = getattr(request.app.state, "redis", None)
        password = await get_user_password(request, username)
        login_user = await get_imap_login_user(request, username)
        async with get_pooled_imap(login_user, password) as imap:
            return await buzon_virtual.existe(imap, redis, username)
    except HTTPException:
        raise  # sesión vencida: que la interfaz la renueve como en cualquier otra ruta
    except Exception as e:  # noqa: BLE001
        log.warning("capacidades: no se pudo consultar el buzón virtual (%s)", e)
        return False


@router.get("/capacidades")
async def capacidades_de_busqueda(
    request: Request, username: str = Depends(get_current_user)
):
    con_indice = cuenta_indexada(username)
    return {
        "indice_texto": con_indice,
        "adjuntos": con_indice and adjuntos_indexados(),
        "todas_las_carpetas": await _hay_buzon_virtual(request, username),
    }
