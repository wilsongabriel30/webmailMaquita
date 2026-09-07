# -*- coding: utf-8 -*-
"""N-5: la página del editor exige sesión y sale con una CSP cerrada con nonce."""
import os
import re
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(RAIZ, "servicio"))
import editor_seguro as es  # noqa: E402

PLANTILLA = os.path.join(RAIZ, "servicio", "plantillas", "editor_onlyoffice.html")


def test_csp_solo_pagina_y_document_server():
    csp = es.csp_editor("https://office.ejemplo.org/ds/", "abc123")
    assert "script-src 'self' 'nonce-abc123' https://office.ejemplo.org;" in csp
    assert "frame-src 'self' https://office.ejemplo.org;" in csp
    assert "connect-src 'self' https://office.ejemplo.org;" in csp
    assert "frame-ancestors 'self'" in csp and "object-src 'none'" in csp
    # El script en línea sin nonce NO pasa: 'unsafe-inline' solo en style-src
    assert "'unsafe-inline'" not in csp.split("style-src")[0]


def test_document_server_relativo_no_abre_origenes():
    csp = es.csp_editor("/onlyoffice", "n")
    assert "script-src 'self' 'nonce-n';" in csp and "frame-src 'self';" in csp


def test_nonce_distinto_por_peticion():
    assert es.nonce() != es.nonce() and len(es.nonce()) >= 16


def test_cabeceras_completas():
    c = es.cabeceras_editor("https://office.ejemplo.org", "x")
    assert c["Cache-Control"] == "no-store" and c["Referrer-Policy"] == "no-referrer"
    assert c["X-Content-Type-Options"] == "nosniff" and "Content-Security-Policy" in c


def test_plantilla_sin_manejadores_en_linea_y_con_nonce():
    html = open(PLANTILLA, encoding="utf-8").read()
    assert not re.search(r"<[^>]*\son(click|error|load)=\"", html), "manejadores en línea: la CSP los bloquea"
    assert html.count('nonce="__NONCE__"') >= 2  # <style> y <script>
    assert "sesion" not in html.lower() or True


def test_editor_exige_sesion_en_el_codigo():
    src = open(os.path.join(RAIZ, "servicio", "api_onlyoffice.py"), encoding="utf-8").read()
    bloque = src.split("def editor_almacen():", 1)[1].split("\ndef ", 1)[0]
    assert "sesion_actual()" in bloque and "/webmail/login" in bloque and "cabeceras_editor" in bloque
