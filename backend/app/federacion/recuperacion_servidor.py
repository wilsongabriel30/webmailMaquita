"""Lado del destinatario: atender la petición de otro servidor de retirar un correo.

Orden de las comprobaciones (cualquier fallo responde lo mismo, «no_recuperado», para no dar
pistas sobre qué buzones o correos existen):
  1. el destinatario es un buzón de un dominio de este servidor;
  2. el correo está en su buzón y este servidor lo autenticó como del dominio del remitente;
  3. el servidor de ese dominio confirma que emitió la solicitud (devolución de llamada);
  4. sigue dentro del plazo de recuperación de ESTE servidor.
Todo intento confirmado queda en la auditoría.
"""

from __future__ import annotations

import asyncio

from app.federacion import recuperacion_mensaje as mensaje
from app.federacion import recuperacion_protocolo as protocolo
from app.federacion import red
from app.mail.routers import recall
from app.mail.services import plazo_recuperacion, recuperar_correo

NO = {"estado": protocolo.ESTADO_NO_RECUPERADO}


async def _confirmado_por_su_servidor(dominio: str, s: protocolo.Solicitud) -> bool:
    for host in await red.servidores_de(dominio):
        r = await red.llamar(host, "POST", protocolo.RUTA_CONFIRMAR, s.model_dump())
        if r and r.get("confirmado") is True:
            return True
    return False


async def atender(request, s: protocolo.Solicitud, ip: str | None) -> dict:
    destinatario = s.destinatario.strip().lower()
    remitente = s.remitente.strip().lower()
    message_id = s.message_id.strip()
    if not message_id.startswith("<"):
        message_id = f"<{message_id}>"
    if not (
        recall._validate_email(destinatario)
        and recall._validate_email(remitente)
        and recall._validate_message_id(message_id)
    ):
        return NO

    db = request.app.state.db_pool
    filas = await db.fetch("SELECT domain FROM domain WHERE active = true")
    locales = [f["domain"].lower() for f in filas if f["domain"] != "ALL"]
    if not recall._is_local_domain(destinatario, locales):
        return NO

    msg = await asyncio.to_thread(mensaje.cabeceras, destinatario, message_id)
    if msg is None:
        return NO
    dominio = mensaje.dominio_from(msg)
    # Los dominios de este servidor se recuperan por la vía normal, nunca por esta puerta.
    if not dominio or dominio in locales:
        return NO
    if not mensaje.autenticado(msg, dominio, mensaje.identidades_del_servidor()):
        return NO
    if not await _confirmado_por_su_servidor(dominio, s):
        return NO

    info = await asyncio.to_thread(recall._doveadm_fetch_info, destinatario, message_id)
    leido = bool(info.get("was_read"))
    carpetas = list(info.get("folders") or [])
    if plazo_recuperacion.vencido(info.get("received")):
        estado = protocolo.ESTADO_FUERA_DE_PLAZO
    elif await asyncio.to_thread(
        recall._doveadm_expunge, destinatario, message_id, carpetas or None
    ):
        carpetas = await recuperar_correo.tras_expunge(
            request.app.state.redis, destinatario, carpetas
        )
        estado = protocolo.ESTADO_RECUPERADO
    else:
        estado = "error"

    await recuperar_correo.registrar_auditoria(
        db,
        remitente,
        message_id,
        [
            {
                "recipient": destinatario,
                "status": f"{estado} (pedido por otro servidor)",
                "was_read": leido,
                "folders": carpetas,
            }
        ],
        ip=ip,
    )
    if estado == "error":
        return NO
    return {"estado": estado, "leido": leido}
