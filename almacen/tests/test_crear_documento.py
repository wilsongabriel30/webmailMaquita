# -*- coding: utf-8 -*-
"""«Nuevo → Documento (Word)»: POST /api/almacen/archivos/crear.

Respondía 405 Method Not Allowed: la ruta no existía en el Almacén del webmail y la
petición caía en el comodín `/api/almacen/<path>`, registrado solo para GET.
"""
import contextlib
import io
import os
import sys
import zipfile

import pytest
from flask import Flask

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(RAIZ, "servicio"))
os.environ.setdefault("ALMACEN_CLAVE_SESION", "valor-de-prueba-del-ci-no-es-un-secreto-0123")  # gitleaks:allow
os.environ.setdefault("WEBMAIL_SECRET_KEY", "valor-de-prueba-del-ci-no-es-un-secreto-4567")  # gitleaks:allow

import api_crear  # noqa: E402
import plantillas_office  # noqa: E402


# ── el paquete en blanco de cada tipo es un OOXML válido ─────────────────
@pytest.mark.parametrize("extension, principal", [
    ("docx", "word/document.xml"), ("xlsx", "xl/workbook.xml"), ("pptx", "ppt/presentation.xml")])
def test_documento_vacio_es_ooxml(extension, principal):
    datos = plantillas_office.documento_vacio(extension)
    with zipfile.ZipFile(io.BytesIO(datos)) as zf:
        assert zf.testzip() is None
        nombres = zf.namelist()
        assert nombres[0] == "[Content_Types].xml" and "_rels/.rels" in nombres and principal in nombres
        import xml.dom.minidom
        for nombre in nombres:
            xml.dom.minidom.parseString(zf.read(nombre))   # todo XML bien formado
        tipos = zf.read("[Content_Types].xml").decode()
        for nombre in nombres:
            if not nombre.endswith(".rels") and nombre != "[Content_Types].xml":
                assert "/" + nombre in tipos, "%s sin tipo de contenido" % nombre


def test_documento_vacio_abre_con_las_librerias_de_office():
    """Si están instaladas (no lo están en el CI del Almacén), se abre de verdad."""
    docx = pytest.importorskip("docx")
    openpyxl = pytest.importorskip("openpyxl")
    pptx = pytest.importorskip("pptx")
    assert len(docx.Document(io.BytesIO(plantillas_office.documento_vacio("docx"))).paragraphs) == 1
    assert openpyxl.load_workbook(io.BytesIO(plantillas_office.documento_vacio("xlsx"))).sheetnames == ["Hoja1"]
    assert len(pptx.Presentation(io.BytesIO(plantillas_office.documento_vacio("pptx"))).slides) == 1


# ── la ruta ──────────────────────────────────────────────────────────────
@pytest.fixture
def cliente(monkeypatch, tmp_path):
    subidos = []

    def subir(usuario, carpeta, nombre, flujo, tamano_esperado=0):
        ruta = ("" if carpeta == "/" else carpeta) + "/" + nombre
        destino = tmp_path / ruta.strip("/")
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_bytes(flujo.read())
        subidos.append((usuario, carpeta, nombre))
        return {"ruta": ruta, "tamano_humano": "1 KB"}

    monkeypatch.setattr(api_crear.nucleo, "subir", subir)
    monkeypatch.setattr(api_crear, "ruta_fisica", lambda u, r, **_k: str(tmp_path / r.strip("/")))
    monkeypatch.setattr(api_crear, "usuario_actual", lambda: 7)
    monkeypatch.setattr(api_crear, "_permiso_unidad", lambda u, c, escritura=False: True)
    monkeypatch.setattr(api_crear, "registrar_actividad", lambda *a, **k: None)
    app = Flask("prueba")
    app.register_blueprint(api_crear.bp_crear, url_prefix="/api/almacen")
    c = app.test_client()
    c.subidos, c.carpeta = subidos, tmp_path
    return c


def test_nuevo_documento_word_crea_un_docx(cliente):
    r = cliente.post("/api/almacen/archivos/crear", json={"ruta": "/Informes/Acta.docx", "tipo": "documento"})
    assert r.status_code == 201 and r.get_json()["success"] is True
    assert cliente.subidos == [(7, "/Informes", "Acta.docx")]
    with zipfile.ZipFile(cliente.carpeta / "Informes" / "Acta.docx") as zf:
        assert "word/document.xml" in zf.namelist()


