# -*- coding: utf-8 -*-
"""«Mi perfil» del explorador: GET/POST /api/almacen/mi-perfil.

La ruta está en el contrato y el menú la llama, pero el Almacén del webmail no la tenía:
respondía 404 «Función no disponible» y la pantalla no cambiaba (reporte de Andes sobre la
v1.21.1). Estas pruebas fijan la forma de la respuesta, que el nombre se guarda solo con el
directorio local y que un nombre inadmisible no llega a la base.
"""
import os
import sys

import pytest
from flask import Flask

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(RAIZ, "servicio"))
os.environ.setdefault("ALMACEN_CLAVE_SESION", "valor-de-prueba-del-ci-no-es-un-secreto-0123")  # gitleaks:allow
os.environ.setdefault("WEBMAIL_SECRET_KEY", "valor-de-prueba-del-ci-no-es-un-secreto-4567")  # gitleaks:allow

import api_perfil  # noqa: E402

USUARIO = 7
FILA_LOCAL = {"username": "ana.perez@example.org", "email": "ana.perez@example.org",
              "full_name": "Ana Perez", "nombre_directorio": ""}


@pytest.fixture
def cliente(monkeypatch):
    estado = {"filas": [dict(FILA_LOCAL)], "externos": [], "escrituras": []}

    def consultar(sql, parametros=None, nomina=False):
        return estado["externos"] if "usuarios_externos" in sql else estado["filas"]

    def ejecutar(sql, parametros=None):
        assert sql.startswith("UPDATE usuarios SET full_name")
        estado["escrituras"].append(parametros)
        return {"id": parametros[1]}

    monkeypatch.setattr(api_perfil, "consultar", consultar)
    monkeypatch.setattr(api_perfil, "ejecutar", ejecutar)
    monkeypatch.setattr(api_perfil, "usuario_actual", lambda: USUARIO)
    monkeypatch.setattr(api_perfil.auth_webmail, "_MODO", "local")
    app = Flask("prueba")
    app.register_blueprint(api_perfil.bp_perfil, url_prefix="/api/almacen")
    c = app.test_client()
    c.estado = estado
    return c


def test_ver_perfil_local(cliente):
    r = cliente.get("/api/almacen/mi-perfil")
    assert r.status_code == 200
    assert r.get_json() == {"success": True, "email": "ana.perez@example.org", "nombre_nomina": "Ana Perez",
                            "nombre_visible": "Ana Perez", "foto_url": None, "editable": True}


def test_el_nombre_guardado_es_el_visible(cliente):
    cliente.estado["filas"][0]["full_name"] = "Ana P. de Ruiz"
    datos = cliente.get("/api/almacen/mi-perfil").get_json()
    assert datos["nombre_visible"] == "Ana P. de Ruiz" and datos["nombre_nomina"] == "Ana Perez"


def test_guardar_nombre_visible(cliente):
    r = cliente.post("/api/almacen/mi-perfil", json={"nombre_visible": "  Ana   María Pérez "})
    assert r.status_code == 200 and r.get_json() == {"success": True, "nombre_visible": "Ana María Pérez"}
    assert cliente.estado["escrituras"] == [("Ana María Pérez", USUARIO)]


def test_vacio_restablece_el_predeterminado(cliente):
    r = cliente.post("/api/almacen/mi-perfil", json={"nombre_visible": ""})
    assert r.status_code == 200 and cliente.estado["escrituras"] == [("Ana Perez", USUARIO)]


@pytest.mark.parametrize("nombre", ["<b>Ana</b>", 'Ana "la jefa"', "D'Angelo", "Ana\\Perez", "Ana\x00", "x" * 81, 5, ["Ana"]])
def test_nombres_inadmisibles(cliente, nombre):
    r = cliente.post("/api/almacen/mi-perfil", json={"nombre_visible": nombre})
    assert r.status_code == 400 and cliente.estado["escrituras"] == []


def test_directorio_central_solo_muestra(cliente, monkeypatch):
    monkeypatch.setattr(api_perfil.auth_webmail, "_MODO", "nomina")
    cliente.estado["filas"] = [{"username": "aperez", "email": "ana.perez@example.org",
                                "full_name": "A. Perez", "nombre_directorio": "Ana Lucía Pérez"}]
    datos = cliente.get("/api/almacen/mi-perfil").get_json()
    assert datos["nombre_visible"] == "Ana Lucía Pérez" and datos["editable"] is False
    r = cliente.post("/api/almacen/mi-perfil", json={"nombre_visible": "Otra"})
    assert r.status_code == 403 and cliente.estado["escrituras"] == []


def test_cuenta_externa_solo_muestra(cliente, monkeypatch):
    monkeypatch.setattr(api_perfil, "usuario_actual", lambda: api_perfil.auth_webmail._OFFSET_EXTERNOS + 3)
    cliente.estado["externos"] = [{"email": "Aliada@Example.com", "full_name": None}]
    datos = cliente.get("/api/almacen/mi-perfil").get_json()
    assert datos["email"] == "aliada@example.com" and datos["nombre_visible"] == "Aliada"
    assert datos["editable"] is False
    assert cliente.post("/api/almacen/mi-perfil", json={"nombre_visible": "Otra"}).status_code == 403


def test_sin_fila_en_el_directorio(cliente):
    cliente.estado["filas"] = []
    assert cliente.get("/api/almacen/mi-perfil").status_code == 404
    assert cliente.post("/api/almacen/mi-perfil", json={"nombre_visible": "Ana"}).status_code == 404


def test_la_aplicacion_del_webmail_registra_la_ruta():
    fuente = open(os.path.join(RAIZ, "servicio", "app_webmail.py"), encoding="utf-8").read()
    assert "from api_perfil import bp_perfil" in fuente and "bp_crear, bp_perfil)" in fuente
