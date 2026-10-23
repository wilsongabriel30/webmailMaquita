# -*- coding: utf-8 -*-
"""«Eliminar definitivamente» un elemento de la papelera (POST /papelera/eliminar).

Faltaba la ruta: el explorador respondía «Función no disponible: /papelera/eliminar».
El elemento no se destruye: pasa a la retención, como al vaciar la papelera.
"""
import os
import sys

import pytest

os.environ.setdefault("ALMACEN_CLAVE_SESION", "valor-de-prueba-del-ci-no-es-un-secreto-0123")  # gitleaks:allow
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "servicio"))
import papelera_eliminar  # noqa: E402
import seguridad_rutas  # noqa: E402

USUARIO = 7


@pytest.fixture
def papelera(tmp_path, monkeypatch):
    monkeypatch.setattr(seguridad_rutas, "raiz_datos", lambda: str(tmp_path))
    filas = [{"id": 1, "ruta_original": "/informe.txt", "nombre": "informe.txt",
              "nombre_fisico": "informe.txt.1700000000", "es_carpeta": False, "tamano_bytes": 5}]
    ordenes = []

    def consultar(sql, params):
        return [f for f in filas if (USUARIO, f["nombre_fisico"]) == params]

    monkeypatch.setattr(papelera_eliminar, "consultar", consultar)
    monkeypatch.setattr(papelera_eliminar, "ejecutar", lambda sql, params: ordenes.append((sql.split()[0], params)))
    base = tmp_path / str(USUARIO) / "papelera"
    base.mkdir(parents=True)
    (base / "informe.txt.1700000000").write_text("datos")
    return tmp_path, ordenes


def test_pasa_el_elemento_a_la_retencion(papelera):
    raiz, ordenes = papelera
    assert papelera_eliminar.eliminar_de_papelera(USUARIO, "informe.txt.1700000000")
    assert not (raiz / str(USUARIO) / "papelera" / "informe.txt.1700000000").exists()
    assert (raiz / str(USUARIO) / "retencion" / "informe.txt.1700000000").read_text() == "datos"
    assert [o[0] for o in ordenes] == ["INSERT", "DELETE"]


def test_lo_que_no_esta_en_la_papelera_da_no_encontrado(papelera):
    with pytest.raises(FileNotFoundError):
        papelera_eliminar.eliminar_de_papelera(USUARIO, "otro.txt.1")


def test_la_ruta_existe_en_el_servicio():
    from flask import Flask
    import api_extras
    app = Flask(__name__)
    app.register_blueprint(api_extras.bp_extras)
    metodos = {r.rule: r.methods for r in app.url_map.iter_rules()}
    assert any(regla.endswith("/papelera/eliminar") and "POST" in m for regla, m in metodos.items())
