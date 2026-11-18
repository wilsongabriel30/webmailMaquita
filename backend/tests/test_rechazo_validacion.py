"""El registro de una solicitud rechazada dice el campo y el motivo, nunca el valor."""

from app.core import rechazo_validacion as rv


def test_dice_campo_tipo_y_largo_pero_no_el_valor():
    errores = [
        {
            "loc": ("body", "to", 0),
            "type": "value_error",
            "msg": "value is not a valid email address",
            "input": "secreto@example.org ",
        },
        {
            "loc": ("body", "html_body"),
            "type": "string_too_long",
            "msg": "String should have at most 10 characters",
            "input": "x" * 5000,
        },
    ]
    texto = rv.resumen(errores)
    assert "to.0: value_error" in texto
    assert "html_body: string_too_long" in texto and "largo=5000" in texto
    assert "secreto" not in texto and "xxxx" not in texto


def test_muchos_fallos_se_resumen():
    errores = [
        {"loc": ("body", f"c{i}"), "type": "missing", "msg": "Field required"}
        for i in range(12)
    ]
    texto = rv.resumen(errores)
    assert texto.count("missing") == rv.MAX_FALLOS and texto.endswith("y 4 más")


def test_sin_errores_no_falla():
    assert rv.resumen([]) == "sin detalle"
    rv.anotar(object(), object())  # nunca lanza
