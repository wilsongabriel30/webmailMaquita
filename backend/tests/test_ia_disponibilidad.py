"""La interfaz solo enseña el asistente si la instalación tiene un modelo de IA configurado."""

from app.ai.disponibilidad import hay_modelo


def test_sin_modelo_no_hay_ia():
    assert hay_modelo({"model": ""}) is False
    assert hay_modelo({"model": None}) is False
    assert hay_modelo({"model": "   "}) is False
    assert hay_modelo({}) is False


def test_con_modelo_hay_ia():
    assert hay_modelo({"model": "un-modelo"}) is True
