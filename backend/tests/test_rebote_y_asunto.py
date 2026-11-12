"""Rebotes explicados en lenguaje llano y asuntos sin marcas de spam ajenas."""

from __future__ import annotations

import pytest

from app.mail.parsers import asunto_limpio, rebote


def _dsn(
    estado: str, diag: str, accion: str = "failed", destino: str = "persona@example.net"
) -> str:
    return (
        "From: MAILER-DAEMON@correo.example.org (Mail Delivery System)\n"
        "To: yo@example.org\nSubject: Undelivered Mail Returned to Sender\nMIME-Version: 1.0\n"
        'Content-Type: multipart/report; report-type=delivery-status; boundary="LIM"\n\n'
        "--LIM\nContent-Description: Notification\nContent-Type: text/plain; charset=us-ascii\n\n"
        "This is the mail system at host correo.example.org.\n\n"
        "--LIM\nContent-Description: Delivery report\nContent-Type: message/delivery-status\n\n"
        "Reporting-MTA: dns; correo.example.org\nArrival-Date: Wed, 11 Nov 2026 10:50:00 -0500\n\n"
        f"Final-Recipient: rfc822; {destino}\nOriginal-Recipient: rfc822;{destino}\nAction: {accion}\n"
        f"Status: {estado}\nDiagnostic-Code: smtp; {diag}\n\n"
        "--LIM\nContent-Description: Undelivered Message Headers\nContent-Type: text/rfc822-headers\n\n"
        "From: yo@example.org\nTo: persona@example.net\nSubject: Informe trimestral\nDate: Wed, 11 Nov 2026 10:49:00 -0500\n\n"
        "--LIM--\n"
    )


CASOS = [
    (
        "4.2.2",
        "452-4.2.2 The recipient's inbox is out of storage space. 452 4.2.2 gsmtp",
        "buzon_lleno",
    ),
    ("5.2.2", "552 5.2.2 Mailbox full", "buzon_lleno"),
    (
        "5.1.1",
        "550 5.1.1 The email account that you tried to reach does not exist",
        "no_existe",
    ),
    (
        "5.1.1",
        "550 5.1.1 <x@example.net>: Recipient address rejected: User unknown in virtual mailbox table",
        "no_existe",
    ),
    (
        "4.4.3",
        "Host or domain name not found. Name service error for name=example.net type=MX: Host not found, try again",
        "dominio_no_existe",
    ),
    (
        "5.7.1",
        "550 5.7.1 Service unavailable; Client host blocked using Spamhaus",
        "nos_rechazan",
    ),
    (
        "5.7.26",
        "550-5.7.26 This mail has been blocked because the sender is unauthenticated (DMARC)",
        "nos_rechazan",
    ),
    (
        "5.2.3",
        "552 5.2.3 Message size exceeds fixed maximum message size",
        "muy_grande",
    ),
    (
        "5.2.1",
        "550 5.2.1 The email account that you tried to reach is disabled",
        "cuenta_inactiva",
    ),
    (
        "4.4.1",
        "connect to mx.example.net[192.0.2.9]:25: Connection timed out",
        "sin_conexion",
    ),
    ("5.0.0", "554 algo que nadie entiende", "desconocido"),
]


@pytest.mark.parametrize("estado,diag,esperado", CASOS)
def test_clasifica_los_motivos_mas_comunes(estado, diag, esperado):
    assert rebote.clasificar(estado, diag) == esperado


def test_explica_un_buzon_lleno_en_lenguaje_llano():
    r = rebote.explicar(
        _dsn("4.2.2", "452-4.2.2 The recipient's inbox is out of storage space")
    )
    d = r["destinatarios"][0]
    assert (
        d["correo"] == "persona@example.net"
        and d["tipo"] == "buzon_lleno"
        and d["definitivo"]
    )
    assert "lleno" in d["titulo"] and "No es un problema de su cuenta" in d["que_hacer"]
    assert "out of storage" in d["detalle_tecnico"]
    assert r["original"]["asunto"] == "Informe trimestral"


def test_direccion_mal_escrita_pide_revisarla():
    d = rebote.explicar(_dsn("5.1.1", "550 5.1.1 User unknown"))["destinatarios"][0]
    assert d["tipo"] == "no_existe" and "bien escrita" in d["que_hacer"]


def test_rechazo_del_otro_servidor_dice_que_no_es_error_de_la_persona():
    d = rebote.explicar(_dsn("5.7.1", "550 5.7.1 blocked using blocklist"))[
        "destinatarios"
    ][0]
    assert (
        d["tipo"] == "nos_rechazan"
        and "No es un error suyo" in d["que_hacer"]
        and "Tecnología" in d["que_hacer"]
    )


def test_aviso_de_demora_no_es_definitivo():
    d = rebote.explicar(_dsn("4.4.1", "Connection timed out", accion="delayed"))[
        "destinatarios"
    ][0]
    assert (
        d["tipo"] == "demorado"
        and not d["definitivo"]
        and "seguirá intentándolo" in d["que_paso"]
    )


def test_un_correo_normal_no_es_un_rebote():
    assert (
        rebote.explicar(
            "From: a@example.org\nTo: b@example.org\nSubject: Hola\n\nTexto\n"
        )
        is None
    )


def test_un_correo_ilegible_no_rompe_nada():
    assert rebote.explicar("\x00\x01 basura") is None


@pytest.mark.parametrize(
    "sucio,limpio",
    [
        ("RE: [===SPAM===] Informe final", "RE: Informe final"),
        ("Re: RE: [===SPAM===] Re: Microproyecto", "Re: RE: Re: Microproyecto"),
        ("***SPAM*** Oferta", "Oferta"),
        ("[SPAM] Hola", "Hola"),
        ("[SUSPECTED SPAM] Factura", "Factura"),
        ("{Spam?} Reunión", "Reunión"),
        ("Fwd: [ SPAM ] : Acta", "Fwd: Acta"),
        ("Hotel Days: Ahorra hasta 300 € ��", "Hotel Days: Ahorra hasta 300 €"),
    ],
)
def test_quita_las_marcas_de_spam_y_los_caracteres_danados(sucio, limpio):
    assert asunto_limpio.limpiar(sucio) == limpio


@pytest.mark.parametrize(
    "asunto",
    [
        "Campaña antispam 2026",
        "Informe sobre spam recibido",
        "Reunión",
        "",
        "RE: Spam en el buzón de ventas",
    ],
)
def test_no_toca_asuntos_que_solo_hablan_de_spam(asunto):
    assert asunto_limpio.limpiar(asunto) == asunto


def test_un_asunto_que_solo_era_la_marca_no_queda_vacio():
    assert asunto_limpio.limpiar("[SPAM]") == "[SPAM]"


def test_la_demora_dice_tambien_la_causa():
    d = rebote.explicar(
        _dsn(
            "4.2.2",
            "452-4.2.2 The recipient's inbox is out of storage space",
            accion="delayed",
        )
    )["destinatarios"][0]
    assert (
        d["tipo"] == "demorado"
        and "está lleno" in d["que_paso"]
        and "seguirá intentándolo" in d["que_paso"]
    )


def test_el_decodificador_entrega_el_asunto_sin_la_marca():
    from app.mail.parsers.mime_parser import parse_headers

    m = parse_headers(
        "From: a@example.org\nSubject: RE: [===SPAM===] Informe final\n\n"
    )
    assert m.subject == "RE: Informe final"
