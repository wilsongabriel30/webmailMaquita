# -*- coding: utf-8 -*-
"""/api/almacen/salud y /api/almacen/listo para el balanceador."""
import os
import sys
import types
from contextlib import contextmanager

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "servicio"))
from flask import Flask  # noqa: E402

import salud_balanceador  # noqa: E402


def _app():
    app = Flask("prueba")
    app.register_blueprint(salud_balanceador.bp_salud)
    return app.test_client()


def _base_falsa(monkeypatch, responde=True):
    class _Cur:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def execute(self, sql):
            if not responde:
                raise RuntimeError("sin base")

        def fetchone(self):
            return (1,)

    class _Con:
        def cursor(self):
            return _Cur()

    @contextmanager
    def conexion():
        yield _Con()

    monkeypatch.setitem(sys.modules, "almacen_bd", types.SimpleNamespace(conexion=conexion))


def test_salud_no_toca_la_base(monkeypatch):
    _base_falsa(monkeypatch, responde=False)
    r = _app().get("/api/almacen/salud")
    assert r.status_code == 200 and r.get_json() == {"estado": "vivo"}
    assert r.headers["Cache-Control"] == "no-store"


def test_listo_con_base(monkeypatch, tmp_path):
    monkeypatch.setattr(salud_balanceador, "ARCHIVO_DRENAJE", str(tmp_path / "drenar"))
    _base_falsa(monkeypatch, responde=True)
    assert _app().get("/api/almacen/listo").status_code == 200


def test_listo_sin_base_es_503(monkeypatch, tmp_path):
    monkeypatch.setattr(salud_balanceador, "ARCHIVO_DRENAJE", str(tmp_path / "drenar"))
    _base_falsa(monkeypatch, responde=False)
    r = _app().get("/api/almacen/listo")
    assert r.status_code == 503 and r.get_json() == {"estado": "no_listo"}


def test_listo_en_drenaje_es_503(monkeypatch, tmp_path):
    archivo = tmp_path / "drenar"
    archivo.write_text("")
    monkeypatch.setattr(salud_balanceador, "ARCHIVO_DRENAJE", str(archivo))
    _base_falsa(monkeypatch, responde=True)
    r = _app().get("/api/almacen/listo")
    assert r.status_code == 503 and r.get_json() == {"estado": "drenando"}
