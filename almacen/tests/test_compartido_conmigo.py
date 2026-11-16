# -*- coding: utf-8 -*-
"""«Compartido conmigo» del explorador (reporte de Andes sobre la v1.21.1).

1. La sección se abre con vista = 'compartidos' y ruta '/'; el explorador solo miraba la ruta
   y pedía la lista propia (GET /archivos?ruta=/). Ahora la atiende un módulo propio que pide
   GET /compartidos-conmigo. Se fija el cableado (plantilla y navegación).
2. Lo compartido con una persona desde el diálogo «Compartir» se guarda con tipo 0/4 y token;
   la descarga por enlace solo admitía tipo 3 y respondía 404 a quien lo recibía.
"""
import os
import sys

import pytest
from flask import Flask

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(RAIZ, "servicio"))
os.environ.setdefault("ALMACEN_CLAVE_SESION", "valor-de-prueba-del-ci-no-es-un-secreto-0123")  # gitleaks:allow
os.environ.setdefault("WEBMAIL_SECRET_KEY", "valor-de-prueba-del-ci-no-es-un-secreto-4567")  # gitleaks:allow

import api_extras  # noqa: E402
import congelados  # noqa: E402

JS = os.path.join(RAIZ, "servicio", "estaticos", "js", "nextcloud")
PLANTILLA = os.path.join(RAIZ, "servicio", "plantillas", "nextcloud", "explorador.html")
TOKEN = "tokenDePruebaCompartido01"


def _leer(ruta):
    with open(ruta, encoding="utf-8") as f:
        return f.read()


def test_la_plantilla_carga_el_modulo_antes_de_la_navegacion():
    html = _leer(PLANTILLA)
    assert html.index("explorador-compartidos-conmigo.js") < html.index("explorador-navegacion.js")


def test_la_navegacion_delega_en_el_modulo():
    navegacion = _leer(os.path.join(JS, "explorador-navegacion.js"))
    assert "esVistaCompartidosConmigo(ruta)" in navegacion and "cargarCompartidosConmigo(ruta, silencioso)" in navegacion
    # la delegación va antes de elegir la API de la lista propia
    assert navegacion.index("cargarCompartidosConmigo(") < navegacion.index("/archivos?ruta=")


def test_el_modulo_pide_la_ruta_del_servicio_y_reconoce_la_vista():
    modulo = _leer(os.path.join(JS, "explorador-compartidos-conmigo.js"))
    assert "'/compartidos-conmigo?" in modulo
    assert "vistaActual === 'compartidos'" in modulo
    assert "/almacen-s/" in modulo           # cada elemento se abre con su enlace, no con una ruta propia


@pytest.fixture
def cliente(monkeypatch, tmp_path):
    archivo = tmp_path / "Acta.pdf"
    archivo.write_bytes(b"%PDF-1.4 prueba")
    filas = [{"token": TOKEN, "propietario_id": 3, "ruta": "/Acta.pdf", "expira_en": None,
              "clave_hash": None, "permite_descarga": True}]
    consultas = []

    def consultar(sql, parametros=None, nomina=False):
        consultas.append(" ".join(sql.split()))
        return [f for f in filas if f["token"] == parametros[0]]

    monkeypatch.setattr(api_extras, "consultar", consultar)
    monkeypatch.setattr(api_extras, "ruta_fisica", lambda usuario, ruta, **_k: str(tmp_path / ruta.strip("/")))
    monkeypatch.setattr(congelados, "esta_congelado", lambda usuario: False)
    app = Flask("prueba")
    app.register_blueprint(api_extras.bp_extras, url_prefix="/api/almacen")
    c = app.test_client()
    c.filas, c.consultas = filas, consultas
    return c


def test_descarga_lo_compartido_con_una_persona(cliente):
    r = cliente.get("/api/almacen/publico/" + TOKEN)
    assert r.status_code == 200 and r.data == b"%PDF-1.4 prueba"
    assert "tipo = 3" not in cliente.consultas[0]     # el token es la credencial, sea cual sea el tipo


def test_respeta_solo_lectura_y_token_desconocido(cliente):
    assert cliente.get("/api/almacen/publico/otroTokenQueNoExiste99").status_code == 404
    cliente.filas[0]["permite_descarga"] = False
    assert cliente.get("/api/almacen/publico/" + TOKEN).status_code == 403
