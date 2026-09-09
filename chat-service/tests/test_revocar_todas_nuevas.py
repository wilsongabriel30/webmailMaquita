# -*- coding: utf-8 -*-
"""Cerrar todas las sesiones no puede impedir volver a entrar (aviso 9-bis de Andes)."""
import pytest

from interfaces.api import sesion_central as sc


@pytest.fixture(autouse=True)
def limpio():
    sc._memoria.clear()
    yield
    sc._memoria.clear()


def test_las_abiertas_caen_y_las_nuevas_entran():
    sc.registrar_revocacion(7, "*", ahora=1000.0)
    assert sc.sesion_revocada(7, "sid-vieja", 0, nacida=999.0) is True     # abierta antes
    assert sc.sesion_revocada(7, "sid-nueva", 0, nacida=1001.0) is False   # entra después


def test_la_del_mismo_instante_se_considera_abierta():
    sc.registrar_revocacion(8, "*", ahora=500.0)
    assert sc.sesion_revocada(8, "sid", 0, nacida=500.0) is True


def test_sin_saber_cuando_nacio_se_rechaza():
    """Fallo cerrado: una sesión anterior al cambio no trae ese dato."""
    sc.registrar_revocacion(9, "*", ahora=100.0)
    assert sc.sesion_revocada(9, "sid", 0) is True


def test_la_marca_antigua_sigue_entendiendose():
    sc._poner("chat:revocado:11", sc.TODAS, 60)
    assert sc.sesion_revocada(11, "sid", 0, nacida=9999.0) is True


def test_con_generacion_se_conserva_el_corte_fino():
    sc.registrar_revocacion(12, "*", 4)
    assert sc.sesion_revocada(12, "sid", 3, nacida=9999.0) is True
    assert sc.sesion_revocada(12, "sid", 4, nacida=1.0) is False


def test_una_sesion_concreta_no_afecta_a_las_demas():
    sc.registrar_revocacion(13, "sid-A")
    assert sc.sesion_revocada(13, "sid-A", 1, nacida=1.0) is True
    assert sc.sesion_revocada(13, "sid-B", 1, nacida=1.0) is False
