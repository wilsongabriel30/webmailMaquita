"""maquita-sudo: forma exacta de las órdenes de observación y datos de maquita-sitios (registros, estadísticas,
disponibilidad, copias del sitio y administrador de archivos)."""

import base64
import importlib.machinery
import importlib.util
import os

import pytest

_RUTA = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                     "deploy", "sudoers", "maquita-sudo")
_loader = importlib.machinery.SourceFileLoader("maquita_sudo_datos", _RUTA)
_spec = importlib.util.spec_from_loader("maquita_sudo_datos", _loader)
ms = importlib.util.module_from_spec(_spec)
_loader.exec_module(ms)

D = "example.org"


def b64(texto):
    return base64.urlsafe_b64encode(texto.encode()).decode().rstrip("=")


def _ok(*args):
    return ms.autorizar("maquita-admin", "maquita-sitios", list(args), comprobar_buzon=lambda b: True)


def _no(*args):
    with pytest.raises(ms.Rechazo):
        _ok(*args)


@pytest.mark.parametrize("args", [
    ("registros", D, "error", "200"),
    ("registros", D, "acceso", "1000", b64("wp-login")),
    ("registros", D, "php", "1"),
    ("estadisticas", D), ("estadisticas-generar", D), ("estadisticas-informe", D),
    ("disponibilidad", D),
    ("copias", D), ("copia-crear", D),
    ("copia-descargar", D, "20261021-103000"), ("copia-restaurar", D, "20261021-103000"),
    ("copia-borrar", D, "20261021-103000"),
    ("archivos-listar", D, b64(".")), ("archivos-descargar", D, b64("css/estilo.css")),
    ("archivos-carpeta", D, b64("nueva")), ("archivos-borrar", D, b64("viejo.php")),
    ("archivos-subir", D, b64("index.html"), "0" * 32 + ".subida"),
    ("archivos-subir", D, b64("index.html"), "a" * 32 + ".subida", "reemplazar"),
    ("archivos-mover", D, b64("a.txt"), b64("b.txt")), ("archivos-copiar", D, b64("a"), b64("b")),
    ("archivos-descomprimir", D, b64("x.zip"), b64(".")),
    ("archivos-comprimir", D, b64('{"rutas": ["a"], "destino": "a.zip"}')),
    ("archivos-permisos", D, b64("index.php"), "640"),
    ("archivos-papelera", D), ("archivos-vaciar", D), ("archivos-recuperar", D, "0123456789ab"),
])
def test_ordenes_de_datos_permitidas(args):
    assert _ok(*args) == list(args)


def test_rutas_largas_en_archivos():
    larga = b64("carpeta/" * 120 + "archivo.txt")
    assert len(larga) > 300
    assert _ok("archivos-listar", D, larga)
    assert _ok("archivos-comprimir", D, b64('{"rutas": [' + ",".join(['"a"'] * 2000) + '], "destino": "a.zip"}'))


@pytest.mark.parametrize("args", [
    ("registros", D, "error"),
    ("registros", D, "../error", "10"),
    ("registros", D, "error", "0"),
    ("registros", D, "error", "1001"),
    ("registros", D, "error", "10", "con espacios"),
    ("registros", "no_es_dominio", "error", "10"),
    ("estadisticas", D, "extra"),
    ("copia-crear", D, "ahora"),
    ("copia-restaurar", D, "../../etc"),
    ("copia-borrar", D, "2026-10-21"),
    ("archivos-listar", D, "../etc"),
    ("archivos-listar", D, "/etc/passwd"),
    ("archivos-listar", D),
    ("archivos-subir", D, b64("a"), "../../etc/shadow"),
    ("archivos-subir", D, b64("a"), "0" * 32 + ".txt"),
    ("archivos-subir", D, b64("a"), "0" * 32 + ".subida", "pisar"),
    ("archivos-mover", D, b64("a")),
    ("archivos-permisos", D, b64("a"), "777"),
    ("archivos-permisos", D, b64("a"), "4755"),
    ("archivos-recuperar", D, "../x"),
    ("archivos-vaciar", D, "todo"),
    ("archivos-listar", D, "a\nb"),
    ("disponibilidad-comprobar",),
    ("datos-noche",),
    ("disponibilidad-comprobar", D),
])
def test_ordenes_de_datos_rechazadas(args):
    _no(*args)


def test_solo_el_panel():
    with pytest.raises(ms.Rechazo):
        ms.autorizar("www-data", "maquita-sitios", ["archivos-listar", D, b64(".")])
