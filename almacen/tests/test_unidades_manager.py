# -*- coding: utf-8 -*-
"""F-11: una unidad compartida no puede quedarse sin manager."""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "servicio"))
import gobierno_unidad as gu  # noqa: E402


class _Cur:
    def __init__(self, bd):
        self.bd, self._filas, self.bloqueos = bd, [], 0

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def execute(self, sql, params=()):
        s = " ".join(sql.split())
        if s.startswith("SELECT usuario_id, rol FROM unidad_miembros"):
            assert s.endswith("FOR UPDATE")
            self.bloqueos += 1
            self._filas = [(u, r) for (un, u), r in self.bd.items() if un == params[0]]
        elif s.startswith("INSERT INTO unidad_miembros"):
            self.bd[(params[0], params[1])] = params[2]
        elif s.startswith("DELETE FROM unidad_miembros"):
            self.bd.pop((params[0], params[1]), None)
        else:
            raise AssertionError(s)

    def fetchall(self):
        return self._filas


class _Con:
    def __init__(self, bd):
        self.bd = bd

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def cursor(self):
        return _Cur(self.bd)


def _bd():
    return {(1, 10): "manager", (1, 11): "editor", (1, 12): "manager", (2, 20): "manager"}


def test_managers_restantes():
    assert gu.managers_restantes({10: "manager", 11: "editor"}, excepto=10) == 0
    assert gu.managers_restantes({10: "manager", 12: "manager"}, excepto=10) == 1


def test_degradar_o_quitar_con_otro_manager_pasa():
    bd = _bd()
    gu.asignar_rol(lambda: _Con(bd), 1, 10, "editor")  # queda 12 como manager
    assert bd[(1, 10)] == "editor"
    gu.asignar_rol(lambda: _Con(bd), 1, 10, "manager")  # vuelve a haber dos
    gu.quitar(lambda: _Con(bd), 1, 12)
    assert (1, 12) not in bd and bd[(1, 10)] == "manager"


def test_ultimo_manager_no_se_degrada_ni_se_quita():
    bd = _bd()
    conexion = lambda: _Con(bd)  # noqa: E731
    gu.asignar_rol(conexion, 1, 12, "viewer")  # queda 10 como único manager
    with pytest.raises(gu.UltimoManager):
        gu.asignar_rol(conexion, 1, 10, "editor")
    with pytest.raises(gu.UltimoManager):
        gu.quitar(conexion, 1, 10)
    assert bd[(1, 10)] == "manager"
    # en otra unidad no interfiere
    with pytest.raises(gu.UltimoManager):
        gu.quitar(conexion, 2, 20)


def test_agregar_manager_o_quitar_editor_siempre_pasa():
    bd = _bd()
    conexion = lambda: _Con(bd)  # noqa: E731
    gu.asignar_rol(conexion, 1, 30, "manager")
    gu.quitar(conexion, 1, 11)
    assert bd[(1, 30)] == "manager" and (1, 11) not in bd
    gu.asignar_rol(conexion, 1, 30, "manager")  # mismo rol, sin cambio
