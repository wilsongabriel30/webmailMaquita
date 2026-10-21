"""«Mi sitio web», v1.10: funciones web, cuentas FTP adicionales, registros, estadísticas, disponibilidad, copias y
administrador de archivos. Alcance (lo ajeno da 404 sin llamar al intermediario), traducción a órdenes, formas
no válidas, auditoría sin contraseñas y entrega de descargas de un solo uso. Con el intermediario simulado."""

import json
import os
import re
import time

import pytest

from app.main import app
from app.sitios import descargas
from test_sitios import CABECERA, CLAVE, entorno  # noqa: F401  (entorno es la fijación)

HEX = "0123456789abcdef0123456789abcdef"

AJENAS = [
    ("get", "/api/sitios/dos.example/web", None),
    ("put", "/api/sitios/dos.example/web/redirecciones", {"redirecciones": []}),
    ("put", "/api/sitios/dos.example/web/errores", {"paginas": {}}),
    ("put", "/api/sitios/dos.example/web/hotlink", {"activo": True}),
    ("put", "/api/sitios/dos.example/web/bloqueo", {"redes": ["203.0.113.7"]}),
    ("put", "/api/sitios/dos.example/web/optimizacion", {"compresion": True}),
    ("post", "/api/sitios/dos.example/web/purgar", {}),
    ("post", "/api/sitios/dos.example/web/privacidad", {"carpeta": "/p", "usuario": "ana"}),
    ("delete", "/api/sitios/dos.example/web/privacidad?carpeta=/p", None),
    ("get", "/api/sitios/dos.example/ftp/cuentas", None),
    ("post", "/api/sitios/dos.example/ftp/cuentas", {"nombre": "ana", "carpeta": "x"}),
    ("post", "/api/sitios/dos.example/ftp/cuentas/ana/clave", {}),
    ("delete", "/api/sitios/dos.example/ftp/cuentas/ana", None),
    ("get", "/api/sitios/dos.example/registros/error", None),
    ("get", "/api/sitios/dos.example/estadisticas", None),
    ("post", "/api/sitios/dos.example/estadisticas/generar", {}),
    ("post", "/api/sitios/dos.example/estadisticas/informe", {}),
    ("get", "/api/sitios/dos.example/disponibilidad", None),
    ("get", "/api/sitios/dos.example/copias", None),
    ("post", "/api/sitios/dos.example/copias", {}),
    ("post", "/api/sitios/dos.example/copias/20261021-101010/descargar", {}),
    ("post", "/api/sitios/dos.example/copias/20261021-101010/restaurar", {}),
    ("delete", "/api/sitios/dos.example/copias/20261021-101010", None),
    ("get", "/api/sitios/dos.example/archivos", None),
    ("post", "/api/sitios/dos.example/archivos/descargar", {"ruta": "a.txt"}),
    ("post", "/api/sitios/dos.example/archivos/carpeta", {"ruta": "x"}),
    ("post", "/api/sitios/dos.example/archivos/mover", {"origen": "a", "destino": "b"}),
    ("post", "/api/sitios/dos.example/archivos/copiar", {"origen": "a", "destino": "b"}),
    ("post", "/api/sitios/dos.example/archivos/descomprimir", {"origen": "a.zip", "destino": "."}),
    ("post", "/api/sitios/dos.example/archivos/borrar", {"ruta": "a"}),
    ("post", "/api/sitios/dos.example/archivos/comprimir", {"rutas": ["a"], "destino": "a.zip"}),
    ("post", "/api/sitios/dos.example/archivos/permisos", {"ruta": "a", "modo": "644"}),
    ("get", "/api/sitios/dos.example/archivos/papelera", None),
    ("post", "/api/sitios/dos.example/archivos/papelera/0123456789ab/recuperar", {}),
    ("delete", "/api/sitios/dos.example/archivos/papelera", None),
    ("get", "/api/sitios/blog.dos.example/web", None),
    ("get", "/api/sitios/uno.example.dos.example/archivos", None),
]


