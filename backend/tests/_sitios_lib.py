"""Carga los módulos del ayudante de sitios (deploy/sitios/lib) para las pruebas, sin root.

deploy/dns/lib también tiene un «comun.py»: se cargan con el de sitios y después se deja sys.modules como
estaba, para no romper las pruebas de DNS (los módulos cargados guardan su referencia al «comun» correcto).
"""

import importlib
import os
import sys

RUTA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "deploy", "sitios", "lib")
CHOQUES = ("comun", "validacion")
NOMBRES = ("comun", "validacion", "como_usuario", "archivos_rutas", "archivos", "archivos_papelera", "archivos_zip",
           "archivos_ordenes", "visor_registros", "estadisticas", "disponibilidad", "copias_cliente", "ordenes_datos",
           # v1.11: git de los sitios PHP y CPU y memoria por sitio
           "red_publica", "git_sitio", "git_despliegue", "recursos", "ordenes_v111")

_cargados = None


def cargar():
    global _cargados
    if _cargados:
        return _cargados
    guardados = {n: sys.modules.pop(n) for n in CHOQUES if n in sys.modules}
    sys.path.insert(0, RUTA)
    try:
        _cargados = {n: importlib.import_module(n) for n in NOMBRES}
    finally:
        sys.path.remove(RUTA)
        for n in CHOQUES:
            sys.modules.pop(n, None)
        sys.modules.update(guardados)
    _cargados["como_usuario"].CAMBIAR_USUARIO = False  # sin root: todo en el mismo proceso
    return _cargados


def sitio(tmp_path, monkeypatch, dominio="example.org", **extra):
    """Un sitio de prueba con su metadato en una carpeta temporal."""
    m = cargar()
    meta_dir = tmp_path / "meta"
    meta_dir.mkdir(exist_ok=True)
    monkeypatch.setattr(m["comun"], "META_DIR", str(meta_dir))
    base = tmp_path / "srv" / dominio
    for carpeta in ("publico", "tmp", "registros"):
        (base / carpeta).mkdir(parents=True, exist_ok=True)
    meta = {"dominio": dominio, "usuario": "web0000", "base": str(base), "publico": str(base / "publico"),
            "tmp": str(base / "tmp"), "registros": str(base / "registros"), "ssl": True, **extra}
    m["comun"].guardar_meta(meta)
    return meta
