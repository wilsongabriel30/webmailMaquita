"""Adjuntos .eml y de texto: se descargan decodificados y el .eml se abre como correo.

Antecedente (12/10/2026): `fetch_attachment` suponía base64 para todo. Un .eml adjunto
como message/rfc822 (7bit) salía como basura binaria y un .md en quoted-printable traía
`=C3=B3` en vez de «ó». Ahora se pide BINARY.PEEK (el servidor decodifica) y solo si
falla se vuelve a la lectura anterior. El .eml se pinta con el lector de la bandeja.
"""

import asyncio
import base64
from email.message import EmailMessage

import pytest
from fastapi import HTTPException

from app.mail.clients import imap_client
from app.mail.routers import adjunto_correo


class _Resp:
    def __init__(self, result, lines):
        self.result = result
        self.lines = lines


class _Imap:
    """Servidor de mentira: responde BINARY o no, y anota lo que se le pide."""

    def __init__(self, binario_ok=True, contenido=b"", en_base64=b""):
        self.binario_ok = binario_ok
        self.contenido = contenido
        self.en_base64 = en_base64
        self.pedidos = []

    async def select(self, carpeta):
        return _Resp("OK", [])

    async def uid(self, orden, uid, que):
        self.pedidos.append(que)
        if "BINARY.PEEK" in que:
            if not self.binario_ok:
                return _Resp("NO", [b"[UNKNOWN-CTE] desconocido"])
            return _Resp(
                "OK",
                [
                    b"1 FETCH (UID 7 BINARY[2] ~{%d}" % len(self.contenido),
                    bytearray(self.contenido),
                    b")",
                    b"Fetch completed.",
                ],
            )
        return _Resp(
            "OK",
            [b"1 FETCH (UID 7 BODY[2] {4}", self.en_base64, b")", b"Fetch completed."],
        )


def _leer(imap):
    return asyncio.run(imap_client.fetch_attachment(imap, "INBOX", 7, "2"))


def test_binary_entrega_el_texto_decodificado():
    texto = "# Informe de gestión\n".encode()
    imap = _Imap(contenido=texto)
    assert _leer(imap) == texto
    assert imap.pedidos == ["(BINARY.PEEK[2])"]


def test_sin_binary_vuelve_a_la_lectura_anterior():
    original = b"hola, contenido del adjunto " * 4
    imap = _Imap(binario_ok=False, en_base64=bytearray(base64.b64encode(original)))
    assert _leer(imap) == original
    assert imap.pedidos == ["(BINARY.PEEK[2])", "(BODY.PEEK[2])"]


def _eml():
    m = EmailMessage()
    m["From"] = "Dirección <direccion@example.org>"
    m["To"] = "gerencia@example.org"
    m["Subject"] = "Reunión de comité"
    m["Date"] = "Mon, 12 Oct 2026 09:00:00 -0500"
    m.set_content("Texto plano")
    m.add_alternative(
        '<p onclick="x()">Hola <b>equipo</b></p><script>alert(1)</script>'
        '<img src="https://rastreo.example.net/p.gif">',
        subtype="html",
    )
    m.add_attachment(
        b"%PDF", maintype="application", subtype="pdf", filename="acta.pdf"
    )
    return bytes(m)


def test_el_eml_se_pinta_como_correo_y_saneado():
    vista = adjunto_correo.correo_adjunto_a_vista(_eml())
    assert vista["subject"] == "Reunión de comité"
    assert "direccion@example.org" in vista["from"]
    assert "<b>equipo</b>" in vista["html_body"]
    assert "<script" not in vista["html_body"]
    assert "onclick" not in vista["html_body"]
    # La imagen remota no se carga (queda un aviso «[Imagen bloqueada]» en su lugar).
    assert '<img src="https://rastreo.example.net' not in vista["html_body"]
    assert vista["blocked_image_count"] == 1
    assert [a["filename"] for a in vista["attachments"]] == ["acta.pdf"]


def test_un_eml_enorme_no_se_previsualiza(monkeypatch):
    monkeypatch.setattr(adjunto_correo, "MAX_BYTES", 10)
    with pytest.raises(HTTPException) as e:
        adjunto_correo.correo_adjunto_a_vista(_eml())
    assert e.value.status_code == 413
