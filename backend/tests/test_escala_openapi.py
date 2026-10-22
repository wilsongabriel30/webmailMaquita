"""Exportación de la especificación OpenAPI (scripts/exportar-openapi.py)."""

import importlib.util
import json
import os
import subprocess
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SCRIPT = os.path.join(RAIZ, "scripts", "exportar-openapi.py")


def _modulo():
    spec = importlib.util.spec_from_file_location("exportar_openapi", SCRIPT)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def test_copia_v1_reescribe_solo_las_rutas_de_la_api():
    m = _modulo()
    esquema = {
        "info": {"title": "Webmail API"},
        "paths": {"/api/mail/x": {"get": {}}, "/autodiscover/x": {"post": {}}},
    }
    v1 = m.a_v1(esquema)
    assert set(v1["paths"]) == {"/api/v1/mail/x", "/autodiscover/x"}
    assert v1["info"]["title"] == "Webmail API v1"
    assert "/api/mail/x" in esquema["paths"]  # el original no se toca


def test_el_esquema_del_webmail_se_genera_sin_servicios():
    r = subprocess.run(
        [sys.executable, SCRIPT, "--interno", "webmail"],
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert r.returncode == 0, r.stderr[-1500:]
    rutas = json.loads(r.stdout)["paths"]
    assert "/api/salud" in rutas and "/api/listo" in rutas
    assert "/api/auth/login" in rutas
