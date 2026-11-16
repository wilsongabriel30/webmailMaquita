# -*- coding: utf-8 -*-
"""La Papelera del explorador se puede usar (hallazgo 19 de Andes, 15/11/2026).

Dentro de Papelera el menú del archivo era el de siempre (terminaba en «Mover a la
papelera»), no había «Vaciar papelera» y el encabezado decía «Mi unidad». Las rutas del
servicio ya existían; faltaba la interfaz:
- el encabezado no cambiaba nunca (`#sectionTitle` fijo en la plantilla);
- la franja con «Vaciar papelera» se insertaba en un contenedor que la plantilla no tiene;
- el menú no tenía «Restaurar» ni «Eliminar definitivamente».
"""
import os
import re
import sys

import pytest
from flask import Flask

from ._explorador import CSS, codigo_js, leer, pintar_explorador, plantilla_sin_comentarios

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(RAIZ, "servicio"))
os.environ.setdefault("ALMACEN_CLAVE_SESION", "valor-de-prueba-del-ci-no-es-un-secreto-0123")  # gitleaks:allow
os.environ.setdefault("WEBMAIL_SECRET_KEY", "valor-de-prueba-del-ci-no-es-un-secreto-4567")  # gitleaks:allow

import api_extras  # noqa: E402


# ── el encabezado dice la sección ────────────────────────────────────────
@pytest.mark.parametrize("vista, titulo", [
    ("papelera", "Papelera"), ("favoritos", "Destacados"), ("recientes", "Recientes"),
    ("compartidos", "Compartido conmigo"), ("archivos", "Mi unidad")])
def test_el_servidor_pinta_el_titulo_de_la_seccion(vista, titulo):
    html = pintar_explorador(vista)
    assert '<h1 id="sectionTitle">%s</h1>' % titulo in html
    assert "<title>%s - Nube</title>" % titulo in html


def test_los_titulos_del_modulo_coinciden_con_los_de_la_plantilla():
    modulo = codigo_js("explorador-secciones.js")
    for vista, titulo in (("papelera", "Papelera"), ("favoritos", "Destacados"), ("recientes", "Recientes"),
                          ("compartidos", "Compartido conmigo"), ("archivos", "Mi unidad")):
        assert re.search(r"\b%s: '%s'" % (vista, titulo), modulo), vista
    # la vista con que el servidor abrió la página también cuenta, no solo la ruta
    assert "vista === 'papelera'" in modulo and "getElementById('sectionTitle')" in modulo


def test_la_navegacion_anuncia_la_seccion_despues_de_pintar():
    navegacion = codigo_js("explorador-navegacion.js")
    assert "actualizarTituloSeccion(seccion)" in navegacion
    assert "ajustarVistaPapelera(seccion === 'papelera', total)" in navegacion
    assert navegacion.count("_anunciarSeccion(") == 4      # la definición y las tres ramas de carga
    assert "gd-file-area" not in navegacion                # el contenedor que no existe en la plantilla


# ── menú de la Papelera ──────────────────────────────────────────────────
def test_el_menu_tiene_restaurar_y_eliminar_definitivamente():
    html = pintar_explorador("papelera")
    menu = html.split('id="contextMenu"', 1)[1].split("Submenús del menú contextual", 1)[0]
    menu = menu.split('id="submenuCompartir"', 1)[0]
    propias = re.findall(r'<div class="gd-context-item[^"]*ctx-solo-papelera" onclick="(\w+)\(\)">', menu)
    assert propias == ["restaurarSeleccionado", "eliminarDefinitivoSeleccionados"]
    assert "Restaurar" in menu and "Eliminar definitivamente" in menu


def test_la_hoja_de_estilo_separa_los_dos_menus():
    assert "explorador-papelera.css" in plantilla_sin_comentarios()
    css = re.sub(r"/\*.*?\*/", "", leer(os.path.join(CSS, "explorador-papelera.css")), flags=re.S)
    assert "body:not(.gd-en-papelera) .ctx-solo-papelera" in css
    assert "body.gd-en-papelera #contextMenu > :not(.ctx-solo-papelera)" in css


def test_el_modulo_de_papelera():
    modulo = codigo_js("explorador-papelera.js")
    assert "const CLASE_EN_PAPELERA = 'gd-en-papelera'" in modulo
    assert "getElementById('filesContainer')" in modulo            # donde SÍ se puede insertar la franja
    assert 'onclick="vaciarPapelera()"' in modulo and "Vaciar papelera" in modulo
    assert "API_BASE + '/papelera/eliminar'" in modulo
    assert "¿Eliminar definitivamente?" in modulo                  # con confirmación
    assert "cargarArchivos(rutaActual, true)" in modulo            # forzado: la lista se guarda 30 s


def test_vaciar_y_restaurar_confirman_y_recargan_sin_cache():
    interacciones = codigo_js("explorador-interactions.js")
    vaciar = interacciones.split("async function vaciarPapelera()", 1)[1]
    assert "¿Vaciar papelera?" in vaciar and 'API_BASE + "/papelera/vaciar"' in vaciar
    assert "cargarArchivos(rutaActual, true)" in vaciar
    restaurar = interacciones.split("async function restaurarSeleccionado()", 1)[1].split("async function vaciarPapelera()", 1)[0]
    assert 'API_BASE + "/papelera/restaurar"' in restaurar and "cargarArchivos(rutaActual, true)" in restaurar
    # lo eliminado no se abre con doble clic
    abrir = interacciones.split("function abrirItem(elemento) {", 1)[1][:400]
    assert "abrirItemEnPapelera(elemento)" in abrir


def test_orden_de_carga_de_los_modulos():
    html = plantilla_sin_comentarios()
    for modulo in ("explorador-secciones.js", "explorador-papelera.js"):
        assert html.index(modulo) < html.index("explorador-navegacion.js"), modulo


# ── las rutas que usa la interfaz existen en el servicio ─────────────────
@pytest.fixture
def cliente(monkeypatch):
    llamadas = []
    monkeypatch.setattr(api_extras, "usuario_actual", lambda: 7)
    monkeypatch.setattr(api_extras.nucleo, "restaurar_de_papelera", lambda u, r: llamadas.append(("restaurar", u, r)) or "/a.txt")
    monkeypatch.setattr(api_extras.nucleo, "eliminar_de_papelera", lambda u, r: llamadas.append(("eliminar", u, r)) or True)
    monkeypatch.setattr(api_extras.nucleo, "vaciar_papelera", lambda u: llamadas.append(("vaciar", u)) or 2)
    app = Flask("prueba")
    app.register_blueprint(api_extras.bp_extras, url_prefix="/api/almacen")
    c = app.test_client()
    c.llamadas = llamadas
    return c


def test_rutas_de_la_papelera(cliente):
    assert cliente.post("/api/almacen/papelera/restaurar", json={"ruta": "a__1.txt"}).get_json()["ruta_restaurada"] == "/a.txt"
    assert cliente.post("/api/almacen/papelera/eliminar", json={"ruta": "a__1.txt"}).status_code == 200
    assert cliente.post("/api/almacen/papelera/vaciar").get_json()["retenidos"] == 2
    assert cliente.llamadas == [("restaurar", 7, "a__1.txt"), ("eliminar", 7, "a__1.txt"), ("vaciar", 7)]
    assert cliente.post("/api/almacen/papelera/restaurar", json={}).status_code == 400
