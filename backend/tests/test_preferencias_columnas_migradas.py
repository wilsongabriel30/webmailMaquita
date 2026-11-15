"""Toda columna de user_preferences que el código escribe tiene que existir en el esquema o en una migración.

El 09/11/2026 se añadió `acuse_lectura` al código y la orden de crear la columna quedó solo en la
documentación: guardar ajustes daba 500 en las demás instalaciones (informe de Andes, 15/11/2026).
"""

from __future__ import annotations

import re
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]


def _columnas_del_esquema() -> set[str]:
    esquema = (RAIZ / "migrations/000_schema.sql").read_text(encoding="utf-8")
    tabla = re.search(
        r"CREATE TABLE IF NOT EXISTS public\.user_preferences \((.*?)\n\);",
        esquema,
        re.S,
    )
    assert tabla, "no se encontró user_preferences en el esquema base"
    columnas = {
        linea.split()[0] for linea in tabla.group(1).splitlines() if linea.strip()
    }
    for archivo in (RAIZ / "migrations").glob("*.sql"):
        columnas.update(
            re.findall(
                r"ALTER TABLE\s+(?:ONLY\s+)?(?:public\.)?user_preferences\s+ADD COLUMN\s+(?:IF NOT EXISTS\s+)?(\w+)",
                archivo.read_text(encoding="utf-8"),
                re.I,
            )
        )
    return columnas


def _columnas_que_escribe_el_codigo() -> set[str]:
    usadas: set[str] = set()
    for archivo in (RAIZ / "backend/app").rglob("*.py"):
        texto = archivo.read_text(encoding="utf-8")
        for lista in re.findall(
            r"INSERT INTO user_preferences\s*\(([^)]*)\)", texto, re.I
        ):
            usadas.update(c.strip() for c in lista.split(",") if c.strip())
    return usadas


def test_las_columnas_que_se_guardan_existen_en_las_migraciones():
    usadas = _columnas_que_escribe_el_codigo()
    assert "acuse_lectura" in usadas  # la prueba mira donde debe
    assert usadas - _columnas_del_esquema() == set()
