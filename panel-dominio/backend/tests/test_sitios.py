"""«Mi sitio web»: alcance en el portal, reenvío de la ficha, errores del intermediario, baja,
subidas con tope y auditoría sin contraseñas. Con el intermediario simulado (simulado_sitios)."""

import json
import os
import re

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.main import app
from app.sesion import admin_actual
from app.sitios import cliente, config
from simulado_sitios import BaseSimulada, Intermediario

ADMIN = {"id": 7, "username": "ana", "display_name": "Ana", "sesion_id": 1, "totp": True,
         "debe_cambiar_clave": False, "dominios": ["uno.example"]}
FICHA = "ficha-de-prueba-0123456789"
CABECERA = {"Authorization": "Bearer " + FICHA}
CLAVE = "Zq9-clave-que-no-debe-quedar"


@pytest.fixture
def entorno(tmp_path, monkeypatch):
    subidas = tmp_path / "subidas-portal"
    subidas.mkdir()
    simulado = Intermediario(str(subidas))
    monkeypatch.setattr(config, "SOCKET", simulado.socket)
    monkeypatch.setattr(config, "DIR_SUBIDAS", str(subidas))
    monkeypatch.setattr(config, "SUBIDA_MAX_BYTES", 64 * 1024)
    monkeypatch.setattr(config, "ARCHIVO_MAX_BYTES", 4 * 1024)
    from app.sitios import inicio
    inicio._revisiones.clear()
    app.dependency_overrides[admin_actual] = lambda: ADMIN
    app.state.db = BaseSimulada()
    yield TestClient(app), simulado, subidas
    app.dependency_overrides.clear()
    simulado.cerrar()


AJENAS = [
    ("post", "/api/sitios", {"sitio": "dos.example"}),
    ("post", "/api/sitios", {"sitio": "uno.example.dos.example"}),
    ("post", "/api/sitios", {"sitio": "nouno.example"}),
    ("get", "/api/sitios/dos.example/estado", None),
    ("post", "/api/sitios/dos.example/app", {"aplicacion": "wordpress", "titulo": "x", "correo": "a@dos.example"}),
    ("post", "/api/sitios/dos.example/entrar", {}),
    ("post", "/api/sitios/blog.dos.example/clave-admin", {}),
    ("post", "/api/sitios/dos.example/https", {"correo": "a@dos.example"}),
    ("post", "/api/sitios/dos.example/ftp", {"accion": "activar"}),
    ("post", "/api/sitios/dos.example/revisar", {}),
    ("post", "/api/sitios/dos.example/actualizar", {}),
    ("get", "/api/sitios/dos.example/tareas", None),
    ("put", "/api/sitios/dos.example/tareas", {"trabajos": []}),
    ("post", "/api/sitios/dos.example/tareas/0123abcd/ejecutar", {}),
    ("get", "/api/sitios/dos.example/bases", None),
    ("post", "/api/sitios/dos.example/bases", {"motor": "mariadb"}),
    ("delete", "/api/sitios/dos.example/bases/x_dos_ab12", None),
    ("get", "/api/sitios/dos.example/avanzado", None),
    ("put", "/api/sitios/dos.example/php", {"ajustes": {}}),
    ("put", "/api/sitios/dos.example/php/version", {"version": "8.2"}),
    ("get", "/api/sitios/dos.example/archivo?ruta=wp-config.php", None),
    ("post", "/api/sitios/dos.example/restaurar", {"version": "20261021-101010-123"}),
    ("post", "/api/sitios/dos.example/baja", {"motivo": "x"}),
    ("get", "/api/sitios/dns/dos.example", None),
    ("get", "/api/sitios/dns/blog.uno.example", None),  # la zona es el dominio exacto, no un subdominio
    ("post", "/api/sitios/dns/dos.example", {"registro": {"nombre": "@", "tipo": "A", "valor": "192.0.2.1"}}),
    ("delete", "/api/sitios/dns/dos.example/0123abcd", None),
    ("get", "/api/sitios/..%2Fdos.example/estado", None),
]


@pytest.mark.parametrize("metodo,ruta,cuerpo", AJENAS)
def test_lo_ajeno_da_404_sin_llamar_al_intermediario(entorno, metodo, ruta, cuerpo):
    cliente_http, simulado, _ = entorno
    r = getattr(cliente_http, metodo)(ruta, headers=CABECERA, **({"json": cuerpo} if cuerpo is not None else {}))
    assert r.status_code == 404
    assert simulado.peticiones == []


