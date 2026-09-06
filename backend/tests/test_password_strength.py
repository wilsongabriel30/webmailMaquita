"""Tests del validador de fortaleza de contraseña (app.auth.password)."""

from app.auth.password import validate_password_strength as v


def test_rechaza_repetidos():
    # 4+ caracteres iguales seguidos deben rechazarse (regresion: la regla estaba muerta por un byte \x01)
    assert v("aaaa1111Bb!!") is not None
    assert v("1111aaaaBb!!") is not None
    assert v("Hooooola2026!") is not None


def test_acepta_buena():
    assert v("Holamundo2026!") is None
    assert v("Maquita$2026seguro") is None


def test_reglas_basicas():
    assert v("corta1!") is not None  # < 10
    assert v("holamundo2026!") is not None  # sin mayuscula
    assert v("HOLAMUNDO2026!") is not None  # sin minuscula
    assert v("Holamundoxxx!") is not None  # sin numero
    assert v("Holamundo2026") is not None  # sin simbolo
    assert v("Holamundo2026!", username="holamundo") is not None  # contiene usuario
