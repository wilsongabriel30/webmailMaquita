# -*- coding: utf-8 -*-
"""El chat vive sin nómina: mirar una conversación no puede depender de una foto."""
import pytest

from interfaces.api import nomina_opcional as n


@pytest.fixture(autouse=True)
def limpio():
    n.reiniciar_cache()
    yield
    n.reiniciar_cache()


def test_con_nomina_la_consulta_trae_la_foto_de_la_ficha():
    sql = n.consulta_remitentes(True)
    assert "LEFT JOIN trabajadores" in sql
    assert "foto_trabajador" in sql


def test_sin_nomina_la_consulta_no_nombra_la_tabla():
    """El fallo que se corrige: sin nómina, la consulta con JOIN daba 500."""
    sql = n.consulta_remitentes(False)
    assert "trabajadores" not in sql
    assert "foto_trabajador" in sql          # la columna sigue, vacía, para no tocar el resto


def test_se_pregunta_una_sola_vez():
    llamadas = []

    def ejecutar(sql):
        llamadas.append(sql)
        return True

    assert n.hay_nomina(ejecutar) is True
    assert n.hay_nomina(ejecutar) is True
    assert len(llamadas) == 1


def test_si_la_comprobacion_falla_se_asume_que_no_hay():
    def revienta(sql):
        raise RuntimeError("no existe information_schema")

    assert n.hay_nomina(revienta) is False


def test_esquema_sin_nomina_responde_que_no():
    assert n.hay_nomina(lambda sql: False) is False


def test_reiniciar_cache_vuelve_a_preguntar():
    n.hay_nomina(lambda sql: True)
    n.reiniciar_cache()
    llamadas = []
    n.hay_nomina(lambda sql: llamadas.append(sql) or False)
    assert len(llamadas) == 1
