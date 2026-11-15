"""Texto libre de la búsqueda: cada palabra por separado y en cualquier parte del correo."""

from app.mail import busqueda_palabras as bp
from app.mail.search_advanced import _entrecomillar, parse_search_query


def _t(criterios):
    return " ".join(criterios)


def test_dos_palabras_pueden_estar_en_campos_distintos():
    """«ana factura»: Ana en el remitente y «factura» en el asunto es un acierto."""
    t = _t(parse_search_query("ana factura", con_indice=True))
    assert 'FROM "ana"' in t and 'SUBJECT "factura"' in t
    assert '"ana factura"' not in t, "ya no se busca todo junto como una sola cadena"
    for campo in ("FROM", "TO", "CC", "SUBJECT", "BODY"):
        assert f'{campo} "ana"' in t and f'{campo} "factura"' in t


def test_la_copia_tambien_cuenta():
    assert 'CC "ana"' in _t(parse_search_query("ana", con_indice=True))


def test_sin_indice_no_entra_en_el_cuerpo():
    t = _t(parse_search_query("ana factura"))
    assert "BODY" not in t and "TEXT" not in t
    assert 'SUBJECT "ana"' in t and 'SUBJECT "factura"' in t


def test_no_se_usa_text():
    """TEXT mira también las cabeceras técnicas y llena los resultados de ruido."""
    assert "TEXT" not in _t(parse_search_query("informe mensual", con_indice=True))


def test_una_frase_entre_comillas_sigue_junta():
    t = _t(parse_search_query('"informe mensual" octubre', con_indice=True))
    assert 'SUBJECT "informe mensual"' in t and 'SUBJECT "octubre"' in t


def test_palabras_vacias_y_signos_sueltos_no_cuentan():
    assert bp.terminos(["informe", "de", "-", "seguimiento", "(1)"]) == [
        "informe",
        "seguimiento",
    ]
    assert bp.terminos(["de", "la"]) == [
        "de",
        "la",
    ], "si solo hay palabras vacías, se busca lo escrito"
    assert bp.terminos(["Ana", "ana", "ANA"]) == ["Ana"]
    assert bp.terminos(["-", "—", "()"]) == []


def test_un_asunto_pegado_con_signos_no_se_queda_en_cero():
    t = _t(
        parse_search_query("Informe de seguimiento - COOPERACIÓN (1)", con_indice=True)
    )
    assert 'SUBJECT "-"' not in t and 'SUBJECT "de"' not in t
    assert 'SUBJECT "COOPERACIÓN"' in t


def test_hay_un_tope_de_palabras():
    assert len(bp.terminos([f"palabra{i}" for i in range(30)])) == bp.MAX_TERMINOS


def test_con_personas_el_grupo_de_palabras_va_entre_parentesis():
    c = bp.criterio(
        ["ronald", "leon"], True, ["ronald.leon@example.org"], _entrecomillar
    )
    t = _t(c)
    assert t.endswith('CC "ronald.leon@example.org"')
    assert c[:3] == ["OR", "OR", "OR"] and c[3].startswith("(") and c[3].endswith(")")


def test_se_combina_con_operadores():
    t = _t(parse_search_query("despues:2026-01-01 ana factura", con_indice=True))
    assert t.startswith("SINCE 01-Jan-2026 ") and 'FROM "factura"' in t


def test_las_comillas_del_usuario_siguen_escapadas():
    """Una comilla escrita por la persona no puede cerrar la cadena y colar un criterio."""
    criterios = parse_search_query('ana" ALL "x', con_indice=True)
    assert "ALL" not in criterios
    assert all(c == "OR" or c.count('"') - c.count('\\"') == 2 for c in criterios)


def test_las_tildes_no_cuentan_al_buscar_personas():
    """En remitente y destinatarios el índice no quita las tildes: se buscan las variantes."""
    assert bp.variantes("raices")[:2] == [
        "raices",
        "ráices",
    ] and "raíces" in bp.variantes("raices")
    assert "bárbara" in bp.variantes("barbara") and "barbara" in bp.variantes("Bárbara")
    assert "muñoz" in bp.variantes("munoz") and "núñez" in bp.variantes("nunez")
    assert bp.variantes("2026") == ["2026"] and bp.variantes("ana@example.org") == [
        "ana@example.org"
    ]
    assert len(bp.variantes("hernandezfernandez")) <= bp.MAX_VARIANTES
    t = _t(parse_search_query("raices", con_indice=True))
    assert 'FROM "raíces"' in t and 'CC "raíces"' in t
    assert (
        'SUBJECT "raíces"' not in t
    ), "en asunto y cuerpo el índice ya quita las tildes"


def test_un_trozo_de_una_letra_no_anula_el_termino():
    """«T-53» daba cero: la «T» suelta no está en el índice y arrastraba al «53»."""
    assert bp.terminos(["T-53"]) == ["53"]
    assert bp.terminos(["001-001-000123"]) == ["001 001 000123"]
    assert bp.terminos(["ana.perez@example.org"]) == ["ana.perez@example.org"]
    assert bp.terminos(["informe_final.pdf"]) == ["informe final.pdf"]
    assert bp.terminos(["a"]) == ["a"], "si es lo único escrito, se busca"


def test_los_operadores_de_persona_tambien_ignoran_las_tildes():
    t = _t(parse_search_query("de:barbara", con_indice=True))
    assert 'FROM "bárbara"' in t and 'OR FROM "barbara" (' in t
    assert 'TO "muñoz"' in _t(parse_search_query("para:munoz"))
    assert 'CC "garcía"' in _t(parse_search_query("copia:garcia"))


def test_valor_con_coma_o_punto_se_busca_entero():
    """«205,6» buscaba solo «205» (el trozo de una cifra se descartaba): miles de correos."""
    assert bp.terminos(["205,6"]) == ["205.6"] == bp.terminos(["205.6"])
    assert bp.terminos(["$1.250,00"]) == ["1.250.00"]
    assert bp.terminos(["205,6", "205.6"]) == [
        "205.6"
    ], "coma y punto son el mismo valor"
    t = _t(parse_search_query("205,6", con_indice=True))
    assert 'BODY "205.6"' in t and 'SUBJECT "205.6"' in t and '"205"' not in t


def test_lo_que_no_es_un_valor_se_parte_como_antes():
    assert bp.terminos(["T-53"]) == ["53"]
    assert bp.terminos(["informe_final"]) == ["informe final"]
    assert bp.terminos(["ana.perez@example.org"]) == ["ana.perez@example.org"]


def test_solo_encabezados_no_entra_en_el_cuerpo():
    """El nivel 1 de los resultados: todas las palabras en remitente, para, copia o asunto."""
    detalle = {}
    t = _t(
        parse_search_query(
            "ana factura de:luis",
            con_indice=True,
            solo_encabezados=True,
            detalle=detalle,
        )
    )
    assert detalle["libres"] == ["ana", "factura"]
    for campo in ("FROM", "TO", "CC", "SUBJECT"):
        assert f'{campo} "ana"' in t and f'{campo} "factura"' in t
    assert 'BODY "ana"' not in t and 'BODY "factura"' not in t
    assert 'CC "ana"' in _t(parse_search_query("ana", solo_encabezados=True))
