"""Una cabecera de direcciones mal formada no debe impedir listar ni abrir el correo."""

from app.mail.parsers.mime_parser import parse_full_message, parse_headers

MALO = (
    "From: Ana <ana@example.org>\r\n"
    'To: "Luis\r\n Perez" <luis@example.org>, =?utf-8?q?Mar=C3=ADa=0D=0AJos=C3=A9?= <maria@example.org>\r\n'
    "Cc: =?utf-8?b?UGVkcm8NCkdvbWV6?= <pedro@example.org>\r\n"
    "Subject: Informe\r\n"
    "Message-ID: <1@example.org>\r\n"
    "Date: Fri, 13 Nov 2026 10:00:00 -0500\r\n"
)


def test_listar_no_falla_con_un_salto_de_linea_en_el_nombre():
    n = parse_headers(MALO, uid=7)
    assert n.uid == 7 and n.subject == "Informe"
    assert (
        "luis@example.org" in n.to_addr
        and "\n" not in n.to_addr
        and "\r" not in n.to_addr
    )
    assert "pedro@example.org" in n.cc_addr
    assert "ana@example.org" in n.from_addr


def test_abrir_el_correo_tampoco_falla():
    n = parse_full_message(MALO + "\r\nHola.\r\n", uid=7)
    assert n.subject == "Informe" and "luis@example.org" in n.to_addr


def test_las_cabeceras_normales_no_cambian():
    bueno = "From: Ana <ana@example.org>\r\nTo: Luis <luis@example.org>\r\nSubject: =?utf-8?q?Reuni=C3=B3n?=\r\n\r\n"
    n = parse_headers(bueno)
    assert (
        n.from_addr == "Ana <ana@example.org>"
        and n.to_addr == "Luis <luis@example.org>"
        and n.subject == "Reunión"
    )
