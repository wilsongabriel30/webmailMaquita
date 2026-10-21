"""Archivos del sitio que root lee y guarda: nunca sigue enlaces simbólicos ni enlaces duros."""

import os
import sys

import pytest

import importlib.util

# deploy/dns/lib también tiene un comun.py: se cargan los de sitios con nombre propio y, mientras
# archivo_seguro se ejecuta, «comun» apunta al de sitios; después se deja como estaba.
_LIB = os.path.join(os.path.dirname(__file__), "..", "..", "deploy", "sitios", "lib")


def _cargar(nombre, archivo):
    spec = importlib.util.spec_from_file_location(nombre, os.path.join(_LIB, archivo))
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


_previo = sys.modules.get("comun")
_comun = sys.modules["comun"] = _cargar("comun_sitios_prueba", "comun.py")
try:
    archivo_seguro = _cargar("archivo_seguro_prueba", "archivo_seguro.py")
finally:
    if _previo is None:
        sys.modules.pop("comun", None)
    else:
        sys.modules["comun"] = _previo
ErrorSitio = _comun.ErrorSitio


@pytest.fixture
def publico(tmp_path):
    p = tmp_path / "publico"
    (p / "tema").mkdir(parents=True)
    (p / "tema" / "estilo.css").write_text("a{}")
    return p


def _yo():
    return os.getuid(), os.getgid()


def test_lee_y_escribe_dentro(publico):
    existe, datos, _ = archivo_seguro.leer(str(publico), "tema/estilo.css", 1000)
    assert existe and datos == b"a{}"
    archivo_seguro.escribir(str(publico), "tema/estilo.css", b"b{}", *_yo(), 0o640)
    assert (publico / "tema" / "estilo.css").read_text() == "b{}"
    assert not [n for n in os.listdir(publico / "tema") if n.endswith(".guardando")]


def test_crea_carpetas_que_faltan(publico):
    archivo_seguro.escribir(str(publico), "nuevo/sub/index.html", b"x", *_yo(), 0o640, carpetas_como=(*_yo(), 0o750))
    assert (publico / "nuevo" / "sub" / "index.html").read_bytes() == b"x"


def test_archivo_enlace_simbolico_rechazado(publico, tmp_path):
    secreto = tmp_path / "secreto"
    secreto.write_text("clave")
    (publico / "enlace.php").symlink_to(secreto)
    with pytest.raises(ErrorSitio):
        archivo_seguro.leer(str(publico), "enlace.php", 1000)


def test_carpeta_enlace_simbolico_no_se_sigue_al_escribir(publico, tmp_path):
    fuera = tmp_path / "fuera"
    fuera.mkdir()
    (publico / "salida").symlink_to(fuera)
    with pytest.raises(ErrorSitio):
        archivo_seguro.escribir(str(publico), "salida/pasado.txt", b"x", *_yo(), 0o640)
    assert list(fuera.iterdir()) == []


def test_enlace_duro_rechazado(publico, tmp_path):
    otro = tmp_path / "otro"
    otro.write_text("ajeno")
    os.link(otro, publico / "duro.txt")
    with pytest.raises(ErrorSitio):
        archivo_seguro.leer(str(publico), "duro.txt", 1000)


@pytest.mark.parametrize("ruta", ["../fuera.txt", "tema/../../x", "", "a\x00b"])
def test_rutas_raras(publico, ruta):
    with pytest.raises(ErrorSitio):
        archivo_seguro.escribir(str(publico), ruta, b"x", *_yo(), 0o640)
