"""Lado que recibe: otra instalación avisa de que una persona suya reaccionó a un correo.

Se acepta solo si (1) alguno de los destinatarios indicados es un buzón de este servidor y tiene
ese correo, (2) quien reacciona figura en el De/Para/CC de la copia guardada aquí y (3) el
servidor del dominio de esa persona confirma el aviso. Cualquier fallo responde «ignorada».
"""

from __future__ import annotations

import asyncio
import json

from app.federacion import reacciones_protocolo as protocolo
from app.federacion import recuperacion_mensaje as mensaje
from app.federacion import red
from app.mail.routers import recall
from app.mail.services import reacciones

NO = {"estado": "ignorada"}


async def _confirmado(dominio: str, aviso: protocolo.Aviso) -> bool:
    for host in await red.servidores_de(dominio):
        r = await red.llamar(host, "POST", protocolo.RUTA_CONFIRMAR, aviso.model_dump())
        if r and r.get("confirmado") is True:
            return True
    return False


async def atender(request, aviso: protocolo.Aviso) -> dict:
    usuario = aviso.usuario.strip().lower()
    message_id = " ".join(aviso.message_id.split())
    if not recall._validate_email(usuario) or not recall._validate_message_id(
        message_id
    ):
        return NO
    if aviso.emoji is not None and not reacciones.emoji_valido(aviso.emoji):
        return NO

    db = request.app.state.db_pool
    filas = await db.fetch("SELECT domain FROM domain WHERE active = true")
    dominios = [f["domain"].lower() for f in filas if f["domain"] != "ALL"]
    dominio_usuario = usuario.rsplit("@", 1)[-1]
    if dominio_usuario in dominios:
        return NO  # las personas de este servidor reaccionan por la vía normal

    candidatos = {
        d.strip().lower()
        for d in aviso.destinatarios
        if recall._validate_email(d.strip().lower())
        and recall._is_local_domain(d.strip().lower(), dominios)
    }
    msg = None
    for cuenta in await reacciones.cuentas_locales(db, candidatos):
        msg = await asyncio.to_thread(mensaje.cabeceras, cuenta, message_id)
        if msg is not None:
            break
    if msg is None:
        return NO
    autor, participantes = reacciones.participantes(msg)
    if usuario not in participantes:
        return NO
    if not await _confirmado(dominio_usuario, aviso):
        return NO

    estado = await reacciones.fijar(
        db, message_id, usuario, aviso.emoji, aviso.nombre.strip()
    )
    try:
        evento = {
            "type": "reaccion_correo",
            "message_id": message_id,
            "emoji": aviso.emoji,
            "estado": estado,
            "de": aviso.nombre.strip() or usuario,
            "asunto": str(msg.get("Subject", ""))[:120],
        }
        redis = request.app.state.redis
        for cuenta in await reacciones.cuentas_locales(db, participantes):
            await redis.publish(
                f"ws:user:{cuenta}",
                json.dumps({**evento, "para_autor": cuenta == autor}),
            )
    except Exception as exc:
        red.logger.warning(
            "federación: no se pudo avisar en vivo de la reacción: %s", exc
        )
    return {"estado": "recibida"}
