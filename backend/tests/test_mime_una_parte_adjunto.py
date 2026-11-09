"""Un correo de una sola parte no textual (informe DMARC en application/zip) es un adjunto,
no un cuerpo ilegible (08/11/2026)."""

import base64
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.mail.parsers.mime_parser import parse_full_message

_ZIP = b"PK\x03\x04" + bytes(range(256))


def _correo(tipo: bytes, disposicion: bytes) -> str:
    return (
        b"From: noreply-dmarc-support@example.com\r\n"
        b"To: postmaster@example.org\r\n"
        b"Subject: Report domain: example.org\r\n"
        b"MIME-Version: 1.0\r\n"
        b"Content-Type: " + tipo + b"\r\n"
        b"Content-Disposition: " + disposicion + b"\r\n"
        b"Content-Transfer-Encoding: base64\r\n\r\n"
        + base64.encodebytes(_ZIP)
    ).decode("ascii")


def test_zip_de_una_sola_parte_es_adjunto():
    r = parse_full_message(
        _correo(
            b'application/zip; name="google.com!example.org!1.xml.zip"',
            b'attachment; filename="google.com!example.org!1.xml.zip"',
        )
    )
    assert r.text_body == "" and r.html_body == ""
    assert "PK" not in r.snippet
    assert len(r.attachments) == 1
    a = r.attachments[0]
    assert a.filename == "google.com!example.org!1.xml.zip"
    assert a.content_type == "application/zip"
    assert a.part_number == "1"
    assert a.size == len(_ZIP)
    json.dumps({"t": r.text_body, "s": r.snippet})


def test_binario_sin_nombre_recibe_nombre_generico():
    r = parse_full_message(_correo(b"application/octet-stream", b"attachment"))
    assert r.attachments[0].filename == "attachment_1"
    assert r.text_body == ""


def test_texto_plano_de_una_parte_sigue_siendo_cuerpo():
    raw = (
        "From: a@example.org\r\nTo: b@example.org\r\nSubject: Hola\r\n"
        "Content-Type: text/plain; charset=utf-8\r\n\r\nHola, buenos dias.\r\n"
    )
    r = parse_full_message(raw)
    assert r.text_body.strip() == "Hola, buenos dias."
    assert r.attachments == []
