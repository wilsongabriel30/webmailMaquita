"""«Mi sitio web», v1.11: alias, aplicaciones Node.js y Python, git de los sitios PHP, CPU y memoria, información del
servidor y DNS dinámico; y las rutas sin sesión (gancho de git y /nic/update). Alcance (lo ajeno da 404 sin llamar
al intermediario), traducción a órdenes, formas no válidas y auditoría sin secretos. Con el intermediario simulado."""

import base64
import json
import os
import re

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.sesion import admin_actual
from app.sitios import config
from simulado_sitios import BaseSimulada, Intermediario

ADMIN = {"id": 9, "username": "eva", "display_name": "Eva", "sesion_id": 3, "totp": True,
         "debe_cambiar_clave": False, "dominios": ["example.org"]}
CABECERA = {"Authorization": "Bearer ficha-de-prueba-v111-0123456789"}
SECRETO = "clave-que-no-debe-quedar-en-la-auditoria"


@pytest.fixture
def entorno(tmp_path, monkeypatch):
    subidas = tmp_path / "subidas-portal"
    subidas.mkdir()
    simulado = Intermediario(str(subidas))
    monkeypatch.setattr(config, "SOCKET", simulado.socket)
    monkeypatch.setattr(config, "DIR_SUBIDAS", str(subidas))
    app.dependency_overrides[admin_actual] = lambda: ADMIN
    app.state.db = BaseSimulada()
    yield TestClient(app), simulado, subidas
    app.dependency_overrides.clear()
    simulado.cerrar()


AJENAS = [
    ("put", "/api/sitios/{s}/alias", {"alias": []}),
    ("post", "/api/sitios/{s}/propia", {"tipo": "node"}),
    ("get", "/api/sitios/{s}/propia", None),
    ("post", "/api/sitios/{s}/propia/accion", {"accion": "reiniciar"}),
    ("put", "/api/sitios/{s}/propia/entorno", {"variables": {}}),
    ("delete", "/api/sitios/{s}/propia?confirmacion={s}", None),
    ("get", "/api/sitios/{s}/git", None),
    ("put", "/api/sitios/{s}/git", {"repo": "git@git.example.org:a/b.git"}),
    ("post", "/api/sitios/{s}/git/clave", {}),
    ("post", "/api/sitios/{s}/git/gancho", {"accion": "activar"}),
    ("post", "/api/sitios/{s}/git/desplegar", {}),
    ("post", "/api/sitios/{s}/git/volver", {"version": "20261021-101010"}),
    ("delete", "/api/sitios/{s}/git?confirmacion={s}", None),
    ("get", "/api/sitios/{s}/recursos", None),
]
AJENAS_ZONA = [
    ("get", "/api/sitios/dns/{s}/dinamico", None),
    ("post", "/api/sitios/dns/{s}/dinamico", {"nombre": "casa"}),
    ("post", "/api/sitios/dns/{s}/dinamico/0123abcd/clave", {}),
    ("delete", "/api/sitios/dns/{s}/dinamico/0123abcd", None),
]


def _llamar(cliente_http, metodo, ruta, cuerpo):
    return getattr(cliente_http, metodo)(ruta, headers=CABECERA, **({"json": cuerpo} if cuerpo is not None else {}))


@pytest.mark.parametrize("ajeno", ["example.com", "blog.example.com", "example.org.example.com", "noexample.org"])
@pytest.mark.parametrize("metodo,ruta,cuerpo", AJENAS)
def test_lo_ajeno_da_404_sin_llamar(entorno, ajeno, metodo, ruta, cuerpo):
    cliente_http, simulado, _ = entorno
    assert _llamar(cliente_http, metodo, ruta.format(s=ajeno), cuerpo).status_code == 404
    assert simulado.peticiones == []


@pytest.mark.parametrize("ajeno", ["example.com", "blog.example.org"])  # la zona es el dominio exacto
@pytest.mark.parametrize("metodo,ruta,cuerpo", AJENAS_ZONA)
def test_zona_ajena_da_404(entorno, ajeno, metodo, ruta, cuerpo):
    cliente_http, simulado, _ = entorno
    assert _llamar(cliente_http, metodo, ruta.format(s=ajeno), cuerpo).status_code == 404
    assert simulado.peticiones == []


