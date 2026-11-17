"""Correspondencia con una persona: lo directo, sin las copias (busqueda_persona.py)."""

from __future__ import annotations

import pytest

from app.mail import busqueda_palabras
from app.mail.search_advanced import parse_search_query

YO = ("yo@example.org",)


@pytest.fixture
def sin_tildes(monkeypatch):
    """Deja fuera las variantes acentuadas para poder comparar el criterio entero."""
    monkeypatch.setattr(busqueda_palabras, "variantes", lambda v: [v])


def _texto(consulta: str, mias=YO) -> str:
    return " ".join(parse_search_query(consulta, mis_direcciones=mias))


def test_directo_trae_los_dos_sentidos_y_exige_estar_en_para(sin_tildes):
    t = _texto("directo:mariana")
    assert t == (
        'OR (FROM "mariana" TO "yo@example.org") '
        '(FROM "yo@example.org" TO "mariana")'
    )
    assert "CC" not in t


def test_me_envio_es_solo_lo_que_la_persona_me_mando_a_mi(sin_tildes):
    assert _texto("meenvio:mariana") == '(FROM "mariana" TO "yo@example.org")'


def test_le_envie_es_solo_lo_que_yo_le_mande(sin_tildes):
    assert _texto("leenvie:mariana") == '(FROM "yo@example.org" TO "mariana")'


def test_con_incluye_tambien_las_copias(sin_tildes):
    assert _texto("con:mariana") == ('OR FROM "mariana" OR TO "mariana" CC "mariana"')


def test_con_adjunto_sigue_siendo_el_filtro_de_adjuntos():
    assert _texto("con:adjunto") == 'HEADER Content-Type "multipart/mixed"'


def test_las_variantes_con_tilde_entran_en_el_mismo_criterio():
    t = _texto("meenvio:barbara")
    assert 'FROM "barbara"' in t and 'FROM "bárbara"' in t
    assert t.startswith("((OR ") and t.endswith('TO "yo@example.org")')
    assert t.count("yo@example.org") == 1


def test_sin_saber_quien_busca_se_queda_en_remitente_y_destinatario(sin_tildes):
    assert _texto("directo:mariana", mias=()) == ('OR (FROM "mariana") (TO "mariana")')


def test_se_combina_con_fecha_y_adjunto(sin_tildes):
    t = _texto("directo:mariana tiene:adjunto despues:2026-01-01")
    assert "SINCE 01-Jan-2026" in t and "multipart/mixed" in t
    assert t.startswith('OR (FROM "mariana"')


def test_las_comillas_de_lo_escrito_no_rompen_el_criterio():
    t = _texto('directo:a\\"b')
    assert "ALL" not in t


def test_varias_palabras_valen_en_cualquier_orden(sin_tildes):
    # «Mariana López» también encuentra «López Paredes, Mariana»: cada palabra por separado.
    assert _texto('meenvio:"mariana lopez"') == (
        '((FROM "mariana" FROM "lopez") TO "yo@example.org")'
    )
    assert _texto('con:"mariana lopez"').count('"mariana lopez"') == 0


def test_lo_enviado_a_un_alias_propio_tambien_es_a_mi(sin_tildes):
    t = _texto("directo:mariana", mias=("yo@example.org", "soporte@example.org"))
    assert t == (
        'OR (FROM "mariana" (OR TO "yo@example.org" TO "soporte@example.org")) '
        '((OR FROM "yo@example.org" FROM "soporte@example.org") TO "mariana")'
    )


def test_solo_se_piden_los_alias_cuando_la_busqueda_los_usa():
    from app.mail import busqueda_persona

    assert busqueda_persona.usa_operador("directo:mariana factura")
    assert busqueda_persona.usa_operador("LEENVIE:ana")
    assert not busqueda_persona.usa_operador("con:mariana de:ana factura")


def test_operador_sin_valor_no_anade_nada():
    assert _texto("directo:") == "ALL"


def test_en_ingles_es_lo_mismo():
    assert _texto("direct:mariana") == _texto("directo:mariana")
    assert _texto("with:mariana") == _texto("con:mariana")
