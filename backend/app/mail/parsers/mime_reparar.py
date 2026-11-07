"""Correos con el límite MIME mal declarado (05/11/2026).

El facturador del SRI (facturadorsri@infosri.gob.ec) envía mensajes cuya cabecera dice
`Content-Type: multipart/mixed; boundary="----=_Part_5408_…"` pero cuyo cuerpo usa otro
límite (`------=_Part_4008_…`, generado antes). Python no encuentra el límite declarado
(StartBoundaryNotFoundDefect), trata el mensaje como texto plano y la persona ve las
cabeceras MIME crudas en vez de los enlaces al PDF y al XML del comprobante (reporte de
Fabiola Quille, bcontabilidad@, 162 correos del SRI en su bandeja). Zimbra lo toleraba.

Aquí se detecta ese caso y se vuelve a declarar en la cabecera el límite que realmente
aparece en el cuerpo. El correo guardado en el buzón no se toca: solo cambia lo que se
interpreta al mostrarlo.
"""

import email
import email.policy
import re
from email.errors import StartBoundaryNotFoundDefect

_LINEA_LIMITE = re.compile(r"^--([^\s\"]{6,})\r?$", re.M)


def reparar_limite_mime(raw: str) -> str:
    """Devuelve `raw` con el límite corregido si hace falta; si no, tal cual."""
    if not raw or "boundary" not in raw[:8192].lower():
        return raw
    try:
        msg = email.message_from_string(raw, policy=email.policy.default)
    except Exception:  # noqa: BLE001
        return raw
    if msg.get_content_maintype() != "multipart" or msg.is_multipart():
        return raw
    if not any(isinstance(d, StartBoundaryNotFoundDefect) for d in msg.defects):
        return raw
    declarado = msg.get_boundary()
    if not declarado:
        return raw
    corte = raw.find("\r\n\r\n")
    largo = 4
    if corte < 0:
        corte = raw.find("\n\n")
        largo = 2
    if corte < 0:
        return raw
    cuerpo = raw[corte + largo :]
    encontrado = _LINEA_LIMITE.search(cuerpo)
    if not encontrado or encontrado.group(1) == declarado:
        return raw
    # Solo el límite que está en el cuerpo sirve; se usa el primero que abre una parte.
    cabeceras = raw[:corte].replace(declarado, encontrado.group(1))
    return cabeceras + raw[corte:]