TRADUCCIONES = [
    ("put", "/api/sitios/blog.example.org/alias", {"alias": ["www.Tienda.example.org", "tienda.example.org", ""]},
     "alias", "blog.example.org", {"alias": ["tienda.example.org"]}),
    ("post", "/api/sitios/example.org/propia", {"tipo": "python", "modo": "asgi", "entrada": "app:app", "git": ""},
     "propia-crear", "example.org", {"tipo": "python", "conf": {"modo": "asgi", "entrada": "app:app"}}),
    ("get", "/api/sitios/example.org/propia", None, "propia-estado", "example.org", {}),
    ("post", "/api/sitios/example.org/propia/accion", {"accion": "desplegar"}, "propia-accion", "example.org",
     {"accion": "desplegar"}),
    ("delete", "/api/sitios/example.org/propia?confirmacion=example.org", None, "propia-quitar", "example.org",
     {"confirmacion": "example.org"}),
    ("put", "/api/sitios/example.org/git",
     {"repo": " git@git.example.org:a/b.git ", "rama": "main", "exclusiones": [" subidas ", ""]},
     "git-configurar", "example.org", {"git": {"repo": "git@git.example.org:a/b.git", "rama": "main", "carpeta": "",
                                               "raiz_web": "", "exclusiones": ["subidas"]}}),
    ("get", "/api/sitios/example.org/git", None, "git-estado", "example.org", {}),
    ("post", "/api/sitios/example.org/git/clave", {}, "git-clave", "example.org", {}),
    ("post", "/api/sitios/example.org/git/gancho", {"accion": "desactivar"}, "git-gancho", "example.org",
     {"accion": "desactivar"}),
    ("post", "/api/sitios/example.org/git/desplegar", {}, "git-desplegar", "example.org", {}),
    ("post", "/api/sitios/example.org/git/volver", {"version": "20261021-101010"}, "git-volver", "example.org",
     {"version": "20261021-101010"}),
    ("delete", "/api/sitios/example.org/git?confirmacion=example.org", None, "git-quitar", "example.org",
     {"confirmacion": "example.org"}),
    ("get", "/api/sitios/example.org/recursos", None, "recursos", "example.org", {}),
    ("get", "/api/sitios/servidor", None, "servidor-info", None, {}),
    ("get", "/api/sitios/dns/example.org/dinamico", None, "ddns-ver", "example.org", {}),
    ("post", "/api/sitios/dns/example.org/dinamico", {"nombre": "Casa"}, "ddns-crear", "example.org", {"nombre": "casa"}),
    ("post", "/api/sitios/dns/example.org/dinamico/0123abcd/clave", {}, "ddns-clave", "example.org", {"id": "0123abcd"}),
    ("delete", "/api/sitios/dns/example.org/dinamico/0123abcd", None, "ddns-borrar", "example.org", {"id": "0123abcd"}),
]


@pytest.mark.parametrize("metodo,ruta,cuerpo,orden,dominio,args", TRADUCCIONES)
def test_traduccion(entorno, metodo, ruta, cuerpo, orden, dominio, args):
    cliente_http, simulado, _ = entorno
    r = _llamar(cliente_http, metodo, ruta, cuerpo)
    assert r.status_code in (200, 201, 202), r.text
    p = simulado.peticiones[-1]
    assert (p["orden"], p.get("dominio"), p["args"]) == (orden, dominio, args)
    assert p["ficha"] == CABECERA["Authorization"][7:]


