"""«de:persona» incluye lo que esa persona escribió y otro reenvió (solo con índice de texto)."""

from __future__ import annotations

from app.mail import busqueda_reenviados as br
from app.mail.search_advanced import parse_search_query


def _texto(criterios) -> str:
    return " ".join(criterios)


def test_con_indice_de_incluye_los_reenviados_que_mencionan_a_la_persona():
    t = _texto(parse_search_query("de:daniel", con_indice=True))
    assert 'OR FROM "daniel" (' in t and 'BODY "daniel")' in t
    for marca in br.MARCAS:
        assert f'SUBJECT "{marca}"' in t


def test_sin_indice_de_sigue_siendo_solo_el_remitente():
    t = _texto(parse_search_query("de:daniel", con_indice=False))
    assert 'FROM "daniel"' in t and "BODY" not in t and "SUBJECT" not in t


def test_from_en_ingles_se_comporta_igual():
    assert _texto(parse_search_query("from:daniel", con_indice=True)) == _texto(
        parse_search_query("de:daniel", con_indice=True)
    )


def test_se_combina_con_otros_filtros():
    t = _texto(parse_search_query("de:daniel asunto:factura", con_indice=True))
    assert 'OR FROM "daniel" (' in t and 'SUBJECT "factura"' in t


def test_operador_reenviado_solo_trae_reenviados():
    t = _texto(parse_search_query("reenviado:daniel", con_indice=True))
    assert t.startswith("(") and 'BODY "daniel")' in t and "FROM" not in t


def test_el_grupo_de_marcas_esta_bien_formado():
    grupo = br.solo_reenviados('"x"')
    assert (
        grupo.count("OR") == len(br.MARCAS) - 1
        and grupo.startswith("(OR")
        and grupo.endswith('BODY "x")')
    )


def test_las_comillas_del_valor_no_rompen_el_criterio():
    t = _texto(parse_search_query('de:"ana perez"', con_indice=True))
    assert t.count("(") == t.count(")") and 'FROM "ana perez"' in t
