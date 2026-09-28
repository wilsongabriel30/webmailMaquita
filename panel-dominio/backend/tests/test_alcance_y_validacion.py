"""El administrador de dominio solo alcanza lo suyo: rutas, direcciones y validaciones."""

import pytest
from fastapi import HTTPException

from app.alcance import exigir_alcance
from app.validacion import (
    CUOTA_POR_DEFECTO, GIB, cuota_permitida, destinos_de_alias, exigir_clave_fuerte, normalizar_direccion, texto_limpio,
)

ADMIN = {"role": "admin_dominio", "dominios": ["uno.example"]}


def test_direccion_propia_pasa():
    assert exigir_alcance(ADMIN, "ana@uno.example") == "uno.example"


@pytest.mark.parametrize("direccion", [
    "ana@dos.example", "ana@sub.uno.example", "ana@uno.example.dos.example", "ana", "", "ana@uno.example@dos.example",
])
def test_direccion_ajena_da_404(direccion):
    with pytest.raises(HTTPException) as e:
        exigir_alcance(ADMIN, direccion)
    assert e.value.status_code == 404


@pytest.mark.parametrize("mala", [
    "sin-arroba", "a@@b.example", "a b@uno.example", "../x@uno.example", "a@uno.example\nBcc: x@y.z",
    ".a@uno.example", "a..b@uno.example", "a@", "%@uno.example", "a'--@uno.example",
])
def test_direcciones_invalidas(mala):
    with pytest.raises(HTTPException):
        normalizar_direccion(mala)


def test_direccion_se_normaliza():
    assert normalizar_direccion("  Ana.Perez@UNO.example ") == "ana.perez@uno.example"


@pytest.mark.parametrize("clave", ["corta1A", "todominusculas", "12345678901", "ana.perez.2026X"])
def test_claves_debiles(clave):
    with pytest.raises(HTTPException):
        exigir_clave_fuerte(clave, "ana.perez@uno.example")


def test_clave_fuerte():
    assert exigir_clave_fuerte("Cafe-Molido.2026", "ana@uno.example")


def test_cuota():
    assert cuota_permitida(None, 0) == CUOTA_POR_DEFECTO
    assert cuota_permitida(2 * GIB, 0) == 2 * GIB
    assert cuota_permitida(8 * GIB, 10 * GIB) == 8 * GIB
    with pytest.raises(HTTPException):
        cuota_permitida(6 * GIB, 0)
    with pytest.raises(HTTPException):
        cuota_permitida(0, 0)
    # quien ya tenía más la conserva o la baja, pero no la sube
    assert cuota_permitida(None, 0, actual=50 * GIB) == 50 * GIB
    assert cuota_permitida(40 * GIB, 0, actual=50 * GIB) == 40 * GIB
    with pytest.raises(HTTPException):
        cuota_permitida(60 * GIB, 0, actual=50 * GIB)


def test_destinos():
    assert destinos_de_alias("a@uno.example, B@uno.example;a@uno.example") == ["a@uno.example", "b@uno.example"]
    with pytest.raises(HTTPException):
        destinos_de_alias("")


def test_texto_sin_caracteres_de_control():
    assert texto_limpio("Ana\r\nBcc: x") == "Ana  Bcc: x"