NO_VALIDAS = [
    ("put", "/api/sitios/example.org/alias", {"alias": ["example.com"]}, 400),
    ("put", "/api/sitios/example.org/alias", {"alias": ["tienda.example.com"]}, 400),
    ("put", "/api/sitios/example.org/alias", {"alias": "tienda.example.org"}, 400),
    ("put", "/api/sitios/example.org/alias", {"alias": [3]}, 400),
    ("put", "/api/sitios/example.org/alias", {"alias": [f"a{i}.example.org" for i in range(11)]}, 400),
    ("post", "/api/sitios/example.org/propia", {"tipo": "php"}, 400),
    ("post", "/api/sitios/example.org/propia", {"tipo": "node", "puerto_publico": 30000}, 403),
    ("post", "/api/sitios/example.org/propia", {"tipo": "node", "spa": "sí"}, 400),
    ("post", "/api/sitios/example.org/propia/accion", {"accion": "borrar"}, 400),
    ("put", "/api/sitios/example.org/propia/entorno", {"variables": {"minuscula": "x"}}, 400),
    ("put", "/api/sitios/example.org/propia/entorno", {"variables": {"A": 1}}, 400),
    ("delete", "/api/sitios/example.org/propia?confirmacion=example.com", None, 400),
    ("put", "/api/sitios/example.org/git", {"repo": "x", "otra": 1}, 400),
    ("put", "/api/sitios/example.org/git", {"rama": "main"}, 400),
    ("put", "/api/sitios/example.org/git", {"repo": "x", "exclusiones": ["a"] * 21}, 400),
    ("post", "/api/sitios/example.org/git/gancho", {"accion": "renovar"}, 400),
    ("post", "/api/sitios/example.org/git/volver", {"version": "../x"}, 400),
    ("delete", "/api/sitios/example.org/git", None, 400),
    ("post", "/api/sitios/dns/example.org/dinamico", {"nombre": "casa abierta"}, 400),
    ("post", "/api/sitios/dns/example.org/dinamico/0123ABCD/clave", {}, 400),
    ("delete", "/api/sitios/dns/example.org/dinamico/ZZZZ", None, 400),
]


@pytest.mark.parametrize("metodo,ruta,cuerpo,esperado", NO_VALIDAS)
def test_formas_no_validas_sin_llamar(entorno, metodo, ruta, cuerpo, esperado):
    cliente_http, simulado, _ = entorno
    assert _llamar(cliente_http, metodo, ruta, cuerpo).status_code == esperado
    assert simulado.peticiones == []


def test_auditoria_sin_secretos(entorno):
    cliente_http, simulado, _ = entorno
    simulado.respuestas["git-gancho"] = {"ok": True, "datos": {"secreto": SECRETO, "gancho": True}}
    simulado.respuestas["ddns-crear"] = {"ok": True, "datos": {"clave": SECRETO, "creada": {"usuario": "ddns-0123abcd"}}}
    assert _llamar(cliente_http, "post", "/api/sitios/example.org/git/gancho", {"accion": "activar"}).json()["secreto"] == SECRETO
    assert _llamar(cliente_http, "post", "/api/sitios/dns/example.org/dinamico", {"nombre": "casa"}).json()["clave"] == SECRETO
    _llamar(cliente_http, "put", "/api/sitios/example.org/propia/entorno", {"variables": {"CLAVE_API": SECRETO}})
    auditoria = app.state.db.auditoria
    assert [a[2] for a in auditoria] == ["sitio_git_gancho_activar", "dns_dinamico_crear", "sitio_propia_entorno"]
    assert SECRETO not in json.dumps([list(map(str, a)) for a in auditoria])
    assert json.loads(auditoria[-1][4]) == {"variables": ["CLAVE_API"]}


# --- Sin sesión: gancho de git ---


def _gancho(cliente_http, sitio="example.org", cuerpo=b'{"ref":"refs/heads/main"}', **cabeceras):
    return cliente_http.post(f"/api/publico/git/{sitio}", content=cuerpo, headers=cabeceras)


def test_gancho_pasa_cuerpo_y_firma(entorno):
    cliente_http, simulado, subidas = entorno
    app.dependency_overrides.clear()  # sin sesión
    vistos = []
    responder = simulado.responder

    def leer_y_responder(peticion):
        nombre = peticion["args"]["subida"]
        vistos.append((nombre, (subidas / nombre).read_bytes()))
        return {"ok": True, "datos": {"http": 202, "estado": "en curso", "detalle": "Despliegue iniciado"}}

    simulado.responder = leer_y_responder
    r = _gancho(cliente_http, **{"X-Hub-Signature-256": "sha256=" + "a" * 64, "X-GitHub-Event": "push"})
    simulado.responder = responder
    assert r.status_code == 202 and r.json()["estado"] == "en curso"
    p = simulado.peticiones[-1]
    assert p["orden"] == "gancho-git" and p["dominio"] == "example.org" and p["ficha"] == ""
    assert p["args"]["firma"] == "sha256=" + "a" * 64 and p["args"]["evento"] == "push"
    assert re.fullmatch(r"[0-9a-f]{32}\.gancho", vistos[0][0]) and vistos[0][1] == b'{"ref":"refs/heads/main"}'
    assert os.listdir(subidas) == []  # lo que quede se borra


