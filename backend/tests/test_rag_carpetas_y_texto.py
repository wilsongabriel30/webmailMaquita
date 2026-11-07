"""RAG de todas las carpetas: selección de carpetas, lectura de FETCH y texto indexado."""

import base64

from app.rag import carpetas, contexto, estructura, respuesta_fetch, texto

# --- Selección de carpetas -------------------------------------------------------------


def test_excluye_papelera_spam_y_borradores_en_todas_sus_variantes():
    excluidas = [
        "Trash",
        "Papelera",
        "Deleted Items",
        "Elementos eliminados",
        "Trash (2)",
        "Trash{82820000}",
        "mail_mcch_com_ec.Deleted Messages",
        "Junk",
        "Spam",
        "Spambox",
        "Correo electrónico no deseado",
        "Correo electrónico no deseado1",
        "Correo no deseado",
        "Unwanted",
        "Infected Items",
        "INBOX.Infected Items",
        "Drafts",
        "Borradores",
        "Borrador",
        "INBOX.Drafts",
        "Trash.Viejos",
        "Compartidos/jefe@example.org.INBOX",
        "Virtual.Todos",
    ]
    for n in excluidas:
        assert carpetas.excluida(n), n


def test_indexa_enviados_carpetas_propias_y_subcarpetas():
    incluidas = [
        "INBOX",
        "Sent",
        "Elementos enviados",
        "Archive",
        "INBOX.SRI",
        "INBOX.Bandeja entrada Respaldo",
        "Ana Ruiz Bandeja entrada anterior.Correos Anteriores",
        "PROVEEDORES2020-2021",
        "4_ BL Draft",
        "Notes",
        "Comments",
        "mail_example_org.Sent",
    ]
    for n in incluidas:
        assert not carpetas.excluida(n), n


def test_marcas_special_use_y_no_seleccionables():
    assert carpetas.excluida("Mi papelera rara", ["\\Trash"])
    assert carpetas.excluida("Cosas", ["\\Junk"])
    assert carpetas.excluida("Pendientes", ["\\HasNoChildren", "\\Drafts"])
    assert carpetas.excluida("Padre", ["\\Noselect", "\\HasChildren"])
    assert not carpetas.excluida("Enviados", ["\\Sent"])


def test_parsear_list_y_orden():
    lineas = [
        b'LIST (\\HasNoChildren \\Trash) "." Trash',
        b'LIST (\\HasNoChildren) "." "INBOX.Bandeja entrada Respaldo"',
        b'LIST (\\HasNoChildren \\Sent) "." Sent',
        b'LIST (\\HasChildren) "." INBOX',
        b'LIST (\\HasNoChildren) "." "Proyectos &AMk-xito"',
        b'(\\HasNoChildren \\Junk) "." Junk',
        b"List completed (0.001 + 0.000 secs).",
    ]
    todas = carpetas.parsear_list(lineas)
    assert {c["name"] for c in todas} == {
        "Trash",
        "INBOX.Bandeja entrada Respaldo",
        "Sent",
        "INBOX",
        "Proyectos Éxito",
        "Junk",
    }
    elegidas = [c["name"] for c in carpetas.a_indexar(todas)]
    assert elegidas == [
        "INBOX",
        "Sent",
        "INBOX.Bandeja entrada Respaldo",
        "Proyectos Éxito",
    ]
    exito = next(c for c in todas if c["name"] == "Proyectos Éxito")
    assert (
        exito["imap_name"] == "Proyectos &AMk-xito"
    )  # se abre con el nombre IMAP original


def test_etiqueta_legible():
    assert carpetas.etiqueta("INBOX") == "Bandeja de entrada"
    assert carpetas.etiqueta("INBOX.SRI.2024") == "Bandeja de entrada / SRI / 2024"
    assert carpetas.etiqueta("Sent") == "Enviados"
    assert carpetas.etiqueta(
        "Ana Ruiz Bandeja entrada anterior.Correos Anteriores"
    ) == ("Ana Ruiz Bandeja entrada anterior / Correos Anteriores")


# --- Respuestas FETCH y BODYSTRUCTURE -----------------------------------------------------

CAB = b"From: =?utf-8?q?Jos=C3=A9_P=C3=A9rez?= <jose@x.org>\r\nSubject: Informe SRI\r\nDate: Tue, 13 Oct 2026 09:28:53 -0500\r\nTo: ana@example.org\r\n\r\n"
ESTRUCTURA = (
    b'(("TEXT" "PLAIN" ("CHARSET" "utf-8") NIL NIL "QUOTED-PRINTABLE" 120 4 NIL NIL NIL NIL)'
    b'("TEXT" "HTML" ("CHARSET" "utf-8") NIL NIL "7BIT" 300 8 NIL NIL NIL NIL) "ALTERNATIVE")'
    b'("APPLICATION" "PDF" ("NAME" "factura.pdf") NIL NIL "BASE64" 90000 NIL ("ATTACHMENT" ("FILENAME" "factura.pdf")) NIL NIL) "MIXED"'
)


