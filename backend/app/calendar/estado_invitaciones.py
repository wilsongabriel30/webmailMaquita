"""Estado de entrega de las invitaciones del calendario.

Cada invitación sale con un Message-ID propio. El servidor local casi siempre la acepta, pero el
destino puede rechazarla segundos después (dirección inexistente, IP bloqueada, buzón lleno). Esos
rechazos quedan en `mail_trace` (lo llena el lector del registro de Postfix) con el mismo Message-ID,
y el calendario los consulta aquí para avisar a quien envió.
"""

from __future__ import annotations

import smtplib
from email.utils import make_msgid

# Saltos internos que no son la entrega final (el filtro reinyecta el correo).
_RELES_INTERNOS = ("maquita-filter",)

_MOTIVOS_DSN = {
    "5.1.1": "la dirección no existe; revisa que esté bien escrita",
    "5.1.0": "la dirección no existe; revisa que esté bien escrita",
    "5.1.2": "el dominio del destinatario no existe",
    "5.2.1": "el buzón del destinatario está desactivado",
    "5.2.2": "el buzón del destinatario está lleno",
    "5.4.1": "el servidor del destinatario no acepta correo para esa dirección",
    "5.7.1": "el servidor del destinatario rechazó nuestro correo (bloqueo o política del destino)",
}


def nuevo_message_id(remitente: str) -> str:
    dominio = remitente.rsplit("@", 1)[-1] if "@" in remitente else None
    return make_msgid(idstring="invitacion", domain=dominio)


def explicar_error_envio(error: Exception) -> str:
    """Texto claro para un fallo al entregar la invitación a nuestro propio servidor."""
    if isinstance(error, smtplib.SMTPAuthenticationError):
        return "el servidor de correo no aceptó tu sesión; cierra sesión, vuelve a entrar y reenvía"
    if isinstance(error, smtplib.SMTPRecipientsRefused):
        return "el servidor de correo rechazó la dirección del destinatario"
    # smtplib.SMTPException hereda de OSError: solo los OSError que no son respuestas SMTP son de conexión.
    if isinstance(
        error, (smtplib.SMTPConnectError, smtplib.SMTPServerDisconnected)
    ) or (isinstance(error, OSError) and not isinstance(error, smtplib.SMTPException)):
        return "no se pudo conectar con el servidor de correo"
    return "el servidor de correo no aceptó el envío"


def _motivo(estado: str, dsn: str | None) -> str:
    if estado == "en_espera":
        return (
            "el servidor del destinatario no responde por ahora; se seguirá intentando"
        )
    dsn = dsn or ""
    if dsn in _MOTIVOS_DSN:
        return _MOTIVOS_DSN[dsn]
    if dsn.startswith("5.1"):
        return _MOTIVOS_DSN["5.1.1"]
    return "el servidor del destinatario la rechazó"


async def consultar(db, remitente: str, message_ids: list[str]) -> list[dict]:
    """Estado final por destinatario de las invitaciones enviadas por `remitente`.

    Devuelve solo lo que ya tiene resultado: «entregado», «rechazado» o «en_espera». Lo que aún
    no aparece en el registro no se devuelve (sigue en camino)."""
    ids = [m.strip().strip("<>") for m in message_ids if m and m.strip()][:50]
    if not ids:
        return []
    filas = await db.fetch(
        """SELECT DISTINCT ON (message_id, lower(recipient))
                  message_id, lower(recipient) AS destinatario, status, dsn
             FROM mail_trace
            WHERE message_id = ANY($1::text[])
              AND lower(sender) = lower($2)
              AND created_at > now() - interval '3 days'
              AND coalesce(relay, '') NOT LIKE ALL($3::text[])
            ORDER BY message_id, lower(recipient), created_at DESC, id DESC""",
        ids,
        remitente,
        [r + "%" for r in _RELES_INTERNOS],
    )
    resultado = []
    for f in filas:
        if f["status"] == "sent":
            estado = "entregado"
        elif f["status"] == "deferred":
            estado = "en_espera"
        elif f["status"] in ("bounced", "expired", "rejected"):
            estado = "rechazado"
        else:
            continue
        item = {
            "message_id": "<" + f["message_id"] + ">",
            "email": f["destinatario"],
            "estado": estado,
            "dsn": f["dsn"],
        }
        if estado != "entregado":
            item["detalle"] = _motivo(estado, f["dsn"])
        resultado.append(item)
    return resultado
