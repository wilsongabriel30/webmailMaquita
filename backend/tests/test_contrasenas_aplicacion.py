"""D-5: contraseñas de aplicación. La verificación vive en Dovecot + SQL (prueba en producción con
`doveadm auth test -x rip=...`); aquí se prueba lo que genera y acepta el backend."""

import os
import re

from app.auth import contrasenas_aplicacion as ca

MIGRACION = os.path.join(
    os.path.dirname(__file__),
    "..",
    "..",
    "migrations",
    "2026-09-07-contrasenas-aplicacion.sql",
)


def test_formato_legible_y_sin_ambiguos():
    for _ in range(200):
        clave = ca.generar()
        assert re.fullmatch(
            r"[a-z2-9]{4}-[a-z2-9]{4}-[a-z2-9]{4}-[a-z2-9]{4}", clave
        ), clave
        assert not set(clave) & set("01oli")


def test_no_se_repite():
    assert len({ca.generar() for _ in range(500)}) == 500


def test_limpiar_acepta_con_y_sin_guiones():
    assert ca.limpiar("abcd-efgh-jkmn-pqrs") == "abcdefghjkmnpqrs"
    assert ca.limpiar("abcd efgh jkmn pqrs") == "abcdefghjkmnpqrs"
    assert len(ca.limpiar(ca.generar())) == 16


def test_migracion_verifica_en_sql_y_excluye_el_propio_servidor():
    sql = open(MIGRACION, encoding="utf-8").read()
    assert "CREATE OR REPLACE FUNCTION verificar_contrasena_aplicacion" in sql
    assert "crypt(limpia, c.hash)" in sql and "{BLF-CRYPT}" in sql
    assert "('127.0.0.1', '::1')" in sql  # desde el webmail solo vale la principal
    assert (
        "'contrasenas_aplicacion_obligatorias', 'false'" in sql
    )  # se activa a propósito, no al instalar
