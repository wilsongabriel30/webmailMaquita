from app.mail.services.adjuntos_lista import adjuntos_de_estructura


def test_adjuntos_con_nombre():
    bs = (
        '(("TEXT" "PLAIN" ("CHARSET" "utf-8") NIL NIL "7BIT" 40 2 NIL NIL NIL NIL)'
        '("APPLICATION" "XML" NIL NIL NIL "BASE64" 28 NIL ("ATTACHMENT" ("FILENAME" "XML_FACTURA.xml")) NIL NIL)'
        '("APPLICATION" "PDF" NIL NIL NIL "BASE64" 20 NIL ("ATTACHMENT" ("FILENAME" "=?utf-8?q?Factura_n=C2=BA1.pdf?=")) NIL NIL)'
        ' "MIXED" ("BOUNDARY" "x") NIL NIL NIL)'
    )
    hay, nombres = adjuntos_de_estructura(bs)
    assert hay
    assert nombres == ["XML_FACTURA.xml", "Factura nº1.pdf"]


def test_imagen_incrustada_no_cuenta():
    bs = (
        '(("TEXT" "HTML" ("CHARSET" "utf-8") NIL NIL "7BIT" 40 2 NIL NIL NIL NIL)'
        '("IMAGE" "PNG" ("NAME" "logo.png") "<logo>" NIL "BASE64" 20 NIL ("INLINE" ("FILENAME" "logo.png")) NIL NIL)'
        ' "RELATED" ("BOUNDARY" "x") NIL NIL NIL)'
    )
    assert adjuntos_de_estructura(bs) == (False, [])


def test_sin_adjuntos():
    assert adjuntos_de_estructura(
        '("TEXT" "PLAIN" ("CHARSET" "utf-8") NIL NIL "7BIT" 40 2 NIL NIL NIL NIL)'
    ) == (False, [])