@pytest.mark.parametrize("metodo,ruta,cuerpo", AJENAS)
def test_otro_dominio_da_404_sin_llamar(entorno, metodo, ruta, cuerpo):  # noqa: F811
    cliente_http, simulado, _ = entorno
    r = getattr(cliente_http, metodo)(ruta, headers=CABECERA, **({"json": cuerpo} if cuerpo is not None else {}))
    assert r.status_code == 404
    assert simulado.peticiones == []


def test_subir_a_lo_ajeno_da_404_y_no_escribe(entorno):  # noqa: F811
    cliente_http, simulado, subidas = entorno
    r = cliente_http.put("/api/sitios/dos.example/archivos/subir?nombre=a.txt", headers=CABECERA, content=b"hola")
    assert r.status_code == 404 and simulado.peticiones == [] and os.listdir(subidas) == []


TRADUCCIONES = [
    ("get", "/api/sitios/blog.uno.example/web", None, "web", {}),
    ("put", "/api/sitios/uno.example/web/redirecciones", {"redirecciones": [{"origen": "/a", "destino": "/b"}]},
     "web-redirecciones", {"redirecciones": [{"origen": "/a", "destino": "/b"}]}),
    ("put", "/api/sitios/uno.example/web/errores", {"paginas": {"404": "/404.html"}}, "web-errores", {"paginas": {"404": "/404.html"}}),
    ("put", "/api/sitios/uno.example/web/hotlink", {"activo": True}, "web-hotlink", {"hotlink": {"activo": True}}),
    ("put", "/api/sitios/uno.example/web/bloqueo", {"redes": [" 203.0.113.7 ", ""]}, "web-bloqueo", {"redes": ["203.0.113.7"]}),
    ("put", "/api/sitios/uno.example/web/optimizacion", {"cache_pagina": True}, "web-optimizacion", {"optimizacion": {"cache_pagina": True}}),
    ("post", "/api/sitios/uno.example/web/purgar", {}, "web-purgar", {}),
    ("delete", "/api/sitios/uno.example/web/privacidad?carpeta=/p&usuario=ana", None, "web-privado-quitar", {"carpeta": "/p", "usuario": "ana"}),
    ("delete", "/api/sitios/uno.example/web/privacidad?carpeta=/p", None, "web-privado-quitar", {"carpeta": "/p"}),
    ("get", "/api/sitios/uno.example/ftp/cuentas", None, "ftp-cuentas", {}),
    ("post", "/api/sitios/uno.example/ftp/cuentas/ana/clave", {}, "ftp-cuenta-clave", {"nombre": "ana"}),
    ("delete", "/api/sitios/uno.example/ftp/cuentas/ana", None, "ftp-cuenta-quitar", {"nombre": "ana"}),
    ("get", "/api/sitios/uno.example/registros/php?lineas=50&filtro=fatal", None, "registros", {"tipo": "php", "lineas": 50, "filtro": "fatal"}),
    ("get", "/api/sitios/uno.example/registros/acceso", None, "registros", {"tipo": "acceso", "lineas": 200}),
    ("get", "/api/sitios/uno.example/estadisticas", None, "estadisticas", {}),
    ("post", "/api/sitios/uno.example/estadisticas/generar", {}, "estadisticas-generar", {}),
    ("get", "/api/sitios/uno.example/disponibilidad", None, "disponibilidad", {}),
    ("get", "/api/sitios/uno.example/copias", None, "copias", {}),
    ("post", "/api/sitios/uno.example/copias", {}, "copia-crear", {}),
    ("post", "/api/sitios/uno.example/copias/20261021-101010/restaurar", {}, "copia-restaurar", {"id": "20261021-101010"}),
    ("delete", "/api/sitios/uno.example/copias/20261021-101010", None, "copia-borrar", {"id": "20261021-101010"}),
    ("get", "/api/sitios/uno.example/archivos?ruta=/wp-content", None, "archivos-listar", {"ruta": "wp-content"}),
    ("get", "/api/sitios/uno.example/archivos", None, "archivos-listar", {"ruta": "."}),
    ("post", "/api/sitios/uno.example/archivos/carpeta", {"ruta": "nueva"}, "archivos-carpeta", {"ruta": "nueva"}),
    ("post", "/api/sitios/uno.example/archivos/mover", {"origen": "a", "destino": "b"}, "archivos-mover", {"origen": "a", "destino": "b"}),
    ("post", "/api/sitios/uno.example/archivos/descomprimir", {"origen": "a.zip", "destino": ""}, "archivos-descomprimir",
     {"origen": "a.zip", "destino": "."}),
    ("post", "/api/sitios/uno.example/archivos/borrar", {"ruta": "/a"}, "archivos-borrar", {"ruta": "a"}),
    ("post", "/api/sitios/uno.example/archivos/comprimir", {"rutas": ["a", "b"], "destino": "c.zip"}, "archivos-comprimir",
     {"rutas": ["a", "b"], "destino": "c.zip"}),
    ("post", "/api/sitios/uno.example/archivos/permisos", {"ruta": "a", "modo": "600"}, "archivos-permisos", {"ruta": "a", "modo": "600"}),
    ("get", "/api/sitios/uno.example/archivos/papelera", None, "archivos-papelera", {}),
    ("post", "/api/sitios/uno.example/archivos/papelera/0123456789ab/recuperar", {}, "archivos-recuperar", {"id": "0123456789ab"}),
    ("delete", "/api/sitios/uno.example/archivos/papelera", None, "archivos-vaciar", {}),
]


