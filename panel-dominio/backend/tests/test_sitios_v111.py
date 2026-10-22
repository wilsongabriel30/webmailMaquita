"""«Mi sitio web», v1.11: usuarios de bases con permisos y acceso remoto, cortafuegos de aplicaciones y claves SSH.
Alcance (lo ajeno da 404 sin llamar al intermediario), traducción a órdenes, formas no válidas (inyección en
identificadores, redes demasiado amplias) y auditoría sin contraseñas. Con el intermediario simulado."""

import json

import pytest

from test_sitios import CABECERA, entorno  # noqa: F401  (entorno es la fijación)

U = "u_uno1234_lector"

AJENAS = [
    ("get", "/api/sitios/dos.example/bases/usuarios", None),
    ("post", "/api/sitios/dos.example/bases/usuarios", {"base": "w_dos1234", "sufijo": "lector", "permisos": {"perfil": "lectura"}}),
    ("put", f"/api/sitios/dos.example/bases/usuarios/{U}/permisos", {"permisos": {"perfil": "todo"}}),
    ("post", f"/api/sitios/dos.example/bases/usuarios/{U}/clave", {}),
    ("put", f"/api/sitios/dos.example/bases/usuarios/{U}/remoto", {"redes": ["192.0.2.10"]}),
    ("delete", f"/api/sitios/dos.example/bases/usuarios/{U}", None),
    ("get", "/api/sitios/dos.example/cortafuegos", None),
    ("put", "/api/sitios/dos.example/cortafuegos", {"modo": "apagado"}),
    ("get", "/api/sitios/dos.example/cortafuegos/bloqueos", None),
    ("get", "/api/sitios/dos.example/ssh/claves", None),
    ("post", "/api/sitios/dos.example/ssh/claves", {"cuenta": "principal", "clave": "ssh-ed25519 AAAA"}),
    ("delete", "/api/sitios/dos.example/ssh/claves/0a1b2c3d", None),
    ("get", "/api/sitios/blog.dos.example/cortafuegos", None),
]


@pytest.mark.parametrize("metodo,ruta,cuerpo", AJENAS)
def test_otro_dominio_da_404_sin_llamar(entorno, metodo, ruta, cuerpo):  # noqa: F811
    cliente_http, simulado, _ = entorno
    r = getattr(cliente_http, metodo)(ruta, headers=CABECERA, **({"json": cuerpo} if cuerpo is not None else {}))
    assert r.status_code == 404
    assert simulado.peticiones == []


TRADUCCIONES = [
    ("get", "/api/sitios/uno.example/bases/usuarios", None, "bases-usuarios", {}),
    ("post", "/api/sitios/uno.example/bases/usuarios", {"base": "w_uno1234", "sufijo": "lector", "permisos": {"perfil": "lectura"}},
     "base-usuario-crear", {"base": "w_uno1234", "sufijo": "lector", "permisos": {"perfil": "lectura"}}),
    ("put", f"/api/sitios/uno.example/bases/usuarios/{U}/permisos", {"permisos": {"perfil": "medida", "lista": ["SELECT"]}},
     "base-usuario-permisos", {"usuario": U, "permisos": {"perfil": "medida", "lista": ["SELECT"]}}),
    ("post", f"/api/sitios/uno.example/bases/usuarios/{U}/clave", {}, "base-usuario-clave", {"usuario": U}),
    ("put", f"/api/sitios/uno.example/bases/usuarios/{U}/remoto", {"redes": [" 192.0.2.10 ", "198.51.100.0/24", ""]},
     "base-usuario-remoto", {"usuario": U, "redes": ["192.0.2.10/32", "198.51.100.0/24"]}),
    ("delete", f"/api/sitios/uno.example/bases/usuarios/{U}", None, "base-usuario-borrar", {"usuario": U}),
    ("get", "/api/sitios/blog.uno.example/cortafuegos", None, "waf", {}),
    ("put", "/api/sitios/uno.example/cortafuegos", {"modo": "detectar", "paranoia": 2, "exclusiones": [{"regla": 942100, "ruta": "/wp-admin/"}]},
     "waf-guardar", {"waf": {"modo": "detectar", "paranoia": 2, "exclusiones": [{"regla": 942100, "ruta": "/wp-admin/"}]}}),
    ("get", "/api/sitios/uno.example/cortafuegos/bloqueos?cuantos=20", None, "waf-bloqueos", {"cuantos": 20}),
    ("get", "/api/sitios/uno.example/ssh/claves", None, "ssh-claves", {}),
    ("post", "/api/sitios/uno.example/ssh/claves", {"cuenta": "disenio", "clave": " ssh-ed25519 AAAAC3 ana@example.org "},
     "ssh-clave-agregar", {"cuenta": "disenio", "clave": "ssh-ed25519 AAAAC3 ana@example.org"}),
    ("delete", "/api/sitios/uno.example/ssh/claves/0a1b2c3d", None, "ssh-clave-borrar", {"id": "0a1b2c3d"}),
]


@pytest.mark.parametrize("metodo,ruta,cuerpo,orden,args", TRADUCCIONES)
def test_traduccion_a_ordenes(entorno, metodo, ruta, cuerpo, orden, args):  # noqa: F811
    cliente_http, simulado, _ = entorno
    r = getattr(cliente_http, metodo)(ruta, headers=CABECERA, **({"json": cuerpo} if cuerpo is not None else {}))
    assert r.status_code in (200, 201), r.text
    assert simulado.peticiones[-1]["orden"] == orden and simulado.peticiones[-1]["args"] == args