def _respuesta_cabeceras():
    return [
        b"1 FETCH (UID 41 BODYSTRUCTURE ("
        + ESTRUCTURA
        + b") BODY[HEADER.FIELDS (FROM TO CC SUBJECT DATE)] {%d}" % len(CAB),
        bytearray(CAB),
        b")",
        b'2 FETCH (UID 42 BODYSTRUCTURE ("TEXT" "HTML" ("CHARSET" "iso-8859-1") NIL NIL "BASE64" 500 10 NIL NIL NIL NIL) BODY[HEADER.FIELDS (FROM TO CC SUBJECT DATE)] {4}',
        bytearray(b"\r\n\r\n"),
        b")",
        b"Fetch completed (0.001 + 0.000 secs).",
    ]


def test_mensajes_de_fetch_con_literales_y_estructura():
    ms = respuesta_fetch.mensajes(_respuesta_cabeceras())
    assert [m["UID"] for m in ms] == ["41", "42"]
    assert respuesta_fetch.cabeceras(ms[0]) == CAB
    p = estructura.parte_de_texto(ms[0]["BODYSTRUCTURE"])
    assert p["parte"] == "1.1" and p["subtipo"] == "plain"
    assert p["codificacion"] == "quoted-printable"
    p2 = estructura.parte_de_texto(ms[1]["BODYSTRUCTURE"])
    assert p2 == {
        "parte": "1",
        "subtipo": "html",
        "charset": "iso-8859-1",
        "codificacion": "base64",
        "tamano": 500,
    }


def test_no_elige_adjuntos_de_texto():
    adjunto_txt = [
        [
            "TEXT",
            "PLAIN",
            ["NAME", "notas.txt"],
            None,
            None,
            "7BIT",
            "10",
            "1",
            None,
            ["ATTACHMENT", ["FILENAME", "notas.txt"]],
            None,
            None,
        ],
        ["APPLICATION", "PDF", None, None, None, "BASE64", "100", None, None, None],
        "MIXED",
    ]
    assert estructura.parte_de_texto(adjunto_txt) is None


# --- Texto ---------------------------------------------------------------------------------


def test_decodifica_base64_cortado_y_quoted_printable():
    b64 = base64.b64encode("Reunión con la cooperativa de Ambato".encode("latin-1"))
    assert texto.decodificar(b64[:-3], "base64", "iso-8859-1").startswith(
        "Reunión con la"
    )
    qp = b"Se aprob=C3=B3 el presupuesto =\r\nanual=C3"
    assert (
        texto.decodificar(qp, "quoted-printable", "utf-8")
        == "Se aprobó el presupuesto anual"
    )


def test_cuerpo_html_sin_citas_ni_nul_y_recortado():
    html = (
        "<html><head><style>p{}</style></head><body><p>Hola&nbsp;equipo,</p>"
        "<p>adjunto el informe\x00 final.</p><br>El lun, 12 oct 2026 a las 10:00, Ana escribió:"
        "<br>&gt; texto viejo</body></html>"
    ).encode()
    info = {"subtipo": "html", "codificacion": "7bit", "charset": "utf-8"}
    c = texto.cuerpo(html, info, 1500)
    assert c == "Hola equipo, adjunto el informe  final.".replace("  ", " ")
    assert "\x00" not in c and "escribió" not in c
    assert len(texto.cuerpo(b"x" * 5000, {"subtipo": "plain"}, 1500)) == 1500


def test_contenido_y_cabeceras_decodificadas():
    cab = texto.cabeceras(CAB)
    assert cab == {
        "de": "José Pérez <jose@x.org>",
        "para": "ana@example.org",
        "asunto": "Informe SRI",
        "fecha": "2026-10-13",
    }
    c = texto.contenido("Enviados", {**cab, "asunto": "Con\x00nul"}, "cuerpo")
    assert c.startswith("Carpeta: Enviados | Fecha: 2026-10-13 | De: José Pérez")
    assert "\x00" not in c and c.endswith("| cuerpo")


def test_contexto_incluye_la_carpeta_tambien_en_formato_antiguo():
    filas = [
        {
            "content": "Carpeta: Enviados | De: a | Asunto: b | cuerpo",
            "folder": "Sent",
            "subject": "b",
            "sender": "a",
        },
        {
            "content": "De: c | Asunto: d | ",
            "folder": "INBOX",
            "subject": "d",
            "sender": "c",
        },
    ]
    b = contexto.bloque(filas)
    assert "- Carpeta: Enviados | De: a" in b
    assert "- Carpeta: Bandeja de entrada | d (de c)" in b