@pytest.mark.parametrize("metodo,ruta,cuerpo,orden,args", TRADUCCIONES)
def test_traduccion(entorno, metodo, ruta, cuerpo, orden, args):  # noqa: F811
    cliente_http, simulado, _ = entorno
    r = getattr(cliente_http, metodo)(ruta, headers=CABECERA, **({"json": cuerpo} if cuerpo is not None else {}))
    assert r.status_code in (200, 201), r.text
    p = simulado.peticiones[-1]
    assert (p["orden"], p["args"]) == (orden, args)


MAL = [
    ("put", "/api/sitios/uno.example/web/redirecciones", {"redirecciones": "x"}),
    ("put", "/api/sitios/uno.example/web/redirecciones", {"redirecciones": [{}] * 201}),
    ("put", "/api/sitios/uno.example/web/errores", {"paginas": {"200": "/x.html"}}),
    ("put", "/api/sitios/uno.example/web/bloqueo", {"redes": [7]}),
    ("post", "/api/sitios/uno.example/web/privacidad", {"carpeta": 7, "usuario": "ana"}),
    ("post", "/api/sitios/uno.example/ftp/cuentas", {"nombre": "Ana", "carpeta": "x"}),
    ("post", "/api/sitios/uno.example/ftp/cuentas", {"nombre": "ana", "carpeta": ""}),
    ("post", "/api/sitios/uno.example/ftp/cuentas/ANA/clave", {}),
    ("get", "/api/sitios/uno.example/registros/sistema", None),
    ("get", "/api/sitios/uno.example/registros/error?lineas=1001", None),
    ("get", "/api/sitios/uno.example/registros/error?filtro=" + "x" * 101, None),
    ("post", "/api/sitios/uno.example/copias/2026-10-21/restaurar", {}),
    ("post", "/api/sitios/uno.example/copias/20261021-101010x/descargar", {}),
    ("get", "/api/sitios/uno.example/archivos?ruta=../../etc", None),
    ("post", "/api/sitios/uno.example/archivos/borrar", {"ruta": "/"}),
    ("post", "/api/sitios/uno.example/archivos/descargar", {"ruta": "a\\..\\b"}),
    ("post", "/api/sitios/uno.example/archivos/mover", {"origen": "a", "destino": "../b"}),
    ("post", "/api/sitios/uno.example/archivos/comprimir", {"rutas": [], "destino": "c.zip"}),
    ("post", "/api/sitios/uno.example/archivos/permisos", {"ruta": "a", "modo": "777"}),
    ("post", "/api/sitios/uno.example/archivos/papelera/xyz/recuperar", {}),
]


