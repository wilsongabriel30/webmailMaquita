"""Comprobar que un valor o una frase están de verdad en un correo (busqueda_exacta.py)."""

import base64

from app.mail import busqueda_exacta as be


def test_reconoce_los_valores_con_decimales_o_miles():
    assert be.valor_numerico("205,6") == "205.6"
    assert be.valor_numerico("205.6") == "205.6"
    assert be.valor_numerico("$1.250,00") == "1.250.00"
    assert be.valor_numerico("12,5%") == "12.5"
    for no_es in ("205", "factura", "T-53", "ana@example.org", "10:30", "", "205,"):
        assert be.valor_numerico(no_es) is None, no_es


def test_que_terminos_hay_que_comprobar():
    assert be.es_exacto("205.6") and be.es_exacto("informe mensual")
    assert not be.es_exacto("fernando") and not be.es_exacto("205")


def test_coma_y_punto_valen_lo_mismo():
    c = be.Comprobador(["205.6"])
    assert c.esta_en("Total a pagar: 205,6 USD")
    assert c.esta_en("Total a pagar: 205.6")
    assert c.esta_en(
        "valor $205,60 más impuestos"
    ), "los ceros de más no cambian el valor"
    assert c.esta_en("(205,6)") and c.esta_en("205,6.")


def test_un_numero_mas_largo_no_es_el_valor():
    c = be.Comprobador(["205.6"])
    for otro in (
        "factura 205157 del día 6",
        "1.205,6",
        "3205,6",
        "205,65",
        "205.6.1",
        "205,600.00",
        "205 6",
        "205 y 6",
    ):
        assert not c.esta_en(otro), otro


def test_miles_y_decimales():
    c = be.Comprobador(["1.250.00"])
    assert c.esta_en("Pago de 1.250,00") and c.esta_en("USD 1,250.00")
    assert not c.esta_en("11.250,00") and not c.esta_en("1.250,005")
    assert not c.esta_en("1.250")
    # Con tres cifras al final lo escrito puede ser un millar: no se le añaden ceros.
    assert not be.Comprobador(["1.250"]).esta_en("1.2500")


def test_frase_sin_tildes_mayusculas_ni_signos():
    c = be.Comprobador(["informe mensual"])
    assert c.esta_en("INFORME   MENSUAL de octubre")
    assert c.esta_en("el informe_mensual.pdf") and c.esta_en("Informe\r\nmensual")
    assert not c.esta_en("informe de cierre mensual")
    assert not c.esta_en("preinforme mensual")
    assert be.Comprobador(["planificación anual"]).esta_en("Planificacion Anual 2026")


def test_todos_los_terminos_exactos_deben_estar():
    c = be.Comprobador(["205.6", "informe mensual"])
    assert c.esta_en("Informe mensual", "el valor es 205,6")
    assert not c.esta_en("Informe mensual", "el valor es 206")
    assert not be.Comprobador(["205.6"]).esta_en("", "")


def test_cabecera_codificada_se_lee():
    cruda = b"Subject: =?UTF-8?B?UGFnbyBkZSAyMDUsNiBkw7NsYXJlcw==?=\r\n\r\n"
    assert "Pago de 205,6 dólares" in be.cabecera_legible(cruda)
    assert be.cabecera_legible(b"Subject: uno\r\n dos\r\n") == "Subject: uno dos\r\n"


def test_texto_plano_en_quoted_printable():
    cab = b"Content-Type: text/plain; charset=iso-8859-1\r\nContent-Transfer-Encoding: quoted-printable\r\n"
    cuerpo = b"El valor de la cuota es 205,=\r\n6 d=F3lares."
    texto = be.texto_legible(cab, cuerpo)
    assert "205,6 dólares" in texto
    assert be.Comprobador(["205.6"]).esta_en(texto)


def test_html_en_base64_cortado_a_la_mitad():
    pagina = (
        "<html><head><style>td{width:205.6px}</style></head><body><table><tr>"
        "<td>Total</td><td><b>1.250</b>,00&nbsp;USD</td></tr></table>" + "x" * 500
    )
    codificado = base64.encodebytes(pagina.encode("utf-8"))[
        :-37
    ]  # cortado, sin relleno
    cab = b'Content-Type: text/html; charset="utf-8"\r\nContent-Transfer-Encoding: base64\r\n'
    texto = be.texto_legible(cab, codificado)
    assert "Total" in texto and "<td>" not in texto
    assert not be.Comprobador(["205.6"]).esta_en(texto), "los estilos no son texto"


def test_multiparte_sin_cierre_y_sin_abrir_adjuntos():
    cab = b'Content-Type: multipart/mixed; boundary="lim"\r\n'
    cuerpo = (
        b"--lim\r\nContent-Type: text/plain; charset=utf-8\r\n\r\nAbono de 205,6 recibido.\r\n"
        b'--lim\r\nContent-Type: text/csv; name="datos.csv"\r\n'
        b'Content-Disposition: attachment; filename="datos.csv"\r\n\r\n999,9;1\r\n'
    )
    texto = be.texto_legible(cab, cuerpo)
    assert "Abono de 205,6 recibido." in texto
    assert "999,9" not in texto, "los adjuntos no se abren"


def test_un_cuerpo_ilegible_no_revienta():
    assert be.texto_legible(b"", b"") == ""
    assert isinstance(
        be.texto_legible(b"Content-Type: text/plain; charset=x-raro\r\n", b"\xff\xfe"),
        str,
    )