@pytest.mark.parametrize("ruta", ["/api/sitios/dos.example/paquete", "/api/sitios/dos.example/archivo?ruta=a.txt",
                                  "/api/sitios/dos.example/paquete/respaldo"])
def test_subir_a_lo_ajeno_da_404_y_no_escribe(entorno, ruta):
    cliente_http, simulado, subidas = entorno
    r = cliente_http.put(ruta, headers=CABECERA, content=b"PK\x03\x04" + b"0" * 100)
    assert r.status_code == 404 and simulado.peticiones == [] and os.listdir(subidas) == []


def test_subdominio_permitido_y_ficha_reenviada(entorno):
    cliente_http, simulado, _ = entorno
    r = cliente_http.post("/api/sitios", headers=CABECERA, json={"sitio": "Tienda.Uno.Example", "www": False})
    assert r.status_code == 201
    p = simulado.peticiones[-1]
    assert (p["orden"], p["dominio"], p["args"], p["ficha"]) == ("crear", "tienda.uno.example", {"www": False}, FICHA)


def test_el_dominio_propio_tambien(entorno):
    cliente_http, simulado, _ = entorno
    assert cliente_http.post("/api/sitios", headers=CABECERA, json={"sitio": "www.uno.example"}).status_code == 201
    assert simulado.peticiones[-1]["dominio"] == "uno.example"


@pytest.mark.parametrize("codigo,texto", [(409, "Ya tienes 2 sitios, el máximo de tu dominio"),
                                          (403, "Ese nombre está reservado para el correo"),
                                          (404, "No encontrado"), (413, "Supera el disco del dominio")])
def test_los_errores_del_intermediario_llegan_con_su_codigo(entorno, codigo, texto):
    cliente_http, simulado, _ = entorno
    simulado.respuestas["crear"] = {"ok": False, "codigo": codigo, "error": texto}
    r = cliente_http.post("/api/sitios", headers=CABECERA, json={"sitio": "blog.uno.example"})
    assert (r.status_code, r.json()["detail"]) == (codigo, texto)
    assert app.state.db.auditoria == []  # lo que no se hizo no se audita


def test_sin_socket_los_sitios_no_estan_instalados(entorno, monkeypatch):
    cliente_http, _, _ = entorno
    monkeypatch.setattr(config, "SOCKET", "/nada/no-existe.sock")
    r = cliente_http.get("/api/sitios", headers=CABECERA)
    assert (r.status_code, r.json()["detail"]) == (503, "Los sitios web no están instalados en este servidor")
    assert cliente_http.get("/api/sitios/resumen", headers=CABECERA).json() == {"instalado": False, "sitios": []}


def test_respuestas_raras_del_intermediario():
    with pytest.raises(HTTPException) as e:
        cliente.interpretar(b"no es json\n")
    assert e.value.status_code == 502
    with pytest.raises(HTTPException) as e:
        cliente.interpretar(b"")
    assert e.value.status_code == 503
    # Un 401 del intermediario no debe cerrar la sesión del portal; un 500 no se disfraza de error del portal.
    for codigo, esperado in ((401, 403), (500, 502), (200, 502), ("x", 400)):
        with pytest.raises(HTTPException) as e:
            cliente.interpretar(json.dumps({"ok": False, "codigo": codigo, "error": "x"}).encode())
        assert e.value.status_code == esperado
    assert cliente.interpretar(b'{"ok": true, "datos": [1]}') == [1]


def test_tiempos_largos_para_lo_que_instala():
    assert cliente.tiempo_de("app") >= 1000 and cliente.tiempo_de("paquete") >= 1000
    assert cliente.tiempo_de("actualizar") >= 600 and cliente.tiempo_de("listar") == 60
    with pytest.raises(ValueError):
        import asyncio
        asyncio.run(cliente.pedir(FICHA, "borrar", "uno.example"))