NO_VALIDAS = [
    ("post", "/api/sitios/uno.example/bases/usuarios", {"base": "mysql", "sufijo": "lector", "permisos": {"perfil": "lectura"}}),
    ("post", "/api/sitios/uno.example/bases/usuarios", {"base": "w_uno1234`; DROP", "sufijo": "lector", "permisos": {"perfil": "lectura"}}),
    ("post", "/api/sitios/uno.example/bases/usuarios", {"base": "w_uno1234", "sufijo": "a'; DROP USER root;--", "permisos": {"perfil": "lectura"}}),
    ("post", "/api/sitios/uno.example/bases/usuarios", {"base": "w_uno1234", "sufijo": "Lector", "permisos": {"perfil": "lectura"}}),
    ("post", "/api/sitios/uno.example/bases/usuarios", {"base": "w_uno1234", "sufijo": "lector", "permisos": {"perfil": "superusuario"}}),
    ("post", "/api/sitios/uno.example/bases/usuarios", {"base": "w_uno1234", "sufijo": "lector",
                                                        "permisos": {"perfil": "medida", "lista": ["SELECT; DROP"]}}),
    ("put", "/api/sitios/uno.example/bases/usuarios/root/permisos", {"permisos": {"perfil": "todo"}}),
    ("post", "/api/sitios/uno.example/bases/usuarios/u_uno1234_x'--/clave", {}),
    ("put", f"/api/sitios/uno.example/bases/usuarios/{U}/remoto", {"redes": ["0.0.0.0/0"]}),
    ("put", f"/api/sitios/uno.example/bases/usuarios/{U}/remoto", {"redes": ["::/0"]}),
    ("put", f"/api/sitios/uno.example/bases/usuarios/{U}/remoto", {"redes": ["172.16.0.0/12"]}),
    ("put", f"/api/sitios/uno.example/bases/usuarios/{U}/remoto", {"redes": ["2001:db8::/32"]}),
    ("put", f"/api/sitios/uno.example/bases/usuarios/{U}/remoto", {"redes": ["todas"]}),
    ("put", f"/api/sitios/uno.example/bases/usuarios/{U}/remoto", {"redes": ["192.0.2.1"] * 21}),
    ("put", "/api/sitios/uno.example/cortafuegos", {"modo": "apagar"}),
    ("put", "/api/sitios/uno.example/cortafuegos", {"paranoia": 4}),
    ("put", "/api/sitios/uno.example/cortafuegos", {"exclusiones": [{"regla": "942100"}]}),
    ("put", "/api/sitios/uno.example/cortafuegos", {"exclusiones": [{"regla": 42}]}),
    ("put", "/api/sitios/uno.example/cortafuegos", {"exclusiones": [{"regla": 942100, "ruta": '/a" "id:1,allow'}]}),
    ("post", "/api/sitios/uno.example/ssh/claves", {"cuenta": "../root", "clave": "ssh-ed25519 AAAA"}),
    ("post", "/api/sitios/uno.example/ssh/claves", {"cuenta": "principal", "clave": "ssh-ed25519 AAAA\nssh-rsa BBBB"}),
    ("post", "/api/sitios/uno.example/ssh/claves", {"cuenta": "principal", "clave": ""}),
    ("delete", "/api/sitios/uno.example/ssh/claves/..%2F..%2Fetc", None),
]


@pytest.mark.parametrize("metodo,ruta,cuerpo", NO_VALIDAS)
def test_formas_no_validas_sin_llamar(entorno, metodo, ruta, cuerpo):  # noqa: F811
    cliente_http, simulado, _ = entorno
    r = getattr(cliente_http, metodo)(ruta, headers=CABECERA, **({"json": cuerpo} if cuerpo is not None else {}))
    assert r.status_code in (400, 404, 422)
    assert simulado.peticiones == []


def test_la_clave_nueva_no_queda_en_la_auditoria(entorno):  # noqa: F811
    cliente_http, simulado, _ = entorno
    from app.main import app

    simulado.respuestas["base-usuario-crear"] = {"ok": True, "datos": {"creado": {"usuario": U, "clave": "Zq9-secreta"}}}
    r = cliente_http.post("/api/sitios/uno.example/bases/usuarios", headers=CABECERA,
                          json={"base": "w_uno1234", "sufijo": "lector", "permisos": {"perfil": "lectura"}})
    assert r.json()["creado"]["clave"] == "Zq9-secreta"
    assert "Zq9-secreta" not in json.dumps([list(map(str, a)) for a in app.state.db.auditoria])
    assert any(a[2] == "sitio_base_usuario_crear" for a in app.state.db.auditoria)


def test_la_clave_ssh_se_audita_por_su_huella(entorno):  # noqa: F811
    cliente_http, simulado, _ = entorno
    from app.main import app

    simulado.respuestas["ssh-clave-agregar"] = {"ok": True, "datos": {"agregada": {"tipo": "ssh-ed25519", "huella": "SHA256:x"}}}
    cliente_http.post("/api/sitios/uno.example/ssh/claves", headers=CABECERA,
                      json={"cuenta": "principal", "clave": "ssh-ed25519 AAAAC3NzaDatosDeLaClave ana@example.org"})
    fila = next(a for a in app.state.db.auditoria if a[2] == "sitio_ssh_clave_agregar")
    assert "SHA256:x" in fila[4] and "AAAAC3NzaDatosDeLaClave" not in fila[4]
