# -*- coding: utf-8 -*-
"""El DDL de arranque se ejecuta bajo un bloqueo consultivo de sesión: un worker a la vez."""
import os
import sys
import threading
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "servicio"))
import ddl_arranque  # noqa: E402


class _Cur:
    def __init__(self, con):
        self.con = con

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def execute(self, sql, params=()):
        self.con.registro.append((" ".join(sql.split()), params))
        if sql.startswith("SELECT pg_advisory_lock"):
            self.con.cerrojo.acquire()
        elif sql.startswith("SELECT pg_advisory_unlock"):
            self.con.cerrojo.release()


class _Con:
    def __init__(self, cerrojo, registro):
        self.cerrojo, self.registro, self.autocommit = cerrojo, registro, False

    def cursor(self):
        return _Cur(self)


class _Pool:
    """Doble del pool: cada getconn da una 'sesión' distinta que comparte el cerrojo del servidor."""

    def __init__(self):
        self.cerrojo, self.registro, self.devueltas = threading.Lock(), [], 0

    def getconn(self):
        return _Con(self.cerrojo, self.registro)

    def putconn(self, con):
        self.devueltas += 1


def test_toma_y_suelta_el_bloqueo_y_devuelve_la_conexion():
    pool = _Pool()
    with ddl_arranque.serializado(lambda: pool):
        assert pool.registro[-1] == ("SELECT pg_advisory_lock(%s)", (ddl_arranque.CLAVE_BLOQUEO,))
    assert pool.registro[-1] == ("SELECT pg_advisory_unlock(%s)", (ddl_arranque.CLAVE_BLOQUEO,))
    assert pool.devueltas == 1 and not pool.cerrojo.locked()


def test_suelta_el_bloqueo_aunque_el_ddl_falle():
    pool = _Pool()
    try:
        with ddl_arranque.serializado(lambda: pool):
            raise RuntimeError("DDL roto")
    except RuntimeError:
        pass
    assert not pool.cerrojo.locked() and pool.devueltas == 1


def test_seis_workers_no_se_solapan():
    pool = _Pool()
    dentro, maximo, cerrojo_contador = [0], [0], threading.Lock()

    def worker():
        with ddl_arranque.serializado(lambda: pool):
            with cerrojo_contador:
                dentro[0] += 1
                maximo[0] = max(maximo[0], dentro[0])
            time.sleep(0.01)
            with cerrojo_contador:
                dentro[0] -= 1

    hilos = [threading.Thread(target=worker) for _ in range(6)]
    for h in hilos:
        h.start()
    for h in hilos:
        h.join(5)
    assert maximo[0] == 1 and pool.devueltas == 6
