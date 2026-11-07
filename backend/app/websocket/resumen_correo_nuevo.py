"""Remitente y asunto del correo nuevo para los avisos (06/11/2026).

Antes los avisos decían solo «Tienes 2 correos nuevos» y nadie sabía de quién ni de qué. Ahora:
- un correo:   título = quien lo envía, texto = el asunto;
- varios:      título = «N correos nuevos», texto = «Remitente: asunto» del más reciente.
Se lee solo la cabecera con BODY.PEEK (el correo NO queda marcado como leído).
"""

import email
from email.header import decode_header, make_header
from email.utils import parseaddr

_LARGO = 120


def _texto(valor: str) -> str:
    try:
        valor = str(make_header(decode_header(valor or "")))
    except Exception:
        pass
    valor = " ".join(valor.split())
    return valor if len(valor) <= _LARGO else valor[: _LARGO - 1] + "…"


async def resumen_correo(imap, uid) -> dict:
    """{'de': 'Carlos Ponce', 'asunto': '…'} del UID dado (INBOX ya seleccionado). {} si falla."""
    if not uid:
        return {}
    try:
        r = await imap.uid(
            "fetch", str(uid), "(BODY.PEEK[HEADER.FIELDS (FROM SUBJECT)])"
        )
        if getattr(r, "result", "") != "OK":
            return {}
        crudo = b"".join(bytes(l) for l in (r.lines or []) if isinstance(l, bytearray))
        if not crudo:
            return {}
        msg = email.message_from_bytes(crudo)
        nombre, direccion = parseaddr(_texto(msg.get("From", "")))
        return {
            "de": _texto(nombre or direccion),
            "asunto": _texto(msg.get("Subject", "")) or "(sin asunto)",
        }
    except Exception:
        return {}


def textos_aviso(nuevos: int, resumen: dict | None) -> tuple[str, str]:
    """(título, texto) del aviso. Sin resumen, el texto de siempre."""
    de = (resumen or {}).get("de")
    asunto = (resumen or {}).get("asunto") or "(sin asunto)"
    # El nombre va también en el texto: hay pantallas que muestran solo el texto (06/11/2026).
    if de and nuevos <= 1:
        return de, "De: %s\nAsunto: %s" % (de, asunto)
    if de:
        return "%d correos nuevos" % nuevos, "De: %s\nAsunto: %s" % (de, asunto)
    return "Correo nuevo", (
        "Tienes 1 correo nuevo" if nuevos == 1 else "Tienes %d correos nuevos" % nuevos
    )


def textos_aviso_cuenta(
    nuevos: int, resumen: dict | None, cuenta: str
) -> tuple[str, str]:
    """Cuentas delegadas (06/11/2026): lo mismo, diciendo además a qué cuenta llegó."""
    de = (resumen or {}).get("de")
    asunto = (resumen or {}).get("asunto") or "(sin asunto)"
    if de and nuevos <= 1:
        return de, "De: %s\nAsunto: %s\nCuenta: %s" % (de, asunto, cuenta)
    if de:
        return "%d correos nuevos en %s" % (nuevos, cuenta), "De: %s\nAsunto: %s" % (
            de,
            asunto,
        )
    return "Correo nuevo", (
        "Tienes 1 correo nuevo en %s" % cuenta
        if nuevos == 1
        else "Tienes %d correos nuevos en %s" % (nuevos, cuenta)
    )
