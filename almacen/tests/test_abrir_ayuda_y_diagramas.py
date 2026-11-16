# -*- coding: utf-8 -*-
"""Diagramas, botón de ayuda y archivos de texto (hallazgos 20 y 24 de Andes, 15/11/2026).

20. «Nuevo → Diagrama» creaba el archivo, pero al abrirlo: «No se pudo cargar el diagrama»
    (GET /api/almacen/drawio/contenido → 404). El Almacén del webmail no tiene editor de
    diagramas ni las rutas /drawio/* del contrato: no se ofrece crear lo que no se puede abrir.
24. El botón de ayuda (?) no tenía ninguna acción y un archivo de texto no se abría con
    doble clic (se descargaba).
"""
import os
import re

from ._explorador import SERVICIO, codigo_js, pintar_explorador, plantilla_sin_comentarios


# ── 20 ───────────────────────────────────────────────────────────────────
def test_el_almacen_no_ofrece_crear_diagramas():
    html = pintar_explorador()
    nuevo = html.split('id="newMenu"', 1)[1].split("</aside>", 1)[0]
    assert "crearDocumento('documento')" in nuevo and "crearDocumento('texto')" in nuevo
    assert "crearDocumento('diagrama')" not in nuevo and "Draw.io" not in nuevo


def test_el_servicio_no_tiene_rutas_de_diagramas():
    """Si algún día se añaden /drawio/contenido y /drawio/guardar (y un editor), esta prueba
    avisa de que hay que volver a ofrecer «Diagrama» y quitar el aviso del explorador."""
    for nombre in os.listdir(SERVICIO):
        if nombre.endswith(".py"):
            fuente = open(os.path.join(SERVICIO, nombre), encoding="utf-8").read()
            assert not re.search(r"route\(\s*['\"]/drawio/", fuente), nombre


def test_un_diagrama_existente_se_explica_y_se_puede_descargar():
    abrir = codigo_js("explorador-abrir.js")
    assert "if (EXTENSIONES_DRAWIO.includes(ext)) {" in abrir and "avisarDiagramaSinEditor(ruta);" in abrir
    assert "no tiene editor de diagramas" in abrir and "/archivos/descargar?ruta=" in abrir
    assert "/drawio/contenido" not in abrir


# ── 24 ───────────────────────────────────────────────────────────────────
def test_el_boton_de_ayuda_abre_la_ayuda():
    html = pintar_explorador()
    boton = re.search(r'<button class="gd-icon-btn" id="btnAyuda"[^>]*>', html).group(0)
    assert 'onclick="abrirAyudaNube()"' in boton and 'title="Ayuda"' in boton
    ayuda = codigo_js("explorador-ayuda.js")
    assert "function abrirAyudaNube() {" in ayuda and "Swal.fire({" in ayuda
    assert "mostrarAtajosTeclado()" in ayuda
    assert "explorador-ayuda.js" in plantilla_sin_comentarios()


def test_no_queda_ningun_boton_de_cabecera_sin_accion():
    html = pintar_explorador()
    cabecera = html.split('<div class="gd-header-actions">', 1)[1].split("</header>", 1)[0]
    for boton in re.findall(r'<button class="gd-icon-btn"[^>]*>', cabecera):
        assert "onclick=" in boton or 'id="syncStatusBtn"' in boton, boton


def test_el_doble_clic_abre_los_archivos_de_texto():
    interacciones = codigo_js("explorador-interactions.js")
    abrir_archivo = interacciones.split("async function abrirArchivo(ruta) {", 1)[1].split("\n}\n", 1)[0]
    # la consulta al módulo va antes de la descarga genérica de «otros archivos»
    assert abrir_archivo.index("abrirArchivoPropio(ruta, ext)") < abrir_archivo.index("/archivos/descargar?ruta=")
    abrir = codigo_js("explorador-abrir.js")
    assert "const EXTENSIONES_TEXTO_VISOR = ['txt', 'md', 'log'];" in abrir
    assert "if (EXTENSIONES_TEXTO_VISOR.includes(ext)) {" in abrir and "abrirVisorTexto(ruta);" in abrir
    assert "API_BASE + '/archivos/ver?ruta='" in abrir
    assert "escHtml(recortado ? texto.slice(0, LIMITE_VISOR_TEXTO) : texto)" in abrir   # se pinta como texto
    assert "explorador-abrir.js" in plantilla_sin_comentarios()