def test_lista_y_ficha(entorno):
    cliente_http, simulado, _ = entorno
    r = cliente_http.get("/api/sitios", headers=CABECERA).json()
    assert [s["dominio"] for s in r["sitios"]] == ["uno.example", "blog.uno.example"] and r["dns"] is True
    assert r["solicitudes"] == []
    e = cliente_http.get("/api/sitios/blog.uno.example/estado", headers=CABECERA).json()
    assert (e["dominio"], e["cuota"]["max_sitios"], e["baja_pendiente"]) == ("uno.example", 2, False)
    # En alcance pero no existe: 404 también.
    assert cliente_http.get("/api/sitios/otro.uno.example/estado", headers=CABECERA).status_code == 404


def test_baja_crea_solicitud_y_no_borra_nada(entorno):
    cliente_http, simulado, _ = entorno
    r = cliente_http.post("/api/sitios/blog.uno.example/baja", headers=CABECERA, json={"motivo": "ya no\r\nse usa"})
    assert r.status_code == 201 and r.json()["estado"] == "pendiente"
    assert simulado.ordenes() == ["listar"]  # solo comprobó que existe
    s = app.state.db.solicitudes
    assert [(x["tipo"], x["objetivo"], x["dominio"], x["motivo"]) for x in s] == [
        ("baja_sitio", "blog.uno.example", "uno.example", "ya no  se usa")]
    assert cliente_http.post("/api/sitios/blog.uno.example/baja", headers=CABECERA, json={}).status_code == 409
    assert cliente_http.get("/api/sitios/blog.uno.example/estado", headers=CABECERA).json()["baja_pendiente"] is True
    assert not any(re.search(r"\b(DELETE|UPDATE)\b", c) for c in app.state.db.consultas)


def test_baja_de_un_sitio_que_no_existe(entorno):
    cliente_http, _, _ = entorno
    assert cliente_http.post("/api/sitios/nada.uno.example/baja", headers=CABECERA, json={}).status_code == 404
    assert app.state.db.solicitudes == []


def _auditado() -> str:
    return json.dumps([list(map(str, fila)) for fila in app.state.db.auditoria])


def test_auditoria_sin_contrasenas(entorno):
    cliente_http, simulado, _ = entorno
    simulado.respuestas["app"] = {"ok": True, "datos": {"url_admin": "https://uno.example/wp-admin/",
                                                        "admin_usuario": "admin", "admin_clave": CLAVE}}
    simulado.respuestas["ftp"] = {"ok": True, "datos": {"usuario": "s_uno", "clave": CLAVE}}
    simulado.respuestas["clave-admin"] = {"ok": True, "datos": {"usuario": "admin", "clave": CLAVE}}
    simulado.respuestas["base-crear"] = {"ok": True, "datos": {"base": "x_uno_ab12", "clave": CLAVE}}
    r = cliente_http.post("/api/sitios/uno.example/app", headers=CABECERA,
                          json={"aplicacion": "wordpress", "titulo": "Mi sitio", "correo": "Ana@Uno.Example"})
    assert r.json()["admin_clave"] == CLAVE  # se muestra una vez…
    assert simulado.peticiones[-1]["args"] == {"aplicacion": "wordpress", "titulo": "Mi sitio", "correo": "ana@uno.example"}
    assert cliente_http.post("/api/sitios/uno.example/ftp", headers=CABECERA, json={"accion": "activar"}).json()["clave"] == CLAVE
    cliente_http.post("/api/sitios/uno.example/clave-admin", headers=CABECERA)
    cliente_http.post("/api/sitios/uno.example/bases", headers=CABECERA, json={"motor": "mariadb"})
    acciones = [f[2] for f in app.state.db.auditoria]
    assert acciones == ["sitio_app", "sitio_ftp_activar", "sitio_clave_admin", "sitio_base_crear"]
    assert CLAVE not in _auditado() and FICHA not in _auditado()  # …pero no se guarda


@pytest.mark.parametrize("cuerpo", [
    {"aplicacion": "wordpress", "titulo": "<script>", "correo": "a@uno.example"},
    {"aplicacion": "wordpress", "titulo": "Sitio", "correo": "no-es-correo"},
    {"aplicacion": "../x", "titulo": "Sitio", "correo": "a@uno.example"},
])
def test_app_valida_antes_de_llamar(entorno, cuerpo):
    cliente_http, simulado, _ = entorno
    assert cliente_http.post("/api/sitios/uno.example/app", headers=CABECERA, json=cuerpo).status_code == 400
    assert simulado.peticiones == []


