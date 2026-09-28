"""Pedir un correo sin abrirlo no lo marca como leído.

Antecedente (28/09/2026): los correos nuevos aparecían como leídos sin que nadie los abriera.
La descarga para leer sin conexión pedía cada correo reciente al servidor y esa lectura ponía
la marca `\\Seen`. Ahora las lecturas que no hace una persona van con `mark_seen=False`:
se piden con `BODY.PEEK[]` (RFC822 marca por sí solo) y no se envía el STORE.
"""

import asyncio

from app.mail.clients import imap_client

CORREO = b"From: a@ejemplo.com\r\nSubject: Hola\r\n\r\nCuerpo\r\n"


class _Resp:
    def __init__(self, result, lines):
        self.result = result
        self.lines = lines


class _Imap:
    """Servidor de mentira: anota las órdenes que recibe."""

    def __init__(self, banderas=b""):
        self.ordenes = []
        self.banderas = banderas

    async def select(self, carpeta):
        return _Resp("OK", [])

    async def uid(self, orden, *args):
        self.ordenes.append((orden, args))
        if orden == "fetch":
            cabecera = b"1 FETCH (UID 7 FLAGS (" + self.banderas + b") BODY[] {%d}" % len(CORREO)
            return _Resp("OK", [cabecera, CORREO, b")", b"Fetch completed."])
        return _Resp("OK", [])


def _leer(imap, **kw):
    return asyncio.run(imap_client.fetch_full_message(imap, "INBOX", 7, **kw))


def test_sin_marcar_usa_peek_y_no_envia_store():
    imap = _Imap()
    msg = _leer(imap, mark_seen=False)
    assert msg["uid"] == 7
    assert "Cuerpo" in msg["raw_email"]
    assert "\\Seen" not in msg["flags"]
    assert [o for o, _ in imap.ordenes] == ["fetch"]
    assert "BODY.PEEK[]" in imap.ordenes[0][1][1]


def test_abrir_el_correo_lo_sigue_marcando_como_leido():
    imap = _Imap()
    _leer(imap)
    assert [o for o, _ in imap.ordenes] == ["fetch", "store"]
    assert "RFC822" in imap.ordenes[0][1][1]
    assert imap.ordenes[1][1] == ("7", "+FLAGS", "(\\Seen)")
