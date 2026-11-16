# -*- coding: utf-8 -*-
"""Presentación del editor en línea (hallazgo 26 de Andes, 15/11/2026).

En el editor se veía el idioma «English – United States» y una pestaña «AI». La interfaz ya
se pedía en español (`lang: 'es'`); lo que estaba en inglés era el idioma del DOCUMENTO: los
documentos en blanco no lo declaraban. La pestaña «AI» se oculta con
`customization.ai.disabled`. No se toca nada relativo a macros.
"""
import io
import os
import sys
import zipfile

import pytest

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(RAIZ, "servicio"))
os.environ.setdefault("ALMACEN_CLAVE_SESION", "valor-de-prueba-del-ci-no-es-un-secreto-0123")  # gitleaks:allow
os.environ.setdefault("WEBMAIL_SECRET_KEY", "valor-de-prueba-del-ci-no-es-un-secreto-4567")  # gitleaks:allow

import editor_presentacion as ep  # noqa: E402
import plantillas_office  # noqa: E402


@pytest.fixture(autouse=True)
def _entorno_limpio(monkeypatch):
    monkeypatch.delenv("ALMACEN_ONLYOFFICE_REGION", raising=False)
    monkeypatch.delenv("ALMACEN_ONLYOFFICE_IA", raising=False)


def test_region_por_defecto_y_configurable(monkeypatch):
    assert ep.region() == "es-ES" and ep.idioma_documento() == "es-ES"
    monkeypatch.setenv("ALMACEN_ONLYOFFICE_REGION", "es-EC")
    assert ep.region() == "es-EC" and ep.idioma_documento() == "es-EC"


@pytest.mark.parametrize("valor", ["es", "ES-ec", "es_EC", "español", "es-EC\"><x", ""])
def test_una_region_mal_escrita_no_llega_al_editor(monkeypatch, valor):
    monkeypatch.setenv("ALMACEN_ONLYOFFICE_REGION", valor)
    assert ep.region() == "es-ES"


def test_la_pestana_ai_queda_oculta_salvo_que_se_pida(monkeypatch):
    assert ep.personalizacion() == {"ai": {"disabled": True}}
    monkeypatch.setenv("ALMACEN_ONLYOFFICE_IA", "1")
    assert ep.personalizacion() == {"ai": {"disabled": False}}


def test_la_presentacion_no_toca_macros_ni_complementos():
    claves = set(ep.personalizacion())
    assert not claves & {"macros", "macrosMode", "plugins"}


def test_las_dos_configuraciones_del_editor_la_usan():
    fuente = open(os.path.join(RAIZ, "servicio", "api_onlyoffice.py"), encoding="utf-8").read()
    for funcion in ("def onlyoffice_config():", "def onlyoffice_config_public():"):
        bloque = fuente.split(funcion, 1)[1].split("\n@bp_onlyoffice", 1)[0]
        assert "'lang': 'es'," in bloque, funcion
        assert "'region': editor_presentacion.region()," in bloque, funcion
        assert "**editor_presentacion.personalizacion()," in bloque, funcion
        # la configuración se firma DESPUÉS de completarla
        assert bloque.index("editor_presentacion.personalizacion()") < bloque.index("config['token'] = firmar_jwt(config)")
        assert "'macros'" not in bloque and "'plugins'" not in bloque


def _parte(extension, nombre):
    with zipfile.ZipFile(io.BytesIO(plantillas_office.documento_vacio(extension))) as zf:
        return zf.read(nombre).decode("utf-8")


def test_el_documento_en_blanco_declara_su_idioma(monkeypatch):
    assert '<w:lang w:val="es-ES" w:eastAsia="es-ES"/>' in _parte("docx", "word/styles.xml")
    assert 'Target="styles.xml"' in _parte("docx", "word/_rels/document.xml.rels")
    monkeypatch.setenv("ALMACEN_ONLYOFFICE_REGION", "es-PE")
    assert 'w:val="es-PE"' in _parte("docx", "word/styles.xml")


def test_la_presentacion_en_blanco_declara_su_idioma():
    presentacion = _parte("pptx", "ppt/presentation.xml")
    assert '<p:defaultTextStyle><a:defPPr><a:defRPr lang="es-ES"/></a:defPPr></p:defaultTextStyle>' in presentacion
    # orden del esquema: el estilo de texto va después del tamaño de las notas
    assert presentacion.index("<p:notesSz") < presentacion.index("<p:defaultTextStyle>")


def test_la_pestana_ia_se_desactiva_tambien_por_la_lista_de_complementos(monkeypatch):
    # servidores de documentos que no conocen `customization.ai.disabled` (reprueba de Andes, 15/11/2026)
    assert ep.complementos() == {"disable": [ep.COMPLEMENTO_IA]}
    monkeypatch.setenv("ALMACEN_ONLYOFFICE_IA", "1")
    assert ep.complementos() == {}


def test_las_dos_configuraciones_del_editor_envian_los_complementos():
    ruta = os.path.join(RAIZ, "servicio", "api_onlyoffice.py")
    with open(ruta, encoding="utf-8") as f:
        codigo = "\n".join(l for l in f.read().splitlines() if not l.lstrip().startswith("#"))
    assert codigo.count("'plugins': editor_presentacion.complementos()") == 2
