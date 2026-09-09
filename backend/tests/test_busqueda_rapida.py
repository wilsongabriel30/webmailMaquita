"""Que buscar un correo sea instantáneo, y que siga siéndolo.

Medido en el buzón de tecnología (20 GB, 10.626 mensajes) sin índice de texto en Dovecot:

    una palabra suelta, antes    92.800 ms
    la misma, ahora                  86 ms
    por dominio                      60 ms
    rango de fechas                  67 ms
    dentro del contenido         97.222 ms   (solo si se pide)

La diferencia está en si la consulta toca BODY. Las cabeceras las tiene Dovecot indexadas; el
cuerpo hay que abrirlo y descifrarlo mensaje a mensaje, porque los buzones van cifrados.

Estas pruebas vigilan justo eso: que lo que escribe una persona normal no acabe en BODY sin
haberlo pedido. Si alguien vuelve a meterlo «para que encuentre más cosas», aquí se entera.
"""

from app.mail.search_advanced import parse_search_query


def test_una_palabra_no_entra_en_el_cuerpo():
    """El caso de siempre: alguien escribe una palabra y espera resultados YA."""
    criterios = parse_search_query("factura")
    assert "BODY" not in " ".join(criterios), (
        "el texto suelto no debe buscar en el cuerpo: son 93 segundos de espera"
    )
    juntos = " ".join(criterios)
    assert "FROM" in juntos and "TO" in juntos and "SUBJECT" in juntos


def test_el_cuerpo_se_busca_si_se_pide():
    criterios = parse_search_query("factura", buscar_en_contenido=True)
    assert 'BODY "factura"' in criterios


def test_operador_contenido_explicito():
    """Quien escribe `contenido:` sabe lo que pide."""
    assert parse_search_query("contenido:factura") == ["BODY", '"factura"']


def test_dominio_mira_remitente_y_destinatario():
    criterios = parse_search_query("dominio:andes.com.ec")
    assert criterios == ["OR", "FROM", '"@andes.com.ec"', "TO", '"@andes.com.ec"']


def test_dominio_admite_arroba_delante():
    """«@maquita.org» y «maquita.org» son lo mismo para quien busca."""
    assert parse_search_query("dominio:@maquita.org") == parse_search_query("dominio:maquita.org")


def test_solo_remitentes_de_un_dominio():
    assert parse_search_query("de-dominio:andes.com.ec") == ["FROM", '"@andes.com.ec"']


def test_rango_de_fechas_de_una_vez():
    criterios = parse_search_query("entre:2026-01-01..2026-03-31")
    assert criterios == ["SINCE", "01-Jan-2026", "BEFORE", "31-Mar-2026"]


def test_rango_con_fecha_ilegible_no_revienta():
    """Media fecha mal escrita no debe tumbar la búsqueda entera."""
    criterios = parse_search_query("entre:vaya..2026-03-31")
    assert criterios == ["BEFORE", "31-Mar-2026"]


def test_atajos_de_fecha():
    """Lo que uno recuerda es «era de esta semana», no una fecha."""
    for atajo in ("hoy", "ayer", "semana", "mes", "trimestre", "año"):
        criterios = parse_search_query(atajo)
        assert criterios[0] == "SINCE", f"«{atajo}» debería acotar por fecha"


def test_se_combinan_sin_tocar_el_cuerpo():
    criterios = parse_search_query("dominio:maquita.org mes tiene:adjunto")
    juntos = " ".join(criterios)
    assert "BODY" not in juntos
    assert "@maquita.org" in juntos
    assert "SINCE" in juntos
    assert "multipart/mixed" in juntos


def test_busqueda_vacia_devuelve_todo():
    assert parse_search_query("") == ["ALL"]
    assert parse_search_query("   ") == ["ALL"]


def test_los_operadores_en_espanol_siguen_valiendo():
    assert parse_search_query("asunto:factura") == ["SUBJECT", '"factura"']
    assert parse_search_query("de:ana") == ["FROM", '"ana"']
