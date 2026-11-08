"""Adjuntos de cada correo para la lista de la bandeja (07/11/2026, como Outlook).

La carga de la lista solo pedía cabeceras, así que `has_attachments` llegaba siempre en falso y la
fila nunca mostraba el clip. Aquí se pide, en UNA sola orden IMAP para toda la página, la
BODYSTRUCTURE (solo la estructura, no el contenido; Dovecot la tiene en caché) y se sacan los
nombres de las partes marcadas como adjunto. Las imágenes incrustadas en el cuerpo (INLINE) no
cuentan, igual que en Outlook.

Si el servidor tarda más de TIEMPO_MAX_S o falla, la lista sale igual que antes, sin clip.
"""

import asyncio
import logging
import re

from app.mail.services.busqueda_adjuntos import _decodificar

log = logging.getLogger(__name__)

TIEMPO_MAX_S = 3.0
MAX_NOMBRES = 3  # la fila muestra como mucho dos y «+N»; el resto no hace falta

_RE_UID = re.compile(r"\b(\d+) FETCH \(UID (\d+)\b")
_RE_ADJUNTO = re.compile(r'"ATTACHMENT"\s+\(([^()]*)\)', re.I)
_RE_FILENAME = re.compile(r'"FILENAME\*?"\s+"((?:[^"\\]|\\.)*)"', re.I)


def adjuntos_de_estructura(estructura: str) -> tuple[bool, list[str]]:
    """(¿hay adjuntos?, nombres) a partir del texto de una BODYSTRUCTURE."""
    hay = "ATTACHMENT" in estructura.upper()
    nombres: list[str] = []
    for m in _RE_ADJUNTO.finditer(estructura):
        f = _RE_FILENAME.search(m.group(1))
        if f:
            nombre = _decodificar(f.group(1)).strip()
            if nombre and nombre not in nombres:
                nombres.append(nombre)
    return hay, nombres[:MAX_NOMBRES]


async def adjuntos_por_uid(imap, uids: list[int]) -> dict[int, tuple[bool, list[str]]]:
    """{uid: (hay_adjuntos, nombres)} para los UIDs de la página; {} si no se pudo."""
    if not uids:
        return {}
    try:
        resp = await asyncio.wait_for(
            imap.uid("fetch", ",".join(str(u) for u in uids), "(UID BODYSTRUCTURE)"),
            timeout=TIEMPO_MAX_S,
        )
    except Exception as e:  # noqa: BLE001 - la lista no puede fallar por esto
        log.info("adjuntos de la lista: sin estructura (%s)", e)
        return {}
    if resp.result != "OK":
        return {}
    texto = "\n".join(
        (
            ln.decode("utf-8", "replace")
            if isinstance(ln, (bytes, bytearray))
            else str(ln)
        )
        for ln in resp.lines
    )
    trozos = _RE_UID.split(texto)
    # split devuelve: [previo, seq, uid, cuerpo, seq, uid, cuerpo, ...]
    resultado: dict[int, tuple[bool, list[str]]] = {}
    for j in range(1, len(trozos) - 2, 3):
        resultado[int(trozos[j + 1])] = adjuntos_de_estructura(trozos[j + 2])
    return resultado
