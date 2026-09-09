"""Que el verificador de contraseñas detecte de verdad lo que dice detectar.

El caso que lo motiva es el que reportó Andes: una cuenta con el prefijo `{SHA512-CRYPT}` cuyo
contenido no era formato crypt. Dovecot no puede verificar eso jamás; la persona escribe bien su
contraseña, el servidor dice que no, y nadie sabe por qué. Estuvo un mes sin poder entrar.

Los valores de estas pruebas son inventados y no corresponden a ninguna contraseña real.
"""

import importlib.util
import os

import pytest

# El guion vive en deploy/tools, fuera del backend: dos niveles arriba desde backend/tests.
RUTA = os.path.join(
    os.path.dirname(__file__), "..", "..", "deploy", "tools", "verificar-hashes.py"
)
_spec = importlib.util.spec_from_file_location(
    "verificar_hashes", os.path.abspath(RUTA)
)
verificar_hashes = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(verificar_hashes)
revisar = verificar_hashes.revisar

CRYPT_BIEN = "$6$" + "s" * 16 + "$" + "h" * 86
# 64 bytes de resumen mas 8 de sal, que es lo que lleva un SSHA512 de verdad. La primera
# version de esta prueba se quedaba en 60 y el verificador la rechazaba con razon: el dato
# estaba mal, no el verificador.
SSHA512_BIEN = "UlJSUlJSUlJSUlJSUlJSUlJSUlJSUlJSUlJSUlJSUlJSUlJSUlJSUlJSUlJSUlJSUlJSUlJSUlJSUlJSUlJSUnNhbHNhbHNh"
SSHA512_CORTO = (
    "UlJSUlJSUlJSUlJSUlJSUlJSUlJSUlJSUlJSUlJSUlJSUlJSUlJSUlJSUlJSUlJSUlJSUlJSUlJSUlJS"
)


def test_el_caso_de_andes_se_detecta():
    """Prefijo de crypt sobre un hash que no lo es: es el que dejo a alguien un mes fuera."""
    esquema, problema = revisar("{SHA512-CRYPT}" + SSHA512_BIEN, "SHA512-CRYPT")
    assert esquema == "SHA512-CRYPT"
    assert problema is not None, "esto es justo lo que hay que cazar"
    assert "no empieza por $6$" in problema


def test_un_hash_bueno_no_da_falsa_alarma():
    assert revisar("{SHA512-CRYPT}" + CRYPT_BIEN, "SHA512-CRYPT")[1] is None
    assert revisar("{SSHA512}" + SSHA512_BIEN, "SHA512-CRYPT")[1] is None


def test_sin_prefijo_se_juzga_por_el_esquema_por_omision():
    """Quitarle el prefijo es peor que ponerlo mal: se interpreta con el de por omision."""
    esquema, problema = revisar(SSHA512_BIEN, "SHA512-CRYPT")
    assert esquema == "SHA512-CRYPT"
    assert problema is not None
    assert "no trae prefijo" in problema


def test_sin_prefijo_pero_crypt_de_verdad_esta_bien():
    assert revisar(CRYPT_BIEN, "SHA512-CRYPT")[1] is None


def test_contrasena_vacia():
    for valor in ("", None):
        esquema, problema = revisar(valor, "SHA512-CRYPT")
        assert problema is not None
        assert "no puede entrar" in problema


def test_llave_sin_cerrar():
    esquema, problema = revisar("{SHA512-CRYPT" + CRYPT_BIEN, "SHA512-CRYPT")
    assert problema is not None
    assert "nunca cierra" in problema


def test_prefijo_sin_hash_detras():
    esquema, problema = revisar("{SHA512-CRYPT}", "SHA512-CRYPT")
    assert problema is not None
    assert "no hay hash" in problema


def test_base64_que_no_es_base64():
    esquema, problema = revisar("{SSHA512}esto no es base64!!", "SHA512-CRYPT")
    assert problema is not None
    assert "base64" in problema


def test_base64_demasiado_corto():
    """Un SSHA512 al que le faltan bytes no es un SSHA512, aunque sea base64 valido."""
    esquema, problema = revisar("{SSHA512}" + SSHA512_CORTO, "SHA512-CRYPT")
    assert problema is not None
    assert "bytes" in problema


def test_contrasena_en_claro_se_avisa():
    esquema, problema = revisar("{PLAIN}loquesea", "SHA512-CRYPT")
    assert problema is not None
    assert "legible" in problema


def test_esquema_desconocido_se_avisa_sin_bloquear():
    esquema, problema = revisar("{VAYAUSTEDASABER}abc", "SHA512-CRYPT")
    assert esquema == "VAYAUSTEDASABER"
    assert "desconocido" in problema


@pytest.mark.parametrize(
    "valor",
    [
        "{BLF-CRYPT}$2y$10$" + "x" * 53,
        "{MD5-CRYPT}$1$" + "s" * 8 + "$" + "h" * 22,
        "{CRYPT}$6$" + "s" * 16 + "$" + "h" * 86,
    ],
)
def test_otros_esquemas_validos_no_dan_falsa_alarma(valor):
    assert revisar(valor, "SHA512-CRYPT")[1] is None
