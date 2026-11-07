"""Rechazos definitivos del servidor de correo (05/11/2026).

Postfix (y sus milters: protección de datos, antivirus, destinatarios) responde con códigos 5xx cuando el
mensaje NO se va a aceptar nunca tal cual está. Repetirlo no sirve: hay que decírselo a la persona en claro.
Devuelve el texto para el usuario, o None si el error no es un rechazo definitivo (y se trata como 500).
"""

import re

_CODIGO = re.compile(r"^\(?(\d{3})[,\s]")


def codigo_smtp(err: Exception) -> int | None:
    code = getattr(err, "code", None)
    if isinstance(code, int):
        return code
    m = _CODIGO.match(str(err).strip())
    return int(m.group(1)) if m else None


def mensaje_definitivo(err: Exception) -> str | None:
    code = codigo_smtp(err)
    if code is None or not 500 <= code <= 599:
        return None
    texto = getattr(err, "message", None) or str(err)
    if isinstance(texto, bytes):
        texto = texto.decode("utf-8", "replace")
    texto = str(texto).strip()
    # «(554, '5.7.1 Bloqueado por …')» → «Bloqueado por …»
    m = re.search(r"'(?:\d\.\d\.\d\s+)?(.*?)'\)?$", texto, re.S)
    if m:
        texto = m.group(1)
    texto = re.sub(r"^\d\.\d\.\d\s+", "", texto).strip()
    return f"El servidor de correo rechazó el envío: {texto[:400]} Corrige el mensaje antes de volver a enviarlo; no se reintentará solo."
