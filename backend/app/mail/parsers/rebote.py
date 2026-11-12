"""Rebotes explicados en español llano (12/11/2026).

Cuando un correo no se puede entregar, el servidor devuelve un aviso técnico y en inglés
(«452-4.2.2 The recipient's inbox is out of storage space… gsmtp»). Quien lo recibe no lo entiende,
no sabe si el fallo es suyo, del destinatario o nuestro, y no puede reportarlo. Aquí se lee el
informe de entrega que trae el aviso (RFC 3464, `message/delivery-status`) y se traduce a:
qué pasó, de quién es el problema y qué hacer.

Funciones puras: reciben el correo crudo y devuelven un diccionario (o None si no es un rebote).
"""

from __future__ import annotations

import email
import email.policy
import re

# (tipo, patrón sobre «estado + diagnóstico» en minúsculas). El orden importa: lo más concreto primero.
_REGLAS: list[tuple[str, str]] = [
    (
        "buzon_lleno",
        r"\b[45]\.2\.2\b|over ?quota|out of storage|mailbox (is )?full|quota exceeded|insufficient storage|storage space",
    ),
    (
        "muy_grande",
        r"\b5\.2\.3\b|\b5\.3\.4\b|message (size|too (big|large))|size limit|too large",
    ),
    (
        "no_existe",
        r"\b5\.1\.1\b|\b5\.1\.10\b|user unknown|unknown user|no such (user|recipient|mailbox)|does(n't| not) exist|recipient (address )?rejected.*(unknown|not found)|address not found|invalid recipient|mailbox not found|unknown recipient",
    ),
    (
        "dominio_no_existe",
        r"\b5\.1\.2\b|\b5\.4\.4\b|host or domain name not found|domain not found|name service error|nxdomain|no mx|unrouteable|bad destination (system|mailbox)",
    ),
    (
        "cuenta_inactiva",
        r"\b5\.2\.1\b|account (is )?(disabled|inactive|suspended|locked)|mailbox (is )?(disabled|unavailable|inactive)|no longer (available|active)",
    ),
    (
        "nos_rechazan",
        r"\b5\.7\.\d+\b|\bblocked\b|blacklist|blocklist|spamhaus|\bspam\b|reputation|policy|not authorized|access denied|denied|dmarc|\bspf\b|dkim|rejected due to|relay(ing)? (access )?denied",
    ),
    (
        "sin_conexion",
        r"\b4\.4\.\d\b|connection (timed out|refused)|timed out|no route to host|network is unreachable|lost connection|could not connect|try again later|\b4\.\d\.\d\b|temporar",
    ),
]

_TEXTOS: dict[str, tuple[str, str, str]] = {
    # tipo: (título, qué pasó, qué hacer)
    "buzon_lleno": (
        "El buzón de esa persona está lleno",
        "Su correo salió bien de nuestro servidor, pero el buzón del destinatario no tiene espacio y no puede recibir correos de nadie.",
        "Avísele por teléfono o mensaje que libere espacio en su correo y vuelva a enviarlo después. No es un problema de su cuenta ni de nuestro servidor.",
    ),
    "no_existe": (
        "Esa dirección de correo no existe",
        "El servidor del destinatario respondió que no tiene ninguna cuenta con ese nombre.",
        "Revise si la dirección está bien escrita (una letra de más o de menos, un punto, el final después de la @) y vuelva a enviar. Si está bien escrita, pida a la persona su correo actual.",
    ),
    "dominio_no_existe": (
        "Lo que va después de la @ no existe o no recibe correo",
        "No se encontró ningún servidor de correo para esa dirección.",
        "Revise cómo escribió la parte final de la dirección (por ejemplo «gmail.com» y no «gmial.com»). Si está bien escrita, esa institución no tiene el correo funcionando: contáctela por otro medio.",
    ),
    "cuenta_inactiva": (
        "La cuenta de esa persona está desactivada",
        "El servidor del destinatario informó que esa cuenta ya no está activa.",
        "Pida a la persona su correo actual y reenvíe el mensaje a esa dirección.",
    ),
    "muy_grande": (
        "El correo es demasiado grande para ese destinatario",
        "El servidor del destinatario no acepta correos de ese tamaño (normalmente por los archivos adjuntos).",
        "Envíe los archivos como enlace del Drive, o repártalos en varios correos más pequeños.",
    ),
    "nos_rechazan": (
        "El servidor del destinatario rechazó nuestro correo",
        "Su correo estaba bien dirigido, pero el servidor de destino no lo aceptó por sus reglas de seguridad.",
        "No es un error suyo. Reenvíe este aviso a Tecnología para que lo resuelva con ese servidor; mientras tanto, contacte a la persona por otro medio.",
    ),
    "sin_conexion": (
        "No se pudo conectar con el servidor del destinatario",
        "El servidor de destino no respondió o pidió intentar más tarde.",
        "Suele ser pasajero: espere un rato y vuelva a enviar. Si se repite con la misma dirección, avise a Tecnología.",
    ),
    "desconocido": (
        "El correo no se pudo entregar",
        "El servidor de destino lo devolvió sin un motivo que podamos interpretar.",
        "Reenvíe este aviso a Tecnología para que lo revise.",
    ),
}

