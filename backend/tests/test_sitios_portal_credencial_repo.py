"""maquita-sitios-portal: autenticación de git del sitio (repositorios privados de los sitios PHP y de las aplicaciones
propias). El secreto pasa a maquita-sitios en un archivo 0600 de subidas/ y nunca en los argumentos; la orden que lo
muestra es de lectura. Mismo mundo de dobles que test_sitios_portal.py: el validador de maquita-sudo es el real."""

import json
import os
import socket
import stat

import pytest

from tests.test_sitios_portal import codigo, mundo, pedir  # noqa: F401  (mundo es la fijación)

import fichas  # noqa: E402
import portal  # noqa: E402
import red  # noqa: E402
import rutas  # noqa: E402

# Valores ficticios evidentes: no son credenciales de verdad.
TOKEN = "token-ficticio-de-prueba-0000"
CLAVE = "-----BEGIN OPENSSH PRIVATE KEY-----\nZmljdGljaWEtZGUtcHJ1ZWJh\n-----END OPENSSH PRIVATE KEY-----\n"


@pytest.fixture
def m(mundo, monkeypatch):  # noqa: F811
    mundo.sitio("example.org")
    monkeypatch.setattr(red, "es_publica", lambda d: str(d).startswith("203.0.113."))
    monkeypatch.setattr(socket, "getaddrinfo", lambda host, *a, **k: {
        "git.example.org": [(2, 1, 6, "", ("203.0.113.20", 0))],
        "interno.example.org": [(2, 1, 6, "", ("192.0.2.5", 0))],
    }.get(host) or (_ for _ in ()).throw(socket.gaierror("no existe")))
    vistos = []

    def guardar(args):
        """Lo que maquita-sitios encontraría en subidas/ (el archivo y sus permisos), y lo borra como él."""
        ruta = os.path.join(rutas.SUBIDAS, args[2])
        vistos.append((json.load(open(ruta)), stat.S_IMODE(os.stat(ruta).st_mode)))
        os.remove(ruta)
        return {"metodo": vistos[-1][0]["metodo"], "configurada": True}

    mundo.ayudante.respuestas[("maquita-sitios", "git-credencial-guardar")] = guardar
    mundo.vistos = vistos
    return mundo


def test_ordenes_y_lectura():
    for orden in ("git-credencial", "git-credencial-guardar", "git-credencial-borrar"):
        assert portal.ORDENES[orden][0] == "sitio"
    assert "git-credencial" in portal.ORDENES_LECTURA and "git-credencial" in fichas.LECTURA
    for orden in ("git-credencial-guardar", "git-credencial-borrar"):
        assert orden not in portal.ORDENES_LECTURA and orden not in fichas.LECTURA


def test_ver_y_borrar(m):
    pedir("git-credencial", "example.org")
    assert m.ayudante.ultima == ["maquita-sitios", "git-credencial", "example.org"]
    pedir("git-credencial-borrar", "example.org")
    assert m.ayudante.ultima == ["maquita-sitios", "git-credencial-borrar", "example.org"]


@pytest.mark.parametrize("credencial", [
    {"metodo": "clave-generada", "repo": "git@git.example.org:ana/app.git"},
    {"metodo": "clave-propia", "repo": "ssh://git@git.example.org/ana/app.git", "clave_privada": CLAVE},
    {"metodo": "token-https", "repo": "https://git.example.org/ana/app.git", "token": TOKEN},
    {"metodo": "usuario-contrasena", "repo": "https://git.example.org/ana/app.git", "usuario": "ana",
     "contrasena": "contraseña ficticia"},
    {"metodo": "ninguna", "repo": "https://git.example.org/ana/app.git"},
])
def test_guardar_por_archivo_y_no_en_los_argumentos(m, credencial):
    pedir("git-credencial-guardar", "example.org", credencial=credencial)
    orden = m.ayudante.ultima
    assert orden[:3] == ["maquita-sitios", "git-credencial-guardar", "example.org"] and len(orden) == 4
    assert orden[3].endswith(".cred") and len(orden[3]) == 37
    datos, modo = m.vistos[-1]
    assert modo == 0o600 and datos == {**credencial, "regenerar": False}
    secretos = [credencial.get(k) for k in ("clave_privada", "token", "contrasena") if credencial.get(k)]
    assert not any(s in " ".join(orden) for s in secretos)
    assert os.listdir(rutas.SUBIDAS) == []


def test_la_subida_no_se_queda_si_falla(m):
    m.ayudante.respuestas[("maquita-sitios", "git-credencial-guardar")] = {"error": "credencial rechazada"}
    assert codigo("git-credencial-guardar", "example.org",
                  credencial={"metodo": "token-https", "repo": "https://git.example.org/a/b.git", "token": TOKEN}) == 400
    assert os.listdir(rutas.SUBIDAS) == []


@pytest.mark.parametrize("credencial", [
    None, "texto", {"metodo": "otro"}, {"metodo": "token-https", "desconocido": 1},
    {"metodo": "token-https", "token": "a\nb"}, {"metodo": "token-https", "token": "x" * 513},
    {"metodo": "clave-propia", "clave_privada": "x" * 16385}, {"metodo": "ninguna", "repo": "git@interno.example.org:a/b.git"},
    {"metodo": "token-https", "repo": f"https://ana:{TOKEN}@git.example.org/a/b.git", "token": TOKEN},
    {"metodo": "ninguna", "repo": "file:///etc/passwd"},
])
def test_formas_no_validas(m, credencial):
    assert codigo("git-credencial-guardar", "example.org", credencial=credencial) == 400
    assert m.ayudante.llamadas == [] and os.listdir(rutas.SUBIDAS) == []


def test_ajeno_no(m):
    m.sitio("example.com")
    for orden in ("git-credencial", "git-credencial-guardar", "git-credencial-borrar"):
        assert codigo(orden, "example.com", credencial={"metodo": "ninguna"}) == 404
    assert m.ayudante.llamadas == []
