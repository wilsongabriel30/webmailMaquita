"""H-01: la contraseña inicial aleatoria cumple las reglas y no hay clave conocida en el código."""

import re

from app.auth import bootstrap
from app.auth.password import validate_password_strength


def test_clave_inicial_cumple_reglas_y_es_distinta_cada_vez():
    claves = {bootstrap.clave_inicial_aleatoria() for _ in range(20)}
    assert len(claves) == 20
    for c in claves:
        assert validate_password_strength(c, "u@example.com") is None, c
        assert not re.search(r"[0O1lI]", c)


def test_no_queda_clave_conocida_en_el_codigo():
    import pathlib

    raiz = pathlib.Path(__file__).resolve().parents[1] / "app"
    for f in raiz.rglob("*.py"):
        assert "Cambiar2026" not in f.read_text(encoding="utf-8"), f
