"""Configuración de Tareas: guardar solo las opciones que cambian (05/11/2026).

«Avisos por correo» también se cambia desde «Compartir lista»; si la ⚙ reenviaba su copia vieja, lo desactivaba.
"""

from __future__ import annotations

import asyncio
import json

import pytest
from pydantic import ValidationError

from app.tasks import ajustes


class _DB:
    """Doble mínimo: guarda `ajustes` (JSONB) y `avisos_correo` como lo haría la tabla."""

    def __init__(self, guardados=None, avisos=False):
        self.guardados, self.avisos, self.sql = dict(guardados or {}), avisos, []

    async def execute(self, sql, *a):
        self.sql.append(sql)
        if "avisos_correo" in sql:
            self.avisos = a[1]
        else:
            assert "||" in sql  # se une con lo guardado, no se reemplaza
            self.guardados.update(json.loads(a[1]))

    async def fetchrow(self, sql, *a):
        return {"avisos_correo": self.avisos, "ajustes": json.dumps(self.guardados)}


def _cambiar(db, **cambio):
    return asyncio.run(
        ajustes.cambiar(db, "ana@example.org", ajustes.CambioAjustes(**cambio))
    )


def test_cambiar_una_opcion_no_toca_avisos_por_correo():
    db = _DB({"importantes_arriba": True}, avisos=True)
    a = _cambiar(db, sonido_completar=False)
    assert a.avisos_correo is True
    assert a.importantes_arriba is True and a.sonido_completar is False
    assert not any("avisos_correo" in s for s in db.sql)


def test_avisos_por_correo_se_guarda_aparte():
    db = _DB()
    a = _cambiar(db, avisos_correo=True)
    assert a.avisos_correo is True
    assert "avisos_correo" not in db.guardados


def test_nulo_no_borra_lo_guardado():
    db = _DB({"confirmar_eliminar": False})
    assert _cambiar(db, confirmar_eliminar=None).confirmar_eliminar is False


def test_listas_ocultas_se_limpian():
    db = _DB()
    a = _cambiar(db, listas_ocultas=["flagged", "my-day", "planned"])
    assert a.listas_ocultas == ["planned", "flagged"]
    with pytest.raises(ValidationError):
        ajustes.CambioAjustes(listas_ocultas=["a", "b", "c", "d", "e"])


def test_el_cuerpo_completo_de_antes_sigue_valiendo():
    db = _DB()
    a = _cambiar(db, **ajustes.Ajustes(importantes_arriba=True).model_dump())
    assert a.importantes_arriba is True and a.confirmar_eliminar is True