@pytest.mark.parametrize("metodo,ruta,cuerpo", MAL)
def test_formas_no_validas_no_llegan(entorno, metodo, ruta, cuerpo):  # noqa: F811
    cliente_http, simulado, _ = entorno
    r = getattr(cliente_http, metodo)(ruta, headers=CABECERA, **({"json": cuerpo} if cuerpo is not None else {}))
    assert r.status_code == 400, r.text
    assert simulado.peticiones == []


def _auditado() -> str:
    return json.dumps([list(map(str, fila)) for fila in app.state.db.auditoria])


def test_contrasenas_una_vez_y_sin_auditar(entorno):  # noqa: F811
    cliente_http, simulado, _ = entorno
    simulado.respuestas["web-privado-agregar"] = {"ok": True, "datos": {"carpeta": "/p", "usuario": "ana", "clave": CLAVE}}
    simulado.respuestas["ftp-cuenta-crear"] = {"ok": True, "datos": {"usuario": "ana_uno", "clave": CLAVE}}
    r = cliente_http.post("/api/sitios/uno.example/web/privacidad", headers=CABECERA, json={"carpeta": "/p", "usuario": "ana"})
    assert r.json()["clave"] == CLAVE
    cliente_http.post("/api/sitios/uno.example/web/privacidad", headers=CABECERA,
                      json={"carpeta": "/p", "usuario": "luis", "clave": CLAVE})
    assert simulado.peticiones[-1]["args"]["clave"] == CLAVE  # la propia viaja al intermediario…
    r = cliente_http.post("/api/sitios/uno.example/ftp/cuentas", headers=CABECERA, json={"nombre": "ana", "carpeta": "/imagenes/"})
    assert r.status_code == 201 and r.json()["clave"] == CLAVE
    assert simulado.peticiones[-1]["args"] == {"nombre": "ana", "carpeta": "imagenes"}
    acciones = [f[2] for f in app.state.db.auditoria]
    assert acciones == ["sitio_web_privado_agregar", "sitio_web_privado_agregar", "sitio_ftp_cuenta_crear"]
    assert CLAVE not in _auditado()  # …pero ninguna queda en la auditoría


def test_subir_archivo(entorno):  # noqa: F811
    cliente_http, simulado, subidas = entorno
    r = cliente_http.put("/api/sitios/uno.example/archivos/subir?nombre=..%2Fhola%20ñ.txt&carpeta=/docs&reemplazar=1",
                         headers=CABECERA, content=b"hola")
    assert r.status_code == 200, r.text
    p = simulado.peticiones[-1]
    assert p["orden"] == "archivos-subir" and p["args"]["ruta"] == "docs/hola ñ.txt" and p["args"]["reemplazar"] is True
    assert re.fullmatch(r"[0-9a-f]{32}\.subida", p["args"]["subida"]) and p["args"]["subida_contenido"] == "hola"
    assert os.listdir(subidas) == []
    assert app.state.db.auditoria[-1][2] == "sitio_archivo_subir"
    for nombre in ("..", "", "a%00b"):
        assert cliente_http.put(f"/api/sitios/uno.example/archivos/subir?nombre={nombre}", headers=CABECERA, content=b"x").status_code == 400
    r = cliente_http.put("/api/sitios/uno.example/archivos/subir?nombre=g.bin", headers=CABECERA, content=b"0" * (70 * 1024))
    assert r.status_code == 413 and os.listdir(subidas) == []


# --- Descargas de un solo uso ---


def _preparar(simulado, subidas, orden, contenido, nombre):
    def responder(peticion):
        (subidas / (HEX + ".descarga")).write_bytes(contenido)
        return {"ok": True, "datos": {"descarga": HEX + ".descarga", "nombre": nombre, "bytes": len(contenido)}}

    original = simulado.responder
    simulado.responder = lambda p: responder(p) if p["orden"] == orden else original(p)


