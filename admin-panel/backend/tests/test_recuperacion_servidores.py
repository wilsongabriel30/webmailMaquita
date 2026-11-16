"""Recuperación entre servidores en el panel: dominios de confianza y lectura del .env del correo."""

from app.recuperacion_servidores import dominios as dom


def test_normaliza_sin_repetir_y_en_minusculas():
    validos, rechazados = dom.normalizar(
        [" Socio.ORG ", "@filial.org.", "socio.org", "", "sub.dominio.com.ec"]
    )
    assert validos == ["socio.org", "filial.org", "sub.dominio.com.ec"]
    assert rechazados == []


def test_rechaza_lo_que_no_es_un_dominio():
    validos, rechazados = dom.normalizar(
        ["ana@socio.org", "localhost", "con espacio.org", "-malo.org", "bueno.org"]
    )
    assert validos == ["bueno.org"]
    assert rechazados == ["ana@socio.org", "localhost", "con espacio.org", "-malo.org"]


def test_lee_la_politica_del_env_del_correo():
    env = (
        "# comentario\n"
        "RECALL_MAX_MINUTOS=60\n"
        'RECALL_FEDERADO_DOMINIOS_CONFIANZA="Socio.org, filial.org"\n'
        "RECALL_FEDERADO_RETIRAR_LEIDOS=true\n"
    )
    assert dom.del_archivo(env) == {
        "retirar_leidos": True,
        "dominios_confianza": ["socio.org", "filial.org"],
    }


def test_sin_variables_rige_el_valor_por_defecto():
    assert dom.del_archivo("OTRA=1\n") == {
        "retirar_leidos": False,
        "dominios_confianza": [],
    }
