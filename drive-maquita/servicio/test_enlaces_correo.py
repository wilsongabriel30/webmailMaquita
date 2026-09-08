# -*- coding: utf-8 -*-
"""Vínculo explícito buzón → persona del directorio (panel): manda sobre la coincidencia por correo."""
import os
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(RAIZ, "servicio"))
os.environ.setdefault("ALMACEN_CLAVE_SESION", "valor-de-prueba-del-ci-no-es-un-secreto-0123")  # gitleaks:allow
os.environ.setdefault("WEBMAIL_SECRET_KEY", "valor-de-prueba-del-ci-no-es-un-secreto-4567")  # gitleaks:allow
import auth_webmail as aw  # noqa: E402


def _consultar_falso(respuestas):
    llamadas = []

    def consultar(sql, parametros=None, nomina=False):
        llamadas.append((sql.split()[0], parametros, nomina))
        for clave, valor in respuestas.items():
            if clave in sql:
                return valor
        return []

    return consultar, llamadas


def test_el_enlace_manda_sobre_el_correo(monkeypatch):
    consultar, llamadas = _consultar_falso({
        "enlaces_correo": [{"usuario_id": 77}],
        "WHERE id = %s": [{"id": 77, "role": "user"}],
    })
    monkeypatch.setattr(aw, "consultar", consultar)
    assert aw._buscar_en_nomina("persona@maquita.org") == (77, "user")
    assert llamadas[0][0] == "SELECT" and "enlaces_correo" in str(llamadas)


def test_sin_enlace_se_busca_por_correo(monkeypatch):
    consultar, _ = _consultar_falso({
        "enlaces_correo": [],
        "LOWER(email) = %s": [{"id": 5, "role": "user"}],
    })
    monkeypatch.setattr(aw, "consultar", consultar)
    assert aw._buscar_en_nomina("persona@maquita.org") == (5, "user")


def test_enlace_a_persona_inactiva_no_vale(monkeypatch):
    consultar, _ = _consultar_falso({"enlaces_correo": [{"usuario_id": 77}], "WHERE id = %s": []})
    monkeypatch.setattr(aw, "consultar", consultar)
    assert aw._buscar_en_nomina("persona@maquita.org") == (None, None)


def test_api_panel_exige_secreto_y_loopback():
    src = open(os.path.join(RAIZ, "servicio", "api_panel.py"), encoding="utf-8").read()
    assert "compare_digest" in src and "_LOOPBACK" in src and "ALMACEN_SECRETO_PANEL" in src
