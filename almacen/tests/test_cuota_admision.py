# -*- coding: utf-8 -*-
"""F-06: la cuota se aplica ANTES de escribir, de forma atómica, y durante el streaming."""
import os
import sys
from contextlib import contextmanager

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "servicio"))
import cuota_admision as ca  # noqa: E402


class _Cursor:
    """Base mínima en memoria: cuotas_uso y cuotas_reservas."""

    def __init__(self, bd):
        self.bd = bd
        self._res = None

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def execute(self, sql, params=()):
        s = " ".join(sql.split())
        if s.startswith("DELETE FROM cuotas_reservas WHERE creada_en"):
            return
        if s.startswith("INSERT INTO cuotas_uso"):
            uid, usado = params[0], params[1]
            if "DO NOTHING" in s:
                self.bd["uso"].setdefault(uid, usado)
            else:
                self.bd["uso"][uid] = max(self.bd["uso"].get(uid, 0) + params[2], 0) if uid in self.bd["uso"] else max(usado, 0)
            return
        if s.startswith("SELECT usado_bytes FROM cuotas_uso"):
            self._res = {"usado_bytes": self.bd["uso"].get(params[0], 0)}
            return
        if s.startswith("SELECT COALESCE(SUM(bytes), 0)"):
            self._res = {"reservado": sum(b for u, b in self.bd["res"].values() if u == params[0])}
            return
        if s.startswith("INSERT INTO cuotas_reservas"):
            self.bd["res"][params[0]] = (params[1], params[2])
            return
        if s.startswith("DELETE FROM cuotas_reservas WHERE id"):
            self.bd["res"].pop(params[0], None)
            return
        raise AssertionError("SQL inesperado: " + s)

    def fetchone(self):
        return self._res


class _Con:
    def __init__(self, bd):
        self.bd = bd

    def cursor(self, **k):
        return _Cursor(self.bd)


@pytest.fixture
def bd():
    estado = {"uso": {}, "res": {}}

    @contextmanager
    def conexion():
        yield _Con(estado)

    return estado, conexion


def test_reserva_dentro_de_cuota_y_luego_libera(bd):
    estado, conexion = bd
    rid = ca.reservar(conexion, usuario_id=7, esperado=4 * 1024**2, limite=10 * 1024**2, usado=0)
    assert rid and estado["res"][rid] == (7, 4 * 1024**2)
    ca.liberar(conexion, rid, 7, 4 * 1024**2)
    assert estado["res"] == {} and estado["uso"][7] == 4 * 1024**2


def test_la_tercera_subida_que_supera_la_cuota_se_rechaza(bd):
    """PoC del informe: cuota 10 MiB, tres archivos de 4 MiB: el tercero no entra."""
    estado, conexion = bd
    limite, tam = 10 * 1024**2, 4 * 1024**2
    for _ in range(2):
        rid = ca.reservar(conexion, 7, tam, limite, estado["uso"].get(7, 0))
        ca.liberar(conexion, rid, 7, tam)
    with pytest.raises(ca.CuotaExcedida):
        ca.reservar(conexion, 7, tam, limite, estado["uso"][7])


def test_dos_subidas_simultaneas_no_se_cuelan_juntas(bd):
    estado, conexion = bd
    limite = 10 * 1024**2
    r1 = ca.reservar(conexion, 7, 6 * 1024**2, limite, 0)  # reserva viva, aún sin liberar
    with pytest.raises(ca.CuotaExcedida):
        ca.reservar(conexion, 7, 6 * 1024**2, limite, 0)  # uso 0 + reservado 6 + 6 > 10
    ca.liberar(conexion, r1, 7, 0)


def test_sin_content_length_se_frena_durante_el_streaming():
    ca.comprobar_durante(usado=9 * 1024**2, escrito=512 * 1024, limite=10 * 1024**2, reservado=0)
    with pytest.raises(ca.CuotaExcedida):
        ca.comprobar_durante(usado=9 * 1024**2, escrito=2 * 1024**2, limite=10 * 1024**2, reservado=0)
    with pytest.raises(ca.CuotaExcedida):  # declaró 1 MiB y va por 3 MiB
        ca.comprobar_durante(usado=0, escrito=3 * 1024**2, limite=100 * 1024**2, reservado=1024**2)


def test_umbral_global_de_espacio_libre(tmp_path, monkeypatch):
    monkeypatch.setattr(ca, "espacio_libre", lambda raiz: 1 * 1024**3)
    with pytest.raises(ca.SinEspacio):
        ca.comprobar_espacio_global(str(tmp_path), minimo=5 * 1024**3)
    ca.comprobar_espacio_global(str(tmp_path), minimo=512 * 1024**2)
