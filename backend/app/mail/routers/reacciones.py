"""Reacciones a un correo: consultar y poner/cambiar/quitar (app/mail/services/reacciones.py)."""

from __future__ import annotations

import asyncio
import email
import json
import logging
from email.header import decode_header, make_header

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from app.auth.dependencies import get_current_user
from app.core.session import get_imap_login_user, get_user_password
from app.federacion import reacciones_cliente
from app.mail.clients.imap_client import _quote_folder
from app.mail.clients.imap_pool import get_pooled_imap
from app.mail.services import reacciones

logger = logging.getLogger("maquita.webmail.reacciones")

router = APIRouter(prefix="/api/mail/reacciones", tags=["mail-reacciones"])

_CAMPOS = "(BODY.PEEK[HEADER.FIELDS (MESSAGE-ID FROM TO CC SUBJECT)])"
# Avisos a otros servidores en curso (se guardan para que no se pierdan a medias).
_TAREAS: set = set()


class Reaccion(BaseModel):
    emoji: str


async def _cabeceras(request: Request, username: str, folder: str, uid: int):
    """Cabeceras del correo leídas con la sesión de la persona: solo reacciona quien TIENE el correo."""
    password = await get_user_password(request, username)
    login_user = await get_imap_login_user(request, username)
    async with get_pooled_imap(login_user, password) as imap:
        resp = await imap.select(_quote_folder(folder))
        if resp.result != "OK":
            raise HTTPException(status_code=404, detail="Carpeta no encontrada")
        fetch = await imap.uid("fetch", str(uid), _CAMPOS)
        if fetch.result != "OK":
            raise HTTPException(status_code=404, detail="Correo no encontrado")
    bloque = b""
    for linea in fetch.lines:
        if (
            isinstance(linea, (bytes, bytearray))
            and b":" in linea
            and len(linea) > len(bloque)
        ):
            if not bytes(linea[:1]).isdigit():
                bloque = bytes(linea)
    msg = email.message_from_bytes(bloque)
    message_id = " ".join(str(msg.get("Message-ID", "")).split())
    if not message_id:
        raise HTTPException(status_code=409, detail="Este correo no admite reacciones")
    return msg, message_id[:500]


def _asunto(msg) -> str:
    try:
        return str(make_header(decode_header(str(msg.get("Subject", ""))))).strip()[
            :120
        ]
    except Exception:
        return str(msg.get("Subject", ""))[:120]


@router.get("/{folder}/{uid}")
async def ver(
    folder: str, uid: int, request: Request, username: str = Depends(get_current_user)
):
    _msg, message_id = await _cabeceras(request, username, folder, uid)
    db = request.app.state.db_pool
    return {
        "message_id": message_id,
        "catalogo": list(reacciones.CATALOGO),
        "reacciones": await reacciones.resumen(db, message_id, username),
    }


@router.post("/{folder}/{uid}")
async def reaccionar(
    folder: str,
    uid: int,
    body: Reaccion,
    request: Request,
    username: str = Depends(get_current_user),
):
    if not reacciones.emoji_valido(body.emoji):
        raise HTTPException(status_code=400, detail="Reacción no válida")
    msg, message_id = await _cabeceras(request, username, folder, uid)
    db = request.app.state.db_pool
    estado = await reacciones.alternar(db, message_id, username, body.emoji)

    # Aviso en vivo a las demás personas de este servidor que tienen el correo (sin generar correos).
    try:
        autor, todos = reacciones.participantes(msg)
        aviso = {
            "type": "reaccion_correo",
            "message_id": message_id,
            "emoji": body.emoji,
            "estado": estado,
            "de": await reacciones.nombre_de(db, username),
            "asunto": _asunto(msg),
        }
        redis = request.app.state.redis
        locales = await reacciones.cuentas_locales(db, todos)
        for cuenta in locales:
            if cuenta == username:
                continue
            await redis.publish(
                f"ws:user:{cuenta}",
                json.dumps({**aviso, "para_autor": cuenta == autor}),
            )
        # Quienes tienen el correo en OTRO servidor de la suite: se avisa sin frenar la respuesta.
        externos = todos - set(locales) - {username}
        if externos:
            tarea = asyncio.create_task(
                reacciones_cliente.avisar_otros_servidores(
                    redis,
                    message_id,
                    username,
                    aviso["de"],
                    None if estado == "quitada" else body.emoji,
                    externos,
                )
            )
            _TAREAS.add(tarea)
            tarea.add_done_callback(_TAREAS.discard)
    except Exception as exc:
        logger.warning("reacciones: no se pudo avisar (%s): %s", message_id, exc)

    return {
        "estado": estado,
        "message_id": message_id,
        "reacciones": await reacciones.resumen(db, message_id, username),
    }
