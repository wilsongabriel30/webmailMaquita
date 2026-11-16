# -*- coding: utf-8 -*-
"""La nube en un celular (hallazgo 22 de Andes, prueba de interfaz a 390 px).

Por debajo de 768 px `explorador.css` ocultaba el menú lateral sin dar nada a cambio: no había
«Nuevo», ni Papelera, ni «Compartido conmigo», y los botones de la cabecera quedaban fuera de la
pantalla. Lo resuelven dos archivos propios (`explorador-movil.css` y `explorador-movil.js`).
Aquí se fija el cableado: que la plantilla los cargue de verdad (con su etiqueta, no en un
comentario) y en el orden que necesitan, y lo esencial de cada uno.
"""
import os
import re

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ESTATICOS = os.path.join(RAIZ, "servicio", "estaticos")
PLANTILLA = os.path.join(RAIZ, "servicio", "plantillas", "nextcloud", "explorador.html")
HOJA = os.path.join(ESTATICOS, "css", "nextcloud", "explorador-movil.css")
MODULO = os.path.join(ESTATICOS, "js", "nextcloud", "explorador-movil.js")


def _leer(ruta):
    with open(ruta, encoding="utf-8") as f:
        return f.read()


def _sin_comentarios(html):
    """La plantilla sin comentarios HTML ni de Jinja: lo que de verdad llega al navegador."""
    html = re.sub(r"<!--.*?-->", "", html, flags=re.S)
    return re.sub(r"\{#.*?#\}", "", html, flags=re.S)


def _posicion_hoja(html, nombre):
    m = re.search(r"<link\b[^>]*\brel=\"stylesheet\"[^>]*css/nextcloud/%s'" % re.escape(nombre), html)
    return m.start() if m else -1


def _posicion_modulo(html, nombre):
    m = re.search(r"<script\b[^>]*\bsrc=\"[^\"]*js/nextcloud/%s'" % re.escape(nombre), html)
    return m.start() if m else -1


def test_la_plantilla_carga_la_hoja_despues_de_la_principal():
    html = _sin_comentarios(_leer(PLANTILLA))
    principal = _posicion_hoja(html, "explorador.css")
    movil = _posicion_hoja(html, "explorador-movil.css")
    # después de explorador.css: a igual peso de selector gana la última, y la principal
    # oculta el menú lateral por debajo de 768 px
    assert -1 < principal < movil


def test_la_plantilla_carga_el_modulo_despues_de_los_que_usa():
    html = _sin_comentarios(_leer(PLANTILLA))
    movil = _posicion_modulo(html, "explorador-movil.js")
    assert movil > -1
    # usa el menú «Nuevo» y el plegado del panel derecho que preparan estos módulos
    for anterior in ("explorador-core.js", "explorador-interactions.js", "explorador-panels.js"):
        assert -1 < _posicion_modulo(html, anterior) < movil


def test_la_hoja_solo_actua_en_pantalla_angosta_y_muestra_el_menu_lateral():
    css = _leer(HOJA)
    antes, _, dentro = css.partition("@media (max-width: 768px)")
    assert dentro, "falta el bloque para pantallas angostas"
    # fuera del bloque, los controles propios del celular no existen (escritorio intacto)
    assert re.search(r"\.gd-movil-menu-btn,\s*\.gd-movil-fondo,\s*\.gd-movil-nuevo\s*\{\s*display:\s*none;", antes)
    assert ".gd-sidebar" not in antes and ".gd-header" not in antes
    # dentro, el menú lateral vuelve a existir (panel deslizante) y se abre con la clase del módulo
    assert re.search(r"\n    \.gd-sidebar\s*\{[^}]*display:\s*flex;[^}]*position:\s*fixed;", dentro)
    assert "body.nube-menu-abierto .gd-sidebar" in dentro


def test_el_modulo_crea_los_controles_y_cierra_el_menu():
    js = _leer(MODULO)
    for identificador in ("'btnMenuMovil'", "'btnNuevoMovil'", "'gd-movil-fondo'", "'nube-menu-abierto'"):
        assert identificador in js
    assert "fondo.addEventListener('click', cerrarMenu)" in js      # tocar fuera
    assert "a.gd-nav-item" in js and "closest(DESTINOS)) cerrarMenu()" in js   # elegir una sección
    assert "getElementById('newMenu')" in js                        # el mismo menú «Nuevo» del panel


def test_los_archivos_nuevos_son_pequenos():
    # regla de la casa: módulos pequeños, nada de engordar los monolitos del explorador
    assert len(_leer(HOJA).splitlines()) < 400
    assert len(_leer(MODULO).splitlines()) < 200