def test_formas_invalidas_no_llegan_al_intermediario(entorno):
    cliente_http, simulado, _ = entorno
    h = CABECERA
    assert cliente_http.post("/api/sitios/uno.example/ftp", headers=h, json={"accion": "borrar"}).status_code == 400
    assert cliente_http.delete("/api/sitios/uno.example/bases/w_uno", headers=h).status_code == 400  # la principal no
    assert cliente_http.post("/api/sitios/uno.example/bases/x_uno_ab12/entrar", headers=h, json={"herramienta": "shell"}).status_code == 400
    assert cliente_http.put("/api/sitios/uno.example/php/version", headers=h, json={"version": "8.2; rm"}).status_code == 400
    assert cliente_http.get("/api/sitios/uno.example/archivo?ruta=../../etc/passwd", headers=h).status_code == 400
    assert cliente_http.put("/api/sitios/uno.example/tareas", headers=h, json={"trabajos": [{"horario": "* * * * *", "orden": "a\nb"}]}).status_code == 400
    assert cliente_http.post("/api/sitios/dns/uno.example", headers=h, json={"registro": {"tipo": "NS", "valor": "x"}}).status_code == 400
    assert simulado.peticiones == []


def test_tareas_bases_avanzado_y_dns(entorno):
    cliente_http, simulado, _ = entorno
    h = CABECERA
    cliente_http.put("/api/sitios/uno.example/tareas", headers=h,
                     json={"trabajos": [{"horario": "*/5 * * * *", "orden": "php publico/cron.php", "activo": True}]})
    assert simulado.peticiones[-1]["args"]["lista"][0]["orden"] == "php publico/cron.php"
    cliente_http.post("/api/sitios/uno.example/bases/w_uno/entrar", headers=h, json={"herramienta": "phpmyadmin"})
    assert simulado.peticiones[-1]["args"] == {"base": "w_uno", "herramienta": "phpmyadmin"}
    cliente_http.get("/api/sitios/uno.example/archivo?ruta=/wp-config.php", headers=h)
    assert simulado.peticiones[-1]["args"] == {"ruta": "wp-config.php"}
    simulado.respuestas["dns-modificar"] = {"ok": False, "codigo": 403, "error": "Ese registro es del correo: no se puede cambiar"}
    r = cliente_http.put("/api/sitios/dns/uno.example/0123abcd", headers=h,
                         json={"registro": {"nombre": "@", "tipo": "MX", "valor": "mail", "prioridad": 10}})
    assert (r.status_code, simulado.peticiones[-1]["dominio"]) == (403, "uno.example")
    cliente_http.post("/api/sitios/dns/uno.example", headers=h, json={"registro": {"nombre": "www", "tipo": "A", "valor": "192.0.2.10"}})
    assert simulado.peticiones[-1]["args"]["registro"] == {"nombre": "www", "tipo": "A", "valor": "192.0.2.10", "ttl": 3600, "prioridad": None}


ZIP = b"PK\x03\x04" + b"\x00" * 200


def test_paquete_se_guarda_y_llega_al_intermediario(entorno):
    cliente_http, simulado, subidas = entorno
    r = cliente_http.put("/api/sitios/blog.uno.example/paquete?con_bd=1&nombre=mi%20sitio.zip", headers=CABECERA, content=ZIP)
    assert r.status_code == 200
    p = simulado.peticiones[-1]
    assert p["orden"] == "paquete" and re.fullmatch(r"[0-9a-f]{32}\.zip", p["args"]["subida"])
    assert p["args"]["con_bd"] is True and "respaldo" not in p["args"]
    assert os.listdir(subidas) == []
    assert json.loads(app.state.db.auditoria[-1][4])["archivo"] == "mi sitio.zip"


def test_paquete_con_respaldo_es_una_migracion(entorno):
    cliente_http, simulado, subidas = entorno
    r = cliente_http.put("/api/sitios/blog.uno.example/paquete/respaldo", headers=CABECERA, content=b"CREATE TABLE t (a int);\n")
    respaldo = r.json()["respaldo"]
    assert re.fullmatch(r"[0-9a-f]{32}\.sql", respaldo) and simulado.peticiones == []
    assert os.listdir(subidas) == [respaldo]
    r = cliente_http.put(f"/api/sitios/blog.uno.example/paquete?respaldo={respaldo}", headers=CABECERA, content=b"\x1f\x8b" + b"0" * 50)
    p = simulado.peticiones[-1]
    assert r.status_code == 200 and p["args"]["respaldo"] == respaldo and p["args"]["con_bd"] is True
    assert p["args"]["subida"].endswith(".tar.gz") and os.listdir(subidas) == []
    assert app.state.db.auditoria[-1][2] == "sitio_migracion"


