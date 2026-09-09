# -*- coding: utf-8 -*-
"""Una instalación no puede nacer sin las columnas que el código lee."""
import pytest

from columnas_faltantes import columnas_a_anadir, plan, sentencia

MODELO = [("cleared_at", "timestamptz", True), ("last_read_message_id", "bigint", True)]


def test_detecta_la_que_falta():
    faltan = columnas_a_anadir(MODELO, ["id", "user_id", "last_read_message_id"])
    assert [f[0] for f in faltan] == ["cleared_at"]


def test_si_no_falta_ninguna_no_hay_nada_que_hacer():
    assert plan("chat_participants", MODELO, ["cleared_at", "last_read_message_id"]) == []


def test_no_se_confunde_por_mayusculas_ni_espacios():
    assert columnas_a_anadir(MODELO, [" Cleared_At ", "last_read_message_id"]) == []


def test_la_sentencia_es_idempotente():
    s = sentencia("chat_participants", "cleared_at", "timestamptz")
    assert "ADD COLUMN IF NOT EXISTS" in s
    assert s.startswith("ALTER TABLE chat_participants")


def test_nunca_una_columna_obligatoria_sobre_datos_existentes():
    with pytest.raises(ValueError):
        sentencia("chat_participants", "algo", "text", admite_nulos=False)


def test_el_plan_sale_en_orden_y_completo():
    p = plan("chat_participants", MODELO, ["id"])
    assert len(p) == 2
    assert "cleared_at timestamptz" in p[0]
    assert "last_read_message_id bigint" in p[1]