def test_sin_extension_toma_la_del_tipo(cliente):
    r = cliente.post("/api/almacen/archivos/crear", json={"ruta": "/Cuentas", "tipo": "hoja"})
    assert r.status_code == 201 and r.get_json()["nombre"] == "Cuentas.xlsx"


def test_diagrama_y_texto(cliente):
    assert cliente.post("/api/almacen/archivos/crear", json={"ruta": "/a.drawio", "tipo": "diagrama"}).status_code == 201
    assert b"mxGraphModel" in (cliente.carpeta / "a.drawio").read_bytes()
    assert cliente.post("/api/almacen/archivos/crear", json={"ruta": "/b.txt", "tipo": "texto"}).status_code == 201
    assert (cliente.carpeta / "b.txt").read_bytes() == b""


def test_no_pisa_un_archivo_que_ya_existe(cliente):
    (cliente.carpeta / "Acta.docx").write_bytes(b"lo que ya escribi")
    r = cliente.post("/api/almacen/archivos/crear", json={"ruta": "/Acta.docx", "tipo": "documento"})
    assert r.status_code == 409 and cliente.subidos == []
    assert (cliente.carpeta / "Acta.docx").read_bytes() == b"lo que ya escribi"


def test_sin_permiso_de_edicion_en_la_unidad(cliente, monkeypatch):
    monkeypatch.setattr(api_crear, "_permiso_unidad", lambda u, c, escritura=False: False)
    r = cliente.post("/api/almacen/archivos/crear", json={"ruta": "/Unidad/x.docx", "tipo": "documento"})
    assert r.status_code == 403 and cliente.subidos == []


@pytest.mark.parametrize("ruta", ["", "/", "/carpeta/", "/..", "a\x00b.docx"])
def test_rutas_invalidas(cliente, ruta):
    r = cliente.post("/api/almacen/archivos/crear", json={"ruta": ruta, "tipo": "documento"})
    assert r.status_code == 400 and cliente.subidos == []


def test_subir_de_nivel_queda_dentro_de_la_unidad(cliente):
    r = cliente.post("/api/almacen/archivos/crear", json={"ruta": "/../../fuera.docx", "tipo": "documento"})
    assert r.status_code == 201 and cliente.subidos == [(7, "/", "fuera.docx")]


# ── el registro en las dos aplicaciones ──────────────────────────────────
def _app_webmail(monkeypatch):
    """Construye la app real del webmail sin base de datos (el DDL de arranque se anula)."""
    import alias_correo
    import app_webmail
    import cuota_admision
    import ddl_arranque
    monkeypatch.setattr(ddl_arranque, "serializado", lambda _pool: contextlib.nullcontext())
    for modulo, nombre in ((app_webmail, "asegurar_esquema"), (app_webmail, "asegurar_tablas_webmail"),
                           (app_webmail, "asegurar_tablas_externas"), (cuota_admision, "asegurar_tabla"),
                           (alias_correo, "asegurar_tabla_alias")):
        monkeypatch.setattr(modulo, nombre, lambda *a, **k: None)
    return app_webmail.crear_app_webmail()


def test_app_webmail_publica_post_archivos_crear(monkeypatch):
    app = _app_webmail(monkeypatch)
    enlace = app.url_map.bind("mail.example.org")
    endpoint, _ = enlace.match("/api/almacen/archivos/crear", method="POST")
    assert endpoint == "almacen_crear.crear_documento"


def test_comodin_del_contrato_responde_404_a_cualquier_metodo(monkeypatch):
    """Antes solo GET: un POST a una ruta que faltaba salía 405 y escondía el fallo."""
    app = _app_webmail(monkeypatch)
    enlace = app.url_map.bind("mail.example.org")
    for metodo in ("GET", "POST", "PUT", "PATCH", "DELETE"):
        endpoint, _ = enlace.match("/api/almacen/no-existe/todavia", method=metodo)
        assert endpoint == "_no_implementado"


def test_app_almacen_tambien_registra_la_ruta():
    with open(os.path.join(RAIZ, "servicio", "app_almacen.py"), encoding="utf-8") as f:
        fuente = f.read()
    assert "register_blueprint(bp_crear, url_prefix='/api/nextcloud')" in fuente


def test_el_explorador_llama_a_esta_ruta_por_post():
    ruta = os.path.join(RAIZ, "servicio", "estaticos", "js", "nextcloud", "explorador-interactions.js")
    with open(ruta, encoding="utf-8") as f:
        fuente = f.read()
    bloque = fuente.split("${API_BASE}/archivos/crear`", 1)[1][:80]
    assert "method: 'POST'" in bloque
