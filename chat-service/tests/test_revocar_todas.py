# -*- coding: utf-8 -*-
"""Cerrar «todas las sesiones» tiene que cerrarlas de verdad (aviso de Andes, instalación limpia).

Lo peor en seguridad es creerse protegido sin estarlo: el cuerpo que documentaba la guía
respondía 200 y dejaba la sesión viva.
"""
import pytest

from interfaces.api import sesion_central as sc


@pytest.fixture(autouse=True)
def limpio():
    sc._memoria.clear()
    yield
    sc._memoria.clear()


def test_todas_sin_generacion_revoca_todo():
    sc.registrar_revocacion(7, "*")
    assert sc.sesion_revocada(7, "sid-A", 0, nacida=1.0) is True
    assert sc.sesion_revocada(7, "sid-B", 99, nacida=1.0) is True


def test_cuerpo_de_la_guia_con_av_cero_tambien_revoca():
    """`{"user": …, "sid": "*"}` llega con av 0 o ausente: las dos formas revocan."""
    sc.registrar_revocacion(8, "*", 0)
    assert sc.sesion_revocada(8, "sid-A", 5, nacida=1.0) is True


def test_con_generacion_se_conserva_el_corte_fino():
    sc.registrar_revocacion(9, "*", 4)
    assert sc.sesion_revocada(9, "sid-A", 3, nacida=1.0) is True     # anterior: fuera
    assert sc.sesion_revocada(9, "sid-A", 4, nacida=1.0) is False    # igual o posterior: sigue
    assert sc.sesion_revocada(9, "sid-A", 7, nacida=1.0) is False


def test_una_sesion_concreta_no_afecta_a_las_demas():
    sc.registrar_revocacion(10, "sid-A")
    assert sc.sesion_revocada(10, "sid-A", 1, nacida=1.0) is True
    assert sc.sesion_revocada(10, "sid-B", 1, nacida=1.0) is False


def test_quien_no_tiene_revocaciones_sigue_dentro():
    assert sc.sesion_revocada(11, "sid-A", 1, nacida=1.0) is False