def test_informe_con_sandbox_y_un_solo_uso(entorno):  # noqa: F811
    cliente_http, simulado, subidas = entorno
    _preparar(simulado, subidas, "estadisticas-informe", b"<script>alert(1)</script>", "estadisticas-uno.example.html")
    r = cliente_http.post("/api/sitios/uno.example/estadisticas/informe", headers=CABECERA).json()
    assert r["enlace"] == f"/api/sitios/descargas/{HEX}.descarga?nombre=estadisticas-uno.example.html&ver=1"
    v = cliente_http.get(r["enlace"])  # sin cabecera de sesión: el enlace es el permiso
    assert v.status_code == 200 and v.content == b"<script>alert(1)</script>"
    assert v.headers["content-security-policy"].startswith("sandbox") and "inline" in v.headers["content-disposition"]
    assert os.listdir(subidas) == []
    assert cliente_http.get(r["enlace"]).status_code == 410


def test_copia_se_descarga_como_adjunto(entorno):  # noqa: F811
    cliente_http, simulado, subidas = entorno
    _preparar(simulado, subidas, "copia-descargar", b"\x1f\x8bcopia", "uno.example-20261021-101010.tar.gz")
    r = cliente_http.post("/api/sitios/uno.example/copias/20261021-101010/descargar", headers=CABECERA).json()
    assert simulado.peticiones[-1]["args"] == {"id": "20261021-101010"} and app.state.db.auditoria[-1][2] == "sitio_copia_descargar"
    v = cliente_http.get(r["enlace"] + "&ver=1")  # «ver» solo vale para un .html
    assert v.status_code == 200 and v.content == b"\x1f\x8bcopia"
    assert v.headers["content-type"] == "application/octet-stream" and "attachment" in v.headers["content-disposition"]


def test_descarga_caducada_o_inventada(entorno, monkeypatch):  # noqa: F811
    cliente_http, simulado, subidas = entorno
    _preparar(simulado, subidas, "archivos-descargar", b"x", "a.txt")
    r = cliente_http.post("/api/sitios/uno.example/archivos/descargar", headers=CABECERA, json={"ruta": "a.txt"}).json()
    viejo = time.time() - descargas.VIGENCIA - 5
    os.utime(subidas / (HEX + ".descarga"), (viejo, viejo))
    assert cliente_http.get(r["enlace"]).status_code == 410 and os.listdir(subidas) == []
    for falso in ("../../etc/passwd", HEX + ".txt", HEX + ".subida", "x" * 32 + ".descarga"):
        assert cliente_http.get("/api/sitios/descargas/" + falso).status_code in (404, 410)


def test_descarga_que_es_un_enlace_simbolico(entorno, tmp_path):  # noqa: F811
    cliente_http, _, subidas = entorno
    secreto = tmp_path / "secreto"
    secreto.write_text("clave")
    os.symlink(secreto, subidas / (HEX + ".descarga"))
    assert cliente_http.get(f"/api/sitios/descargas/{HEX}.descarga").status_code == 404
    assert secreto.read_text() == "clave"


def test_respuesta_rara_del_intermediario(entorno):  # noqa: F811
    cliente_http, simulado, _ = entorno
    simulado.respuestas["archivos-descargar"] = {"ok": True, "datos": {"descarga": "../../etc/shadow"}}
    assert cliente_http.post("/api/sitios/uno.example/archivos/descargar", headers=CABECERA, json={"ruta": "a"}).status_code == 502


def test_las_descargas_olvidadas_se_borran(entorno):  # noqa: F811
    _, _, subidas = entorno
    viejo = time.time() - descargas.VIGENCIA - 5
    for n in (HEX + ".descarga", HEX + ".descarga.12.entregando", HEX + ".zip"):
        (subidas / n).write_bytes(b"x")
        os.utime(subidas / n, (viejo, viejo))
    descargas.limpiar_viejas()
    # La entregando (puede ser una descarga lenta en curso) espera un día; la subida la limpia subidas.py.
    assert sorted(os.listdir(subidas)) == sorted([HEX + ".descarga.12.entregando", HEX + ".zip"])
