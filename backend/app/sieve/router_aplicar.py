"""Endpoint: aplicar una regla de correo a los correos que ya están en una carpeta (10/11/2026).

Va aparte de `router.py` (que ya es grande): aquí solo entra la petición, se abre IMAP con la
sesión de la persona y se delega en `aplicar_existentes`.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field

from app.auth.dependencies import get_current_user
from app.core.session import get_imap_login_user, get_user_password
from app.mail.clients.imap_client import get_imap_connection
from app.sieve.aplicar_existentes import aplicar_regla_existentes
from app.sieve.modelos import FilterRule

logger = logging.getLogger("sieve.aplicar")

router = APIRouter(prefix="/api/sieve", tags=["sieve"])


class AplicarPeticion(BaseModel):
    rule: FilterRule
    folder: str = Field("INBOX", min_length=1, max_length=255)


@router.post("/filters/aplicar")
async def aplicar_regla_a_existentes(
    request: Request,
    body: AplicarPeticion,
    username: str = Depends(get_current_user),
):
    """Aplica la regla a los correos que ya están en `folder` (por defecto la Bandeja de entrada)."""
    if not body.rule.conditions or not body.rule.actions:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="La regla necesita al menos una condición y una acción",
        )
    password: str = await get_user_password(request, username)
    login_user = await get_imap_login_user(request, username)
    imap = await get_imap_connection(login_user, password)
    try:
        resultado = await aplicar_regla_existentes(imap, body.rule, body.folder)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    finally:
        try:
            await imap.logout()
        except Exception:
            pass
    logger.info(
        "Regla «%s» aplicada a %s de %s: %s coinciden, %s movidos, %s copiados, %s a la papelera",
        body.rule.name,
        body.folder,
        username,
        resultado["coinciden"],
        resultado["movidos"],
        resultado["copiados"],
        resultado["papelera"],
    )
    return resultado
