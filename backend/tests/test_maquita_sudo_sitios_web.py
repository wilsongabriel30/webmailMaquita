"""maquita-sudo: forma exacta de las órdenes nuevas de maquita-sitios (funciones web y cuentas FTP adicionales)."""

import base64
import importlib.machinery
import importlib.util
import json
import os

import pytest

_RUTA = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "deploy",
    "sudoers",
    "maquita-sudo",
)
_loader = importlib.machinery.SourceFileLoader("maquita_sudo_web", _RUTA)
_spec = importlib.util.spec_from_loader("maquita_sudo_web", _loader)
ms = importlib.util.module_from_spec(_spec)
_loader.exec_module(ms)


def b64(valor):
    texto = valor if isinstance(valor, str) else json.dumps(valor)
    return base64.urlsafe_b64encode(texto.encode()).decode().rstrip("=")


def _ok(*args):
    return ms.autorizar("maquita-admin", "maquita-sitios", list(args))


def _no(*args, usuario="maquita-admin"):
    with pytest.raises(ms.Rechazo):
        ms.autorizar(usuario, "maquita-sitios", list(args))


def test_ordenes_permitidas():
    assert _ok("web", "example.org") == ["web", "example.org"]
    assert _ok("web-purgar", "example.org")
    assert _ok("ftp-cuentas", "example.org")
    for orden in ("web-redirecciones", "web-errores", "web-hotlink", "web-bloqueo", "web-optimizacion"):
        assert _ok(orden, "example.org", b64({"a": 1}))
    assert _ok("web-privado-agregar", "example.org", b64("/privado"), "ana")
    assert _ok("web-privado-agregar", "example.org", b64("/privado"), "ana.luz", b64("una clave larga"))
    assert _ok("web-privado-quitar", "example.org", b64("/privado"))
    assert _ok("web-privado-quitar", "example.org", b64("/privado"), "ana")
    assert _ok("ftp-cuenta-crear", "example.org", "disenio", b64("imagenes/2026"))
    assert _ok("ftp-cuenta-clave", "example.org", "disenio")
    assert _ok("ftp-cuenta-quitar", "example.org", "disenio")


def test_listas_largas_hasta_su_tope():
    # 500 IP no caben en 300 caracteres: estas órdenes tienen su propio tope.
    largo = b64(["192.0.2.%d" % (i % 250) for i in range(500)])
    assert len(largo) > 300
    assert _ok("web-bloqueo", "example.org", largo)
    assert _ok("web-redirecciones", "example.org", "A" * 20000)
    _no("web-redirecciones", "example.org", "A" * 20001)
    _no("web-errores", "example.org", "A" * 8001)


@pytest.mark.parametrize(
    "args",
    [
        ["web"],
        ["web", "Example.org"],
        ["web", "example.org\n"],
        ["web-bloqueo", "example.org", "abc\n"],
        ["web", "example.org", "de-mas"],
        ["web-purgar", "example.org;id"],
        ["web-redirecciones", "example.org"],
        ["web-redirecciones", "example.org", "no es base64"],
        ["web-redirecciones", "example.org", "abc\n"],
        ["web-bloqueo", "example.org", "abc{"],
        ["web-hotlink", "example.org", "abc;"],
        ["web-privado-agregar", "example.org", "L3ByaXZhZG8", "ana luz"],
        ["web-privado-agregar", "example.org", "L3ByaXZhZG8", "ana;id"],
        ["web-privado-agregar", "example.org", "L3ByaXZhZG8", "a" * 33],
        ["web-privado-agregar", "example.org", "L3ByaXZhZG8", "ana", "clave con espacios"],
        ["web-privado-agregar", "example.org", "/privado", "ana"],
        ["web-privado-quitar", "example.org", "L3ByaXZhZG8", "ana", "otra"],
        ["ftp-cuenta-crear", "example.org", "Ana", "aW1hZ2VuZXM"],
        ["ftp-cuenta-crear", "example.org", "1ana", "aW1hZ2VuZXM"],
        ["ftp-cuenta-crear", "example.org", "ana_", "aW1hZ2VuZXM"],
        ["ftp-cuenta-crear", "example.org", "anaanaanaana", "aW1hZ2VuZXM"],
        ["ftp-cuenta-crear", "example.org", "ana", "../etc"],
        ["ftp-cuenta-clave", "example.org", "ana", "extra"],
        ["ftp-cuenta-quitar", "example.org"],
        ["ftp-montar"],  # solo del sistema (al arrancar), no del panel
        ["web-algo", "example.org"],
    ],
)
def test_rechaza(args):
    _no(*args)


def test_salto_de_linea_final_rechazado_en_todas_las_ordenes():
    # «$» de una expresión regular admite un «\n» final: el envoltorio compara la cadena entera.
    _no("ftp", "example.org\n", "activar")
    _no("ssl", "example.org", "a@example.org\n")


def test_www_data_no_puede():
    _no("web", "example.org", usuario="www-data")


def test_contrasena_enmascarada_en_el_registro():
    linea = ms._enmascarar("maquita-sitios", ["web-privado-agregar", "example.org", b64("/privado"), "ana", b64("secreta-123")])
    assert b64("secreta-123") not in linea and linea.endswith("***")
