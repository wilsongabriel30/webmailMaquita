"""Orden por fecha en el servidor: UID SORT (RFC 5256).

Por qué existe este módulo: aioimaplib no sabe hacer `UID SORT`. Su método `uid()` solo
acepta FETCH, STORE, COPY, MOVE y EXPUNGE, y con cualquier otra orden lanza `Abort`. El
listado de mensajes lo intentaba, se tragaba la excepción y caía al orden por UID.

Con correo recibido de forma natural el UID crece con la fecha y no se nota. Pero en los
buzones migrados desde Zimbra el UID NO sigue la fecha: la sincronización nocturna de agosto
copió primero lo de los últimos 150 días y la migración final del 14/09/2026 copió después
lo anterior, que quedó con UID más altos. Resultado: la persona veía septiembre y, acto
seguido, marzo; abril–agosto quedaban enterrados al final de la lista («no están los correos
después del 27 de marzo»).

Aquí se envía la orden tal cual la define el protocolo, usando la clase `Command` de la
propia librería, que ya sabe esperar la respuesta `* SORT ...`.
"""

import asyncio

import aioimaplib

ORDEN_POR_OMISION = "(REVERSE DATE)"


def parse_sort_lines(lines) -> list[int]:
    """Extrae los UID de las líneas de respuesta a SORT (`* SORT 12 7 3` o `SORT 12 7 3`)."""
    uids: list[int] = []
    for line in lines:
        if isinstance(line, (bytes, bytearray)):
            line = line.decode("utf-8", errors="replace")
        line = line.strip()
        if not line or line.endswith("completed.") or line.endswith("completed"):
            continue
        if line.startswith("*"):
            line = line[1:].strip()
        if line.upper().startswith("SORT"):
            line = line[4:]
        uids.extend(int(x) for x in line.split() if x.isdigit())
    return uids


async def uid_sort(
    imap: aioimaplib.IMAP4,
    criteria: list[str],
    orden: str = ORDEN_POR_OMISION,
    charset: str = "UTF-8",
) -> list[int] | None:
    """Devuelve los UID de la carpeta seleccionada ordenados por el servidor.

    `None` si el servidor no acepta la orden (sin capacidad SORT, estado incorrecto, tiempo
    agotado): quien llama decide el plan B. Nunca lanza.
    """
    proto = imap.protocol
    try:
        cmd = aioimaplib.Command(
            "SORT",
            proto.new_tag(),
            orden,
            charset,
            *criteria,
            prefix="UID",
            loop=proto.loop,
        )
        resp = await asyncio.wait_for(proto.execute(cmd), imap.timeout)
    except Exception:
        return None
    if resp.result != "OK":
        return None
    return parse_sort_lines(resp.lines)
