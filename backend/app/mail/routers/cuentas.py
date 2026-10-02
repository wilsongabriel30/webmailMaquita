"""Cuentas que la persona puede usar en esta sesión: la suya y las delegadas.

GET /api/mail/cuentas -> {"cuentas": [{email, nombre, propia, puede_enviar, alias: [...], carpetas: [...]}]}

Las carpetas de cada cuenta delegada llegan con nombre virtual `Compartidos/<cuenta>/<carpeta>`;
el resto de la API (mensajes, mover, marcar...) acepta esos nombres y trabaja sobre el buzón
real con el usuario maestro (ver services/cuentas_delegadas.py).
"""

import logging
import re

from fastapi import APIRouter, Depends, Request

from app.auth.dependencies import get_current_user
from app.config import get_settings
from app.core.session import get_imap_login_user, get_user_password
from app.mail.clients.imap_client import _decode_lines
from app.mail.clients.imap_pool import get_pooled_imap
from app.mail.services.alias_propios import alias_de
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
    propia = await db.fetchrow(
        "SELECT COALESCE(name, '') AS nombre FROM mailbox WHERE username = $1", username
    )
    cuentas = [
        {
            "email": username,
            "nombre": (propia["nombre"] if propia else "") or "",
            "propia": True,
            "puede_enviar": True,
            "alias": await alias_de(db, username),
            "carpetas": [],  # las propias ya las da /api/mail/folders
        }
    ]
    for c in await cuentas_de(db, username):
        carpetas = []
        try:
            usuario, clave = credenciales_maestras(c["email"], settings)
            async with get_pooled_imap(usuario, clave) as imap:
                for f in await get_folders(imap):
                    carpetas.append(
                        {
                            "name": carpeta_virtual(c["email"], f["name"]),
                            "nombre_real": f["name"],
                            "delimiter": f.get("delimiter", "."),
                            "flags": f.get("flags", []),
                            "type": f.get("type", "folder"),
                            "unseen": f.get("unseen", 0),
                            "cuenta": c["email"],
                        }
                    )
        except Exception as e:  # una cuenta caída no debe tumbar la lista
            log.warning(
                "cuentas: no se pudo abrir %s para %s: %s", c["email"], username, e
            )
        cuentas.append(
            {
                **c,
                "propia": False,
                "alias": await alias_de(db, c["email"]),
                "carpetas": carpetas,
            }
        )
    return {"cuentas": cuentas}


@router.get("/cuentas/no-leidos")
async def no_leidos(request: Request, username: str = Depends(get_current_user)):
    """No leídos de la bandeja de entrada de cada cuenta (la propia y las asignadas).

    Para la barra de cuentas: un solo STATUS por cuenta, en lugar de recorrer todas sus
    carpetas como `/cuentas`. Una cuenta que no abre devuelve null y no tumba la lista.
    """
    db = request.app.state.db_pool
    settings = get_settings()
    objetivos = [
        (
            username,
            await get_imap_login_user(request, username),
            await get_user_password(request, username),
        )
    ]
    for c in await cuentas_de(db, username):
        objetivos.append((c["email"], *credenciales_maestras(c["email"], settings)))
    resultado: dict[str, int | None] = {}
    for email, usuario, clave in objetivos:
        resultado[email] = None
        try:
            async with get_pooled_imap(usuario, clave) as imap:
                resp = await imap.status("INBOX", "(UNSEEN)")
                if resp.result == "OK":
                    for linea in _decode_lines(resp.lines):
                        m = re.search(r"UNSEEN\s+(\d+)", linea)
                        if m:
                            resultado[email] = int(m.group(1))
        except Exception as e:
            log.warning(
                "no-leidos: no se pudo abrir %s para %s: %s", email, username, e
            )
    return {"no_leidos": resultado}
