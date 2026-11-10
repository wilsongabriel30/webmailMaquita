"""Recuperación de correos enviados: lo que pasa DESPUÉS de borrar el correo del buzón del destinatario.

Incidente 09/11/2026: `doveadm expunge` quitaba el correo del buzón, pero el destinatario lo seguía
viendo en su lista hasta 5 minutos (caché Redis de UIDs sin invalidar y sin aviso por WebSocket), y
la auditoría se escribía contra una columna inexistente (`username`) con el error silenciado.

Aquí viven las piezas que no dependen de doveadm ni de FastAPI, para poder probarlas sin servidor:
- qué carpetas del destinatario hay que invalidar y cómo avisarle;
- el registro en `audit_log` con las columnas reales (`admin_user, action, target, details, ip_address`);
- la decisión de mover el correo del remitente de «Enviados» a «Borradores» y el movimiento en sí.
"""

import json
import logging
from datetime import datetime, timezone

from app.mail.services.cache_uids import invalidar_uids

logger = logging.getLogger(__name__)

ACCION_AUDITORIA = "message_recall"
CARPETA_ENVIADOS = "Sent"
CARPETA_BORRADORES = "Drafts"
# Palabra clave IMAP que marca el borrador que nació de una recuperación.
KEYWORD_RECUPERADO = "$Recuperado"
TIPO_EVENTO_WS = "correo_recuperado"
# Estados que NO cuentan como «destinatario local recuperado».
ESTADOS_EXTERNOS = ("external", "external_request_sent")


def carpetas_a_invalidar(carpetas: list[str] | tuple[str, ...] | None) -> list[str]:
    """INBOX siempre, más las carpetas reales donde estaba el mensaje (sin repetidos, en orden)."""
    resultado = ["INBOX"]
    for carpeta in carpetas or ():
        carpeta = (carpeta or "").strip()
        if carpeta and carpeta not in resultado:
            resultado.append(carpeta)
    return resultado


async def avisar_destinatario(redis, destinatario: str, carpetas: list[str]) -> bool:
    """Publica en el canal WebSocket del destinatario (`ws:user:<correo>`) que su lista cambió.

    Es el mismo canal Redis por el que la entrega de correo nuevo publica `new_mail`
    (app/websocket/router.py); el suscriptor de cada worker lo reparte a las conexiones abiertas.
    No se reutiliza el tipo `new_mail` porque ese muestra aviso y sonido de «correo nuevo».
    """
    if redis is None:
        return False
    try:
        await redis.publish(
            f"ws:user:{destinatario}",
            json.dumps({"type": TIPO_EVENTO_WS, "folders": carpetas}),
        )
        return True
    except Exception as exc:
        logger.warning(
            "recuperación: no se pudo avisar a %s por WebSocket: %s", destinatario, exc
        )
        return False


async def tras_expunge(redis, destinatario: str, carpetas_mensaje) -> list[str]:
    """Tras borrar el correo del buzón del destinatario: invalidar su caché y avisarle al instante."""
    carpetas = carpetas_a_invalidar(carpetas_mensaje)
    try:
        await invalidar_uids(redis, destinatario, *carpetas)
    except Exception as exc:
        logger.warning(
            "recuperación: no se pudo invalidar la caché de %s: %s", destinatario, exc
        )
    await avisar_destinatario(redis, destinatario, carpetas)
    return carpetas


def decidir_mover_a_borradores(resultados: list[dict]) -> bool:
    """¿Se mueve el correo del remitente de «Enviados» a «Borradores»?

    Sí, solo cuando TODOS los destinatarios son locales y la recuperación les salió bien
    (al menos uno `recalled`; se tolera `not_found`, que es un buzón donde ya no estaba).
    Con destinatarios externos (solo solicitud), errores o nada recuperado, se queda en Enviados.
    """
    if not resultados:
        return False
    hubo_recuperado = False
    for r in resultados:
        estado = r.get("status")
        if estado in ESTADOS_EXTERNOS:
            return False
        if estado == "recalled":
            hubo_recuperado = True
        elif estado != "not_found":
            return False
    return hubo_recuperado


