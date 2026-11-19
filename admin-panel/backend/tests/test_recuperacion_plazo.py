"""Plazo para recuperar correos en el panel: validación y lectura del .env del correo."""

from app.recuperacion_plazo import reglas


def test_valores_validos():
    assert reglas.validar(60, 0) is None  # leído 1 h, sin leer sin límite
    assert reglas.validar(0, 0) is None  # lo leído no se recupera, sin leer sin límite
    assert reglas.validar(60, 2880) is None
    assert reglas.validar(120, 120) is None


def test_fuera_de_rango_o_incoherente():
    assert "ya leídos" in reglas.validar(-1, 0)
    assert "sin leer" in reglas.validar(60, reglas.MAXIMO + 1)
    assert "no puede ser mayor" in reglas.validar(180, 60)


def test_lee_el_plazo_del_env_del_correo():
    assert reglas.del_archivo("# x\nRECALL_MAX_MINUTOS=90\nOTRA=1\n") == {
        "minutos_leidos": 90,
        "minutos_sin_leer": 0,
    }


def test_sin_variable_o_con_basura_rige_el_valor_por_defecto():
    assert reglas.del_archivo("OTRA=1\n")["minutos_leidos"] == 60
    assert reglas.del_archivo("RECALL_MAX_MINUTOS=abc\n")["minutos_leidos"] == 60
