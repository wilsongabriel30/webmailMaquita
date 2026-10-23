# -*- coding: utf-8 -*-
"""«Eliminar definitivamente» un elemento de la papelera (POST /papelera/eliminar).

El explorador llamaba a esa ruta pero el servicio del Almacén no la tenía (solo existía en
drive-maquita): respondía «Función no disponible». Estas pruebas fijan que el elemento pasa
a la retención (no se destruye), que un nombre repetido en la retención no se pisa y las
respuestas 400/404 de la API. Reporte de Andes sobre la v1.11.4.
"""
import os
import sys

import pytest

os.environ.setdefault("ALMACEN_CLAVE_SESION", "valor-de-prueba-del-ci-no-es-un-secreto-0123")  # gitleaks:allow
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "servicio"))
import nucleo_archivos as nucleo  # noqa: E402
import seguridad_rutas  # noqa: E402

USUARIO = 7


class BaseFalsa:
    """Tablas papelera y retención en memoria, con las dos consultas que usa el núcleo."""

    def __init__(self):
        self.papelera = []
        self.retencion = []

    def consultar(self, sql, params=()):
        if "FROM papelera" in sql:
            usuario, nombre_fisico = params
            return [f for f in self.papelera if f["usuario_id"] == usuario and f["nombre_fisico"] == nombre_fisico]
        raise AssertionError(sql)

    def ejecutar(self, sql, params=()):
        if sql.strip().startswith("INSERT INTO retencion"):
            claves = ("usuario_id", "ruta_original", "nombre", "nombre_fisico", "es_carpeta", "tamano_bytes")
            self.retencion.append(dict(zip(claves, params)))
        elif sql.startswith("DELETE FROM papelera"):
            self.papelera = [f for f in self.papelera if f["id"] != params[0]]
        else:
            raise AssertionError(sql)


@pytest.fixture
def entorno(tmp_path, monkeypatch):
    monkeypatch.setattr(seguridad_rutas, "raiz_datos", lambda: str(tmp_path))
    base = BaseFalsa()
    monkeypatch.setattr(nucleo, "consultar", base.consultar)
    monkeypatch.setattr(nucleo, "ejecutar", base.ejecutar)
    papelera = tmp_path / str(USUARIO) / "papelera"
    retencion = tmp_path / str(USUARIO) / "retencion"
    papelera.mkdir(parents=True)
    retencion.mkdir(parents=True)
    (papelera / "informe__1.txt").write_text("datos")
    base.papelera.append({"id": 41, "usuario_id": USUARIO, "ruta_original": "/informe.txt", "nombre": "informe.txt",
                          "nombre_fisico": "informe__1.txt", "es_carpeta": False, "tamano_bytes": 5})
    return base, papelera, retencion


def test_eliminar_pasa_el_elemento_a_retencion(entorno):
    base, papelera, retencion = entorno
    assert nucleo.eliminar_de_papelera(USUARIO, "informe__1.txt") is True
    assert not (papelera / "informe__1.txt").exists()
    assert (retencion / "informe__1.txt").read_text() == "datos"
    assert base.papelera == []
    assert base.retencion[0]["nombre_fisico"] == "informe__1.txt"
    assert base.retencion[0]["ruta_original"] == "/informe.txt"


def test_nombre_repetido_en_retencion_no_se_pisa(entorno):
    base, _papelera, retencion = entorno
    (retencion / "informe__1.txt").write_text("anterior")
    nucleo.eliminar_de_papelera(USUARIO, "informe__1.txt")
    assert (retencion / "informe__1.txt").read_text() == "anterior"
    assert (retencion / "informe__1_41.txt").read_text() == "datos"
    assert base.retencion[0]["nombre_fisico"] == "informe__1_41.txt"


def test_elemento_inexistente_da_file_not_found(entorno):
    with pytest.raises(FileNotFoundError):
        nucleo.eliminar_de_papelera(USUARIO, "no-existe.txt")


@pytest.fixture
def cliente(entorno, monkeypatch):
    from flask import Flask

    import api_extras
    monkeypatch.setattr(api_extras, "usuario_actual", lambda: USUARIO)
    app = Flask(__name__)
    app.register_blueprint(api_extras.bp_extras)
    return app.test_client()


def test_api_sin_ruta_da_400(cliente):
    assert cliente.post("/papelera/eliminar", json={}).status_code == 400


def test_api_inexistente_da_404(cliente):
    respuesta = cliente.post("/papelera/eliminar", json={"ruta": "no-existe.txt"})
    assert respuesta.status_code == 404


def test_api_elimina_y_responde_200(cliente, entorno):
    base, _papelera, _retencion = entorno
    respuesta = cliente.post("/papelera/eliminar", json={"ruta": "informe__1.txt"})
    assert respuesta.status_code == 200
    assert respuesta.get_json()["success"] is True
    assert base.papelera == []
