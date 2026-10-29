"""Tareas al estilo To Do, F6 (29/10/2026): configuración personal (la ⚙) y panel «Sugerencias».

- Sin nada guardado, valen los valores de fábrica; las claves desconocidas o inválidas no rompen la lectura.
- Solo se pueden ocultar las listas inteligentes ocultables (Mi día y Tareas siempre se ven).
- Las sugerencias piden cuatro grupos y nunca incluyen lo que ya está en Mi día, lo completado ni Seguimiento.
"""

import asyncio
import json

import pytest
from pydantic import ValidationError

from app.tasks import ajustes, sugerencias


class _DB:
    def __init__(self, fila=None):
        self.fila, self.sql = fila, []

    async def fetchrow(self, sql, *a):
        return self.fila

    async def fetch(self, sql, *a):
        self.sql.append(sql)
        # Como asyncpg: tantos valores como parámetros usa la consulta.
        usados = max(i for i in range(1, 10) if f"${i}" in sql)
        assert len(a) == usados, (usados, len(a))
        return []


def _leer(fila):
    return asyncio.run(ajustes.leer(_DB(fila), "ana@x.org"))


def test_de_fabrica_sin_fila():
    a = _leer(None)
    assert a.confirmar_eliminar and a.sonido_completar and not a.importantes_arriba
    assert a.listas_ocultas == [] and not a.avisos_correo


def test_lee_lo_guardado_e_ignora_lo_desconocido():
    a = _leer(
        {
            "avisos_correo": True,
            "ajustes": json.dumps({"importantes_arriba": True, "otra_cosa": 1}),
        }
    )
    assert a.importantes_arriba and a.avisos_correo and a.confirmar_eliminar


def test_valor_guardado_invalido_vuelve_a_fabrica():
    a = _leer({"avisos_correo": False, "ajustes": {"confirmar_eliminar": "quizá"}})
    assert a.confirmar_eliminar is True


def test_solo_se_ocultan_las_ocultables():
    a = ajustes.Ajustes(listas_ocultas=["planned", "my-day", "flagged"]).limpios()
    assert a.listas_ocultas == ["planned", "flagged"]
    with pytest.raises(ValidationError):
        ajustes.Ajustes(listas_ocultas=["a", "b", "c", "d", "e"])


def test_sugerencias_excluyen_mi_dia_completadas_y_seguimiento():
    db = _DB()
    s = asyncio.run(sugerencias.sugerencias(db, "ana@x.org"))
    assert s.vencidas == [] and s.recientes == []
    assert len(db.sql) == 4
    for sql in db.sql:
        assert "NOT tc.completed" in sql and "NOT tc.asignada" in sql
        assert "NOT EXISTS (SELECT 1 FROM task_mi_dia" in sql
