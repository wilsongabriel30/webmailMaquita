"""«Mi sitio web»: autenticación de git del sitio (repositorios privados del sitio PHP y de la aplicación propia).
Lo ajeno da 404 sin llamar al intermediario, cada método se traduce a la orden y el secreto no queda en la
auditoría. Con el intermediario simulado y valores ficticios evidentes."""

import json

import pytest

from app.main import app
from test_sitios_v111_portal import CABECERA, _llamar, entorno  # noqa: F401  (entorno es la fijación)

RUTA = "/api/sitios/{s}/git/credencial"
TOKEN = "token-ficticio-de-prueba-0000"
CLAVE = "-----BEGIN OPENSSH PRIVATE KEY-----\nZmljdGljaWEtZGUtcHJ1ZWJh\n-----END OPENSSH PRIVATE KEY-----\n"


@pytest.mark.parametrize("ajeno", ["example.com", "blog.example.com", "noexample.org"])
@pytest.mark.parametrize("metodo,cuerpo", [("get", None), ("put", {"metodo": "ninguna"}), ("delete", None)])
def test_lo_ajeno_da_404(entorno, ajeno, metodo, cuerpo):  # noqa: F811
    cliente_http, simulado, _ = entorno
    assert _llamar(cliente_http, metodo, RUTA.format(s=ajeno), cuerpo).status_code == 404
    assert simulado.peticiones == []


@pytest.mark.parametrize("cuerpo,credencial", [
    ({"metodo": "clave-generada", "repo": "git@git.example.org:a/b.git"},
     {"metodo": "clave-generada", "regenerar": False, "repo": "git@git.example.org:a/b.git"}),
    ({"metodo": "clave-generada", "regenerar": True}, {"metodo": "clave-generada", "regenerar": True}),
    ({"metodo": "clave-propia", "repo": "git@git.example.org:a/b.git", "clave_privada": CLAVE},
     {"metodo": "clave-propia", "regenerar": False, "repo": "git@git.example.org:a/b.git", "clave_privada": CLAVE}),
    ({"metodo": "token-https", "repo": "https://git.example.org/a/b.git", "token": TOKEN, "usuario": ""},
     {"metodo": "token-https", "regenerar": False, "repo": "https://git.example.org/a/b.git", "token": TOKEN}),
    ({"metodo": "usuario-contrasena", "repo": "https://git.example.org/a/b.git", "usuario": "ana", "contrasena": "ficticia"},
     {"metodo": "usuario-contrasena", "regenerar": False, "repo": "https://git.example.org/a/b.git", "usuario": "ana",
      "contrasena": "ficticia"}),
])
def test_traduccion(entorno, cuerpo, credencial):  # noqa: F811
    cliente_http, simulado, _ = entorno
    r = _llamar(cliente_http, "put", RUTA.format(s="example.org"), cuerpo)
    assert r.status_code == 200, r.text
    p = simulado.peticiones[-1]
    assert (p["orden"], p["dominio"], p["args"]) == ("git-credencial-guardar", "example.org", {"credencial": credencial})


def test_ver_y_borrar(entorno):  # noqa: F811
    cliente_http, simulado, _ = entorno
    assert _llamar(cliente_http, "get", RUTA.format(s="example.org"), None).status_code == 200
    assert simulado.peticiones[-1]["orden"] == "git-credencial"
    assert _llamar(cliente_http, "delete", RUTA.format(s="example.org"), None).status_code == 200
    assert simulado.peticiones[-1]["orden"] == "git-credencial-borrar"


@pytest.mark.parametrize("cuerpo", [{}, {"metodo": "otro"}, {"metodo": "ninguna", "otro": 1},
                                    {"metodo": "token-https", "token": "x" * 513}, {"metodo": "token-https", "token": 5}])
def test_formas_no_validas(entorno, cuerpo):  # noqa: F811
    cliente_http, simulado, _ = entorno
    assert _llamar(cliente_http, "put", RUTA.format(s="example.org"), cuerpo).status_code == 400
    assert simulado.peticiones == []


def test_auditoria_solo_el_metodo(entorno):  # noqa: F811
    cliente_http, _, _ = entorno
    _llamar(cliente_http, "put", RUTA.format(s="example.org"),
            {"metodo": "token-https", "repo": "https://git.example.org/a/b.git", "token": TOKEN})
    _llamar(cliente_http, "put", RUTA.format(s="example.org"),
            {"metodo": "clave-propia", "repo": "git@git.example.org:a/b.git", "clave_privada": CLAVE})
    auditoria = app.state.db.auditoria
    assert [a[2] for a in auditoria] == ["sitio_git_credencial", "sitio_git_credencial"]
    texto = json.dumps([list(map(str, a)) for a in auditoria])
    assert TOKEN not in texto and "ZmljdGljaWEt" not in texto and "token-https" in texto
