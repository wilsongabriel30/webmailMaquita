"""Fecha de llegada al servidor (INTERNALDATE), 13/10/2026.

La cabecera Date la pone el equipo del remitente y se falsifica cambiando la hora de
Windows. La hora de llegada la registra nuestro servidor: el webmail la entrega como
`received_date` en la lista y en el correo abierto.
"""

import asyncio

from app.mail.clients import imap_client
from app.mail.clients.imap_client import fecha_llegada_iso


def test_internaldate_a_iso():
    linea = '3 FETCH (UID 23 FLAGS () INTERNALDATE "13-Oct-2026 09:28:53 -0500" RFC822.SIZE 3223'
    assert fecha_llegada_iso(linea) == "2026-10-13T09:28:53-05:00"
    # Día de una cifra (el servidor puede rellenar con espacio) y zona positiva.
    assert fecha_llegada_iso('INTERNALDATE " 1-Jan-2027 00:05:00 +0100"') == "2027-01-01T00:05:00+01:00"


def test_sin_internaldate_o_raro_da_none():
    assert fecha_llegada_iso("3 FETCH (UID 23 FLAGS ())") is None
    assert fecha_llegada_iso('INTERNALDATE "13-Xyz-2026 09:28:53 -0500"') is None


class _Resp:
    def __init__(self, result, lines):
        self.result = result
        self.lines = lines


class _Imap:
    async def select(self, carpeta):
        return _Resp("OK", [])

    async def uid(self, orden, uid, que):
        assert "INTERNALDATE" in que
        crudo = b"From: a@example.org\r\nDate: Wed, 01 Jan 2020 08:00:00 -0500\r\nSubject: x\r\n\r\nhola\r\n"
        return _Resp(
            "OK",
            [
                b'1 FETCH (UID 9 FLAGS (\\Seen) INTERNALDATE "13-Oct-2026 09:28:53 -0500" BODY[] {%d}' % len(crudo),
                bytearray(crudo),
                b")",
                b"Fetch completed.",
            ],
        )


def test_el_correo_abierto_trae_la_hora_de_llegada():
    raw = asyncio.run(imap_client.fetch_full_message(_Imap(), "INBOX", 9, mark_seen=False))
    assert raw["internal_date"] == "2026-10-13T09:28:53-05:00"
    assert raw["uid"] == 9


def test_la_lista_trae_la_hora_de_llegada():
    lineas = [
        b'1 FETCH (UID 5 FLAGS () INTERNALDATE "13-Oct-2026 09:28:53 -0500" RFC822.SIZE 99 BODY[HEADER.FIELDS (DATE)] {40}',
        bytearray(b"Date: Wed, 01 Jan 2020 08:00:00 -0500\r\n\r\n"),
        b")",
        b"Fetch completed.",
    ]
    (m,) = imap_client._parse_uid_fetch_response(lineas)
    assert m["internal_date"] == "2026-10-13T09:28:53-05:00"
    assert m["snippet"] == ""