def test_paquete_con_respaldo_inventado(entorno):
    cliente_http, simulado, _ = entorno
    for falso in ("0" * 32 + ".sql", "../../etc/shadow", "a" * 32 + ".php"):
        r = cliente_http.put(f"/api/sitios/uno.example/paquete?respaldo={falso}", headers=CABECERA, content=ZIP)
        assert r.status_code == 400
    assert simulado.peticiones == []


def test_subida_por_encima_del_tope(entorno):
    cliente_http, simulado, subidas = entorno

    def trozos():  # sin Content-Length: el tope se comprueba mientras llega
        yield b"PK\x03\x04"
        for _ in range(100):
            yield b"0" * 1024

    r = cliente_http.put("/api/sitios/uno.example/paquete", headers=CABECERA, content=trozos())
    assert r.status_code == 413 and "64" in r.json()["detail"]
    assert simulado.peticiones == [] and os.listdir(subidas) == []
    r = cliente_http.put("/api/sitios/uno.example/paquete", headers=CABECERA, content=b"PK\x03\x04" + b"0" * (70 * 1024))
    assert r.status_code == 413 and os.listdir(subidas) == []


@pytest.mark.parametrize("contenido", [b"MZ\x90\x00" + b"0" * 50, b"", b"<?php echo 1;"])
def test_paquete_que_no_es_zip_ni_tar_gz(entorno, contenido):
    cliente_http, simulado, subidas = entorno
    assert cliente_http.put("/api/sitios/uno.example/paquete", headers=CABECERA, content=contenido).status_code == 400
    assert simulado.peticiones == [] and os.listdir(subidas) == []


def test_archivo_de_texto(entorno):
    cliente_http, simulado, subidas = entorno
    texto = "<?php\ndefine('WP_DEBUG', false); // ñandú\n".encode()
    r = cliente_http.put("/api/sitios/uno.example/archivo?ruta=wp-config.php", headers=CABECERA, content=texto)
    p = simulado.peticiones[-1]
    assert r.status_code == 200 and p["orden"] == "avanzado-archivo" and p["args"]["ruta"] == "wp-config.php"
    assert p["args"]["subida_contenido"].encode() == texto and p["args"]["subida"].endswith(".txt")
    assert os.listdir(subidas) == []
    assert cliente_http.put("/api/sitios/uno.example/archivo?ruta=a.txt", headers=CABECERA, content=b"x" * 5000).status_code == 413
    assert cliente_http.put("/api/sitios/uno.example/archivo?ruta=a.txt", headers=CABECERA, content=b"\xff\xfe\x00").status_code == 400
    assert os.listdir(subidas) == []


def test_si_el_intermediario_falla_no_queda_nada_subido(entorno):
    cliente_http, simulado, subidas = entorno
    simulado.respuestas["paquete"] = {"ok": False, "codigo": 409, "error": "Supera el disco de tu dominio"}
    # El simulado borra lo que recibe; para probar la limpieza del portal se le impide.
    simulado.responder = lambda p: simulado.respuestas["paquete"]
    r = cliente_http.put("/api/sitios/uno.example/paquete", headers=CABECERA, content=ZIP)
    assert (r.status_code, r.json()["detail"]) == (409, "Supera el disco de tu dominio")
    assert os.listdir(subidas) == []


def test_resumen_para_la_tarjeta(entorno):
    cliente_http, simulado, _ = entorno
    r = cliente_http.get("/api/sitios/resumen", headers=CABECERA).json()
    assert r["instalado"] is True
    assert r["sitios"][0] == {"sitio": "uno.example", "app": "wordpress", "app_pendiente": False, "https": True,
                              "version": "6.6.2", "actualizaciones": 1, "revisado": True}
    assert r["sitios"][1]["revisado"] is False  # sin aplicación no hay nada que revisar
    cliente_http.get("/api/sitios/resumen", headers=CABECERA)
    assert simulado.ordenes().count("revisar") == 1  # la revisión se guarda unos minutos
