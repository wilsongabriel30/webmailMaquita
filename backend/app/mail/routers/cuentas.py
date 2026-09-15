"""Cuentas que la persona puede usar en esta sesión: la suya y las delegadas.

GET /api/mail/cuentas -> {"cuentas": [{email, nombre, propia, puede_enviar, carpetas: [...]}]}

Las carpetas de cada cuenta delegada llegan con nombre virtual `Compartidos/<cuenta>/<carpeta>`;
el resto de la API (mensajes, mover, marcar...) acepta esos nombres y trabaja sobre el buzón
real con el usuario maestro (ver services/cuentas_delegadas.py).
"""

import logging

from fastapi import APIRouter, Depends, Request

from app.auth.dependencies import get_current_user
from app.config import get_settings
from app.mail.clients.imap_pool import get_pooled_imap
from app.mail.services.cuentas_delegadas import (
    carpeta_virtual,
    credenciales_maestras,
    cuentas_de,
)
from app.mail.services.folder_service import get_folders

router = APIRouter(prefix="/api/mail", tags=["mail-cuentas"])
log = logging.getLogger(__name__)


@router.get("/cuentas")
async def listar_cuentas(request: Request, username: str = Depends(get_current_user)):
    db = request.app.state.db_pool
    settings = get_settings()
    propia = await db.fetchrow("SELECT COALESCE(name, '') AS nombre FROM mailbox WHERE username = $1", username)
    cuentas = [{
        "email": username,
        "nombre": (propia["nombre"] if propia else "") or "",
        "propia": True,
        "puede_enviar": True,
        "carpetas": [],  # las propias ya las da /api/mail/folders
    }]
    for c in await cuentas_de(db, username):
        carpetas = []
        try:
            usuario, clave = credenciales_maestras(c["email"], settings)
            async with get_pooled_imap(usuario, clave) as imap:
                for f in await get_folders(imap):
                    carpetas.append({
                        "name": carpeta_virtual(c["email"], f["name"]),
                        "nombre_real": f["name"],
                        "delimiter": f.get("delimiter", "."),
                        "flags": f.get("flags", []),
                        "type": f.get("type", "folder"),
                        "unseen": f.get("unseen", 0),
                        "cuenta": c["email"],
                    })
        except Exception as e:  # una cuenta caída no debe tumbar la lista
            log.warning("cuentas: no se pudo abrir %s para %s: %s", c["email"], username, e)
        cuentas.append({**c, "propia": False, "carpetas": carpetas})
    return {"cuentas": cuentas}
