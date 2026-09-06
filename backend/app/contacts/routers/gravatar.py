"""Avatares de contacto — resueltos en casa, sin consultar a terceros.

Antes este endpoint calculaba el MD5 del correo consultado y se lo enviaba a
gravatar.com para saber si tenia foto. Eso filtraba a un tercero la libreta de
direcciones: no solo el correo propio, sino el de cualquier persona que se
escribiera en el buscador, junto con la IP del servidor y el momento de la
consulta. El MD5 de un correo no es anonimo; se revierte con un diccionario.

Ahora no sale ninguna peticion de la organizacion: se responde que no hay foto
externa y la interfaz dibuja el avatar de iniciales que ya tenia (componente
`Avatar`). Se mantiene la ruta y la forma de la respuesta para no romper a los
clientes que ya la llaman. [T4]
"""

import logging

from fastapi import APIRouter, Depends, Query, Request

from app.auth.dependencies import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/contacts", tags=["contacts"])


@router.get("/gravatar")
async def check_gravatar(
    request: Request,
    email: str = Query(..., description="Correo del contacto"),
    username: str = Depends(get_current_user),
):
    """Responde siempre que no hay avatar externo; el avatar se dibuja local."""
    return {"has_avatar": False, "fuente": "local"}
