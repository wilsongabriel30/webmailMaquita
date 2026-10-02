"""Asignaciones de cuentas: los dos extremos tienen que estar en el alcance del administrador."""

import pytest
from fastapi import HTTPException

from app.asignaciones import par_valido

UNO = {"dominios": ["uno.example"]}
DOS = {"dominios": ["uno.example", "dos.example"]}


def test_mismo_dominio_pasa_y_normaliza():
    assert par_valido(UNO, " Ventas@Uno.example ", "ana@uno.example") == ("ventas@uno.example", "ana@uno.example")


def test_varios_dominios_puede_cruzar():
    assert par_valido(DOS, "ventas@dos.example", "ana@uno.example") == ("ventas@dos.example", "ana@uno.example")


@pytest.mark.parametrize("cuenta, persona", [
    ("ventas@dos.example", "ana@uno.example"),   # cuenta ajena
    ("ventas@uno.example", "ana@dos.example"),   # persona ajena
    ("ventas@tres.example", "ana@uno.example"),
])
def test_un_extremo_ajeno_da_404(cuenta, persona):
    with pytest.raises(HTTPException) as e:
        par_valido(UNO, cuenta, persona)
    assert e.value.status_code == 404


def test_administrador_de_dos_no_alcanza_un_tercero():
    with pytest.raises(HTTPException) as e:
        par_valido(DOS, "ventas@tres.example", "ana@uno.example")
    assert e.value.status_code == 404


@pytest.mark.parametrize("cuenta, persona", [
    ("ana@uno.example", "ana@uno.example"), ("ANA@uno.example", "ana@uno.example"),
    ("sin-arroba", "ana@uno.example"), ("ventas@uno.example", None), ("a@uno.example\nBcc: x@y.z", "ana@uno.example"),
])
def test_entradas_malas_dan_400(cuenta, persona):
    with pytest.raises(HTTPException) as e:
        par_valido(UNO, cuenta, persona)
    assert e.value.status_code == 400