async def registrar_auditoria(
    db,
    remitente: str,
    message_id: str,
    resultados: list[dict],
    ip: str | None = None,
    movido_a_borradores: bool = False,
) -> bool:
    """Deja rastro de la recuperación en `audit_log` con las columnas reales de la tabla.

    `target` es el Message-ID (la columna admite 255 caracteres) y `details` lleva remitente,
    destinatarios, resultado por destinatario y si cada uno ya lo había leído.
    Un fallo aquí no rompe la recuperación, pero SÍ queda en el registro del servidor.
    """
    detalles = {
        "remitente": remitente,
        "message_id": message_id,
        "destinatarios": [
            {
                "destinatario": r.get("recipient"),
                "resultado": r.get("status"),
                "leido": r.get("was_read"),
                "carpetas": r.get("folders") or [],
            }
            for r in resultados
        ],
        "movido_a_borradores": movido_a_borradores,
    }
    try:
        await db.execute(
            """INSERT INTO audit_log (admin_user, action, target, details, ip_address)
               VALUES ($1, $2, $3, $4::jsonb, $5::inet)""",
            remitente,
            ACCION_AUDITORIA,
            (message_id or "")[:255],
            json.dumps(detalles, ensure_ascii=False),
            ip,
        )
        return True
    except Exception as exc:
        logger.error(
            "recuperación: no se pudo registrar en audit_log (remitente=%s, message_id=%s): %s",
            remitente,
            message_id,
            exc,
        )
        return False


def _texto(linea) -> str:
    return (
        linea.decode("utf-8", "replace")
        if isinstance(linea, (bytes, bytearray))
        else str(linea)
    )


def _uids_de_busqueda(lineas) -> list[str]:
    """Saca los UIDs de la respuesta a UID SEARCH (ignora la línea «SEARCH completed»)."""
    uids: list[str] = []
    for linea in lineas or ():
        texto = _texto(linea).strip()
        if not texto or texto.lower().endswith("completed."):
            continue
        uids.extend(p for p in texto.split() if p.isdigit())
    return uids


async def mover_a_borradores(imap, message_id: str) -> dict:
    """Mueve el correo del remitente de «Enviados» a «Borradores» marcándolo como borrador recuperado.

    Devuelve {"movido": bool, "uid": str | None}. Si no está en Enviados o el servidor falla,
    no se mueve nada (el correo sigue en Enviados) y se informa.
    """
    from app.mail.clients.imap_acciones import mover_uids
    from app.mail.clients.imap_client import _quote_folder

    try:
        resp = await imap.select(_quote_folder(CARPETA_ENVIADOS))
        if resp.result != "OK":
            return {"movido": False, "uid": None, "motivo": "No se pudo abrir Enviados"}
        busqueda = await imap.uid_search("HEADER", "Message-ID", f'"{message_id}"')
        if busqueda.result != "OK":
            return {
                "movido": False,
                "uid": None,
                "motivo": "Búsqueda en Enviados fallida",
            }
        uids = _uids_de_busqueda(busqueda.lines)
        if not uids:
            return {"movido": False, "uid": None, "motivo": "No está en Enviados"}
        uid = uids[-1]
        # \Draft para que el redactor lo abra como borrador; $Recuperado para mostrar «Mensaje recuperado».
        await imap.uid("store", uid, "+FLAGS", f"(\\Draft {KEYWORD_RECUPERADO})")
        if not await mover_uids(imap, uid, _quote_folder(CARPETA_BORRADORES)):
            return {
                "movido": False,
                "uid": uid,
                "motivo": "No se pudo mover a Borradores",
            }
        return {
            "movido": True,
            "uid": uid,
            "fecha": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as exc:
        logger.warning(
            "recuperación: no se pudo mover %s a Borradores: %s", message_id, exc
        )
        return {"movido": False, "uid": None, "motivo": str(exc)}