_DEMORA = (
    "Su correo todavía no se entrega",
    "El servidor de destino no lo ha aceptado aún. Nuestro servidor seguirá intentándolo durante unos días.",
    "No hace falta reenviarlo todavía. Si es urgente, contacte a la persona por otro medio.",
)


# Causa en pocas palabras, para el aviso de demora («todavía no se entrega porque…»).
_CAUSA_CORTA = {
    "buzon_lleno": "el buzón de esa persona está lleno",
    "dominio_no_existe": "no se encuentra el servidor de correo de esa dirección (revise lo que va después de la @)",
    "sin_conexion": "el servidor del destinatario no responde",
    "nos_rechazan": "el servidor del destinatario no lo acepta por ahora",
}


def clasificar(estado: str, diagnostico: str) -> str:
    texto = f"{estado} {diagnostico}".lower()
    for tipo, patron in _REGLAS:
        if re.search(patron, texto):
            return tipo
    return "desconocido"


def _una_linea(texto: str) -> str:
    return " ".join(str(texto or "").split())


def _es_rebote(msg) -> bool:
    if (
        msg.get_content_type() == "multipart/report"
        and "delivery-status" in str(msg.get("Content-Type", "")).lower()
    ):
        return True
    return "mailer-daemon" in str(msg.get("From", "")).lower() and msg.is_multipart()


def explicar(raw_email: str) -> dict | None:
    """Devuelve la explicación del rebote, o None si el correo no es un aviso de entrega."""
    try:
        msg = email.message_from_string(raw_email, policy=email.policy.default)
        if not _es_rebote(msg):
            return None
        destinatarios, original = [], {}
        for parte in msg.walk():
            tipo = parte.get_content_type()
            if tipo == "message/delivery-status":
                for bloque in parte.get_payload() or []:
                    final = bloque.get("Final-Recipient") or bloque.get(
                        "Original-Recipient"
                    )
                    if not final:
                        continue
                    correo = _una_linea(str(final).split(";", 1)[-1])
                    estado = _una_linea(bloque.get("Status", ""))
                    diag = _una_linea(
                        str(bloque.get("Diagnostic-Code", "")).split(";", 1)[-1]
                    )
                    accion = _una_linea(bloque.get("Action", "")).lower()
                    clase = clasificar(estado, diag)
                    demorado = accion == "delayed"
                    titulo, que, hacer = _DEMORA if demorado else _TEXTOS[clase]
                    if demorado and clase in _CAUSA_CORTA:
                        que = f"Todavía no se entrega porque {_CAUSA_CORTA[clase]}. Nuestro servidor seguirá intentándolo durante unos días."
                    destinatarios.append(
                        {
                            "correo": correo,
                            "tipo": "demorado" if demorado else clase,
                            "definitivo": not demorado,
                            "titulo": titulo,
                            "que_paso": que,
                            "que_hacer": hacer,
                            "detalle_tecnico": f"{estado} {diag}".strip()[:500],
                        }
                    )
            elif tipo in ("message/rfc822", "text/rfc822-headers") and not original:
                carga = parte.get_payload()
                interno = carga[0] if isinstance(carga, list) and carga else None
                if interno is None and isinstance(carga, str):
                    interno = email.message_from_string(
                        carga, policy=email.policy.default
                    )
                if interno is not None:
                    original = {
                        "asunto": _una_linea(interno.get("Subject", "")),
                        "fecha": _una_linea(interno.get("Date", "")),
                    }
        if not destinatarios:
            return None
        return {"destinatarios": destinatarios, "original": original}
    except (
        Exception
    ):  # noqa: BLE001 — un aviso raro se muestra tal cual, nunca rompe la lectura
        return None
