"""Tildes en correos con cuerpo 8bit/binary (13/10/2026).

Antecedente: los bytes del correo se pasaban a texto con «utf-8, errors=replace» antes
del lector de Python, que con esas partes daba «comit�» en lugar de «comité». Pasaba
con los .eml adjuntos como message/rfc822 (el servidor los entrega por BINARY, con las
partes ya en binario) y con los correos que llegan en 8bit a la bandeja.
"""

import asyncio
import json

from app.mail.clients import imap_client
from app.mail.parsers.mime_parser import parse_full_message
from app.mail.routers import adjunto_correo

CABECERAS = (
    b"From: Direcci\xc3\xb3n <direccion@example.org>\r\n"
    b"Subject: =?utf-8?q?Reuni=C3=B3n?=\r\n"
    b"MIME-Version: 1.0\r\n"
)


def _cuerpo(tipo, charset, cte, contenido):
    return CABECERAS + (
        b"Content-Type: %s; charset=%s\r\nContent-Transfer-Encoding: %s\r\n\r\n%s\r\n"
        % (tipo, charset, cte, contenido)
    )


def test_eml_entregado_en_binario_conserva_las_tildes():
    eml = (
        CABECERAS
        + b'Content-Type: multipart/alternative; boundary="B"\r\n\r\n'
        b"--B\r\nContent-Type: text/plain; charset=utf-8\r\nContent-Transfer-Encoding: binary\r\n\r\n"
        b"Acta del comit\xc3\xa9, a\xc3\xb1o 2026.\r\n"
        b"--B\r\nContent-Type: text/html; charset=utf-8\r\nContent-Transfer-Encoding: binary\r\n\r\n"
        b"<p>Acta del <b>comit\xc3\xa9</b></p>\r\n--B--\r\n"
    )
    vista = adjunto_correo.correo_adjunto_a_vista(eml)
    assert "comité, año" in vista["text_body"]
    assert "comité" in vista["html_body"]
    assert "�" not in vista["text_body"] + vista["html_body"]
    assert vista["subject"] == "Reunión"
    assert vista["from"].startswith("Dirección")
    json.dumps(vista)  # nada de caracteres sueltos que rompan la respuesta


def test_cuerpo_8bit_en_latin1():
    r = parse_full_message(
        imap_client.bytes_a_correo(_cuerpo(b"text/plain", b"iso-8859-1", b"8bit", b"Comit\xe9"))
    )
    assert r.text_body.strip() == "Comité"


def test_bytes_invalidos_no_rompen_la_respuesta():
    r = parse_full_message(
        imap_client.bytes_a_correo(_cuerpo(b"text/plain", b"utf-8", b"8bit", b"Comit\xe9 \xff"))
    )
    json.dumps({"texto": r.text_body, "asunto": r.subject, "de": r.from_addr})


class _Resp:
    def __init__(self, result, lines):
        self.result = result
        self.lines = lines


class _Imap:
    def __init__(self, crudo):
        self.crudo = crudo

    async def select(self, carpeta):
        return _Resp("OK", [])

    async def uid(self, orden, uid, *resto):
        return _Resp(
            "OK",
            [
                b"1 FETCH (UID 9 FLAGS (\\Seen) BODY[] {%d}" % len(self.crudo),
                bytearray(self.crudo),
                b")",
                b"Fetch completed.",
            ],
        )


def test_la_bandeja_lee_un_correo_8bit_con_tildes():
    crudo = _cuerpo(b"text/plain", b"utf-8", b"8bit", b"Acta del comit\xc3\xa9.")
    raw = asyncio.run(
        imap_client.fetch_full_message(_Imap(crudo), "INBOX", 9, mark_seen=False)
    )
    assert raw["uid"] == 9 and raw["flags"] == ["\\Seen"]
    r = parse_full_message(raw["raw_email"], uid=raw["uid"], flags=raw["flags"])
    assert r.text_body.strip() == "Acta del comité."
