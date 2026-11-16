# -*- coding: utf-8 -*-
"""Panel «Configuración» según el rol y cifras de espacio de una sola fuente
(hallazgos 21 y 23 de Andes, 15/11/2026).

21. Una cuenta normal veía «Herramientas de administración (solo master)» con sus formularios.
    El servidor los rechazaba (403), pero no debían mostrarse.
23. «Mi cuenta» decía «Total 5.0 GB» y la pantalla de cuotas «Por defecto 20 GB»: el 20 era un
    valor fijo del JavaScript que aparecía cuando la petición de administración fallaba.
"""
import os
import re
import sys

import pytest
from flask import Flask

from ._explorador import codigo_js, pintar_explorador, plantilla_sin_comentarios

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(RAIZ, "servicio"))
os.environ.setdefault("ALMACEN_CLAVE_SESION", "valor-de-prueba-del-ci-no-es-un-secreto-0123")  # gitleaks:allow
os.environ.setdefault("WEBMAIL_SECRET_KEY", "valor-de-prueba-del-ci-no-es-un-secreto-4567")  # gitleaks:allow

import api_archivos  # noqa: E402

GB = 1024 ** 3


# ── 21: la página sabe el rol y el panel se arma con él ──────────────────
@pytest.mark.parametrize("rol, esperado", [("user", "false"), ("admin", "false"), ("master", "true"), ("master_admin", "true")])
def test_la_pagina_declara_si_es_administrador(rol, esperado):
    assert "window.ALMACEN_ES_ADMIN = %s;" % esperado in pintar_explorador(rol=rol)


def test_el_panel_separa_lo_personal_de_la_administracion():
    menu = codigo_js("explorador-almacen-menu.js")
    personales = menu.split("const OPCIONES_ALMACEN_PERSONALES = [", 1)[1].split("];", 1)[0]
    admin = menu.split("const OPCIONES_ALMACEN_ADMIN = [", 1)[1].split("];", 1)[0]
    assert re.findall(r"'(abrir\w+)'", personales) == ["abrirActividad", "abrirUnidades", "abrirCuotaAlmacen"]
    assert re.findall(r"'(abrir\w+)'", admin) == ["abrirRecuperacionAlmacen", "abrirAlmacenamiento", "abrirCuotas"]
    assert "return window.ALMACEN_ES_ADMIN === true;" in menu         # sin dato, no es administrador
    assert "esAdmin ? OPCIONES_ALMACEN_ADMIN.concat(OPCIONES_ALMACEN_PERSONALES) : OPCIONES_ALMACEN_PERSONALES.slice()" in menu
    assert "solo master" not in menu


def test_las_herramientas_de_administracion_no_se_abren_sin_rol():
    admin = codigo_js("explorador-almacen-admin.js")
    for funcion in ("abrirRecuperacionAlmacen", "abrirAlmacenamiento", "abrirCuotas"):
        cuerpo = admin.split("async function %s() {" % funcion, 1)[1]
        assert cuerpo.lstrip().startswith("if (!exigirAdminAlmacen()) return;"), funcion
    assert "function abrirConfigAlmacen" not in admin                 # el panel ya no vive aquí
    assert "esAdminAlmacen() ? '<button onclick=\"crearUnidad()\"" in admin


def test_el_menu_se_carga_antes_que_las_herramientas():
    html = plantilla_sin_comentarios()
    assert html.index("explorador-almacen-menu.js") < html.index("explorador-almacen-admin.js")
    assert html.index("explorador-cuota.js") < html.index("explorador-almacen-menu.js")


def test_el_servidor_sigue_rechazando_a_quien_no_es_master():
    fuente = open(os.path.join(RAIZ, "servicio", "app_webmail.py"), encoding="utf-8").read()
    assert "if '/admin/' in ruta and rol not in ('master', 'master_admin'):" in fuente


# ── 23: una sola fuente para las cifras ──────────────────────────────────
def test_la_pantalla_de_cuotas_no_inventa_cifras():
    admin = codigo_js("explorador-almacen-admin.js")
    cuotas = admin.split("async function abrirCuotas() {", 1)[1].split("async function buscarUsuarioCuota", 1)[0]
    assert not re.search(r"(?<![\w#.])20(?![\w.])", cuotas)           # ni «let def = 20» ni «|| 20»
    assert "let def = null;" in cuotas and "if (def === null) {" in cuotas
    assert "cuota por defecto de la instalación: ${def} GB" in cuotas
    assert "Cuota por defecto de la instalación</div>" in cuotas
    assert "'· cuota propia de la cuenta' : '· cuota por defecto de la instalación'" in admin


def test_mi_almacenamiento_lee_la_misma_fuente_que_el_lateral():
    menu = codigo_js("explorador-almacen-menu.js")
    propio = menu.split("async function abrirCuotaAlmacen() {", 1)[1]
    assert "fetch('/api/almacen/cuota'" in propio and "normalizarCuota(datos)" in propio
    assert "Cuota de su cuenta" in propio and "datos.cuota_propia === true" in propio
    assert "(asignada a su cuenta)" in menu and "(la predeterminada de la instalación)" in menu
    lateral = codigo_js("explorador-interactions.js").split("async function cargarCuota() {", 1)[1][:400]
    assert "fetch(`${API_BASE}/cuota`)" in lateral and "normalizarCuota(data)" in lateral


@pytest.fixture
def cliente(monkeypatch):
    estado = {"propias": []}
    monkeypatch.setattr(api_archivos, "usuario_actual", lambda: 7)
    monkeypatch.setattr(api_archivos.nucleo, "cuota", lambda usuario: {
        "usado": 1024, "usado_humano": "1.0 KB", "total": 5 * GB, "total_humano": "5.0 GB",
        "libre": 5 * GB - 1024, "porcentaje": 0.0, "cuota": 5 * GB})

    def consultar(sql, parametros=None, **_k):
        assert "FROM cuotas WHERE usuario_id" in sql and parametros == (7,)
        return estado["propias"]

    monkeypatch.setattr(api_archivos, "_consultar_bd", consultar)
    app = Flask("prueba")
    app.register_blueprint(api_archivos.bp_archivos, url_prefix="/api/almacen")
    c = app.test_client()
    c.estado = estado
    return c


def test_la_cuota_dice_si_es_propia_o_la_predeterminada(cliente):
    datos = cliente.get("/api/almacen/cuota").get_json()
    assert datos["success"] is True and datos["total_humano"] == "5.0 GB" and datos["cuota_propia"] is False
    cliente.estado["propias"] = [{"?column?": 1}]
    assert cliente.get("/api/almacen/cuota").get_json()["cuota_propia"] is True


def test_el_lector_de_codigo_no_cuenta_los_comentarios():
    from ._explorador import sin_comentarios_js
    fuente = "// ruta /api/x/*.\nconst a = 'https://e.org/*'; /* let def = 20 */ const b = `// no`; // fin\n"
    assert sin_comentarios_js(fuente) == "\nconst a = 'https://e.org/*';  const b = `// no`; \n"
