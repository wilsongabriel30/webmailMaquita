# -*- coding: utf-8 -*-
"""Las Aplicaciones del Drive (Editor de PDF y Tableros) toman el nombre de la marca
configurada (`drive_name` del Almacén), no uno escrito en el código («Raíces Maquita»,
«Drive Maquita»)."""
import importlib.util
import json
import os
import re
import subprocess
import sys

import pytest
from flask import Flask, render_template_string

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPO = os.path.dirname(RAIZ)
APLICACIONES = os.path.join(RAIZ, "aplicaciones")
sys.path.insert(0, os.path.join(RAIZ, "servicio"))


def _marca(app):
    spec = importlib.util.spec_from_file_location("marca_drive_%s" % app,
                                                  os.path.join(APLICACIONES, app, "marca_drive.py"))
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


class _Respuesta:
    def __init__(self, cuerpo):
        self.cuerpo = cuerpo

    def read(self):
        return self.cuerpo

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


@pytest.fixture(params=("pdf_editor", "bi"))
def marca(request, monkeypatch):
    monkeypatch.delenv("DRIVE_NAME", raising=False)
    monkeypatch.setenv("ALMACEN_INTERNAL_URL", "http://192.0.2.20:8788/")
    return _marca(request.param)


def test_toma_el_nombre_que_publica_el_almacen(marca, monkeypatch):
    pedidas = []

    def abrir(url, timeout):
        pedidas.append(url)
        return _Respuesta(json.dumps({"drive_name": "Archivos Andes"}).encode())
    monkeypatch.setattr(marca.urllib.request, "urlopen", abrir)
    assert marca.nombre_drive() == "Archivos Andes"
    assert marca.nombre_drive() == "Archivos Andes"
    assert pedidas == ["http://192.0.2.20:8788/api/almacen/marca"]   # en caché


def test_sin_almacen_usa_la_variable_y_luego_el_neutro(marca, monkeypatch):
    def caido(url, timeout):
        raise OSError("sin conexión")
    monkeypatch.setattr(marca.urllib.request, "urlopen", caido)
    monkeypatch.setenv("DRIVE_NAME", "Nube Andes")
    assert marca.nombre_drive() == "Nube Andes"
    marca._cache.update(valor=None, hasta=0.0)
    monkeypatch.delenv("DRIVE_NAME")
    assert marca.nombre_drive() == "Nube"


def test_las_plantillas_reciben_drive_name(marca, monkeypatch):
    monkeypatch.setattr(marca, "nombre_drive", lambda: "Archivos Andes")
    app = Flask("prueba")
    marca.registrar_en_plantillas(app)
    with app.test_request_context("/"):
        assert render_template_string("<title>Tableros — {{ drive_name }}</title>") == \
            "<title>Tableros — Archivos Andes</title>"


def test_el_almacen_publica_su_drive_name(monkeypatch):
    import api_marca
    monkeypatch.setattr(api_marca.config_almacen, "drive_name", lambda: "Archivos Andes")
    app = Flask("prueba")
    app.register_blueprint(api_marca.bp_marca)
    r = app.test_client().get("/api/almacen/marca")
    assert r.status_code == 200 and r.get_json() == {"drive_name": "Archivos Andes"}


def test_la_ruta_de_marca_no_pide_sesion(monkeypatch):
    """La piden las aplicaciones desde el servidor, sin la cookie del usuario."""
    from .test_crear_documento import _app_webmail
    app = _app_webmail(monkeypatch)
    import config_almacen
    monkeypatch.setattr(config_almacen, "drive_name", lambda: "Archivos Andes")
    r = app.test_client().get("/api/almacen/marca")
    assert r.status_code == 200 and r.get_json() == {"drive_name": "Archivos Andes"}
    assert app.test_client().get("/api/almacen/archivos").status_code == 401   # el resto sí la pide


def test_plantillas_del_editor_sin_nombre_fijo():
    plantillas = os.path.join(APLICACIONES, "pdf_editor", "interfaces", "web", "plantillas")
    for nombre in ("pdf_editor/home.html", "pdf_editor/index.html"):
        with open(os.path.join(plantillas, nombre), encoding="utf-8") as f:
            html = f.read()
        assert "{{ drive_name }}{% endblock %}" in html.split("\n", 3)[2]
        assert not re.search(r"Ra[íi]ces Maquita|Drive Maquita", html)
    with open(os.path.join(plantillas, "base.html"), encoding="utf-8") as f:
        assert "window.DRIVE_NAME = {{ (drive_name or 'Nube')|tojson }}" in f.read()


def test_tableros_sin_nombre_fijo():
    with open(os.path.join(APLICACIONES, "bi", "app_bi.py"), encoding="utf-8") as f:
        fuente = f.read()
    assert "<title>Tableros — {{ drive_name }}</title>" in fuente
    assert "Drive Maquita</title>" not in fuente


def test_candado_de_textos_cubre_las_aplicaciones():
    r = subprocess.run([sys.executable, os.path.join("deploy", "tools", "comprobar-textos-marca.py")],
                       cwd=REPO, capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
    spec = importlib.util.spec_from_file_location(
        "comprobar_textos_marca", os.path.join(REPO, "deploy", "tools", "comprobar-textos-marca.py"))
    candado = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(candado)
    assert set(candado.APLICACIONES) == {"almacen/aplicaciones/pdf_editor", "almacen/aplicaciones/bi"}
    # Cadenas de Python: cuentan las que se muestran, no los docstrings.
    fuente = '"""Aplicación del Drive Maquita."""\nTITULO = "Tableros — Drive Maquita"\n'
    assert [n for n, _ in candado.cadenas_python(fuente)] == [2]
    for texto in ("Editor PDF - Raíces Maquita", "Asistente de FARO", "en la Nube de Raices"):
        assert candado.NOMBRE_APLICACIONES.search(texto), texto
    assert not candado.NOMBRE_APLICACIONES.search("window.FaroFirmaCerts; raices del árbol")