def test_gancho_gitlab_y_respuesta_del_intermediario(entorno):
    cliente_http, simulado, subidas = entorno
    simulado.respuestas["gancho-git"] = {"ok": False, "codigo": 403, "error": "Firma no válida o gancho sin activar"}
    r = _gancho(cliente_http, **{"X-Gitlab-Token": "ficha", "X-Gitlab-Event": "Push Hook"})
    assert r.status_code == 403 and simulado.peticiones[-1]["args"]["ficha_gitlab"] == "ficha"
    assert os.listdir(subidas) == []


@pytest.mark.parametrize("sitio,cabeceras", [
    ("example.org", {}), ("example.org", {"X-Hub-Signature-256": "a\x01b"}), ("..", {"X-Hub-Signature-256": "x"}),
    ("EXAMPLE..org", {"X-Hub-Signature-256": "x"}), ("x" * 210 + ".org", {"X-Hub-Signature-256": "x"}),
])
def test_gancho_sin_firma_o_raro_no_llama(entorno, sitio, cabeceras):
    cliente_http, simulado, subidas = entorno
    r = _gancho(cliente_http, sitio, **cabeceras)
    assert r.status_code in (403, 404) and simulado.peticiones == [] and os.listdir(subidas) == []


def test_gancho_grande(entorno):
    cliente_http, simulado, subidas = entorno
    r = _gancho(cliente_http, cuerpo=b"x" * (1024 * 1024 + 10), **{"X-Gitea-Signature": "a" * 64})
    assert r.status_code == 413 and simulado.peticiones == [] and os.listdir(subidas) == []


# --- Sin sesión: DNS dinámico (dyndns2) ---


def _basica(usuario, clave):
    return {"Authorization": "Basic " + base64.b64encode(f"{usuario}:{clave}".encode()).decode()}


def test_nic_update(entorno):
    cliente_http, simulado, _ = entorno
    app.dependency_overrides.clear()
    simulado.respuestas["ddns-actualizar"] = {"ok": True, "datos": {"respuesta": "good 203.0.113.5"}}
    r = cliente_http.get("/api/publico/nic/update?hostname=casa.example.org&myip=203.0.113.5",
                         headers={**_basica("ddns-0123abcd", "clave:con:dos:puntos"), "X-Real-IP": "198.51.100.7"})
    assert r.status_code == 200 and r.text == "good 203.0.113.5\n" and r.headers["content-type"].startswith("text/plain")
    p = simulado.peticiones[-1]
    assert p["orden"] == "ddns-actualizar" and "dominio" not in p
    assert p["args"] == {"usuario": "ddns-0123abcd", "clave": "clave:con:dos:puntos", "hostname": "casa.example.org",
                         "myip": "203.0.113.5", "ip_cliente": "198.51.100.7"}


def test_nic_update_sin_credenciales(entorno):
    cliente_http, simulado, _ = entorno
    for cabeceras in ({}, {"Authorization": "Bearer x"}, {"Authorization": "Basic ***"}, _basica("ana", "")):
        r = cliente_http.get("/api/publico/nic/update?hostname=casa.example.org", headers=cabeceras)
        assert r.status_code == 401 and r.text == "badauth\n" and "Basic" in r.headers["www-authenticate"]
    assert simulado.peticiones == []


def test_nic_update_badauth_y_caida(entorno):
    cliente_http, simulado, _ = entorno
    simulado.respuestas["ddns-actualizar"] = {"ok": True, "datos": {"respuesta": "badauth"}}
    r = cliente_http.get("/api/publico/nic/update?hostname=casa.example.org", headers=_basica("ddns-0123abcd", "x"))
    assert r.status_code == 401 and r.text == "badauth\n"
    simulado.respuestas["ddns-actualizar"] = {"ok": False, "codigo": 503, "error": "caído"}
    r = cliente_http.get("/api/publico/nic/update?hostname=casa.example.org", headers=_basica("ddns-0123abcd", "x"))
    assert r.status_code == 503 and r.text == "911\n"
