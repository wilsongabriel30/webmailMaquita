# -*- coding: utf-8 -*-
"""El healthz tiene que delatar una instalación a medias, no taparla."""
import pytest

from interfaces.api import estado_salud as s


@pytest.fixture(autouse=True)
def limpio():
    s.olvidar_cache()
    yield
    s.olvidar_cache()


def test_todo_en_su_sitio():
    estado, detalle = s.revisar_base(lambda sql: True)
    assert estado == s.CORRECTO and detalle == ""
    cuerpo, codigo = s.respuesta("chat", True, estado, detalle)
    assert codigo == 200 and cuerpo["estado"] == "ok" and cuerpo["success"] is True


def test_sin_tablas_no_puede_dar_verde():
    """El caso de Andes: semanas respondiendo 200 con las tablas sin crear."""
    estado, detalle = s.revisar_base(lambda sql: False)
    assert estado == s.FALTAN_TABLAS
    assert "migrar_chat.py" in detalle
    cuerpo, codigo = s.respuesta("chat", True, estado, detalle)
    assert codigo == 503 and cuerpo["estado"] == "degradado" and cuerpo["success"] is False


def test_sin_base_lo_dice():
    def revienta(sql):
        raise RuntimeError("conexión rechazada")

    estado, detalle = s.revisar_base(revienta)
    assert estado == s.SIN_CONEXION and "no se pudo consultar" in detalle
    assert s.respuesta("chat", True, estado, detalle)[1] == 503


def test_no_pregunta_a_la_base_en_cada_llamada():
    llamadas = []
    s.revisar_base(lambda sql: llamadas.append(sql) or True, ahora=1000.0)
    s.revisar_base(lambda sql: llamadas.append(sql) or True, ahora=1002.0)
    assert len(llamadas) == 1


def test_pasados_unos_segundos_vuelve_a_preguntar():
    llamadas = []
    s.revisar_base(lambda sql: llamadas.append(sql) or True, ahora=1000.0)
    s.revisar_base(lambda sql: llamadas.append(sql) or True, ahora=1000.0 + s._CACHE_SEG + 1)
    assert len(llamadas) == 2
