"""maquita-sitios-portal, v1.10: funciones web, cuentas FTP adicionales, registros, estadísticas, disponibilidad,
copias y administrador de archivos desde el portal. Lista cerrada, traducción de cada orden, alcance, argumentos
raros, cuotas y entrega de descargas. Mismo mundo de dobles que test_sitios_portal.py."""

import json
import os
import sys
import tarfile

import pytest

from tests.test_sitios_portal import RAIZ, codigo, de_b64, mundo, pedir  # noqa: F401  (mundo es la fijación)

sys.path.insert(0, os.path.join(RAIZ, "deploy", "sitios", "portal", "lib"))  # ya lo hizo test_sitios_portal

import portal  # noqa: E402
import rutas  # noqa: E402

HEX = "0123456789abcdef0123456789abcdef"
SUBIDA = HEX + ".subida"

NUEVAS = {
    "web", "web-redirecciones", "web-errores", "web-hotlink", "web-bloqueo", "web-optimizacion", "web-purgar",
    "web-privado-agregar", "web-privado-quitar", "ftp-cuentas", "ftp-cuenta-crear", "ftp-cuenta-clave",
    "ftp-cuenta-quitar", "registros", "estadisticas", "estadisticas-generar", "estadisticas-informe",
    "disponibilidad", "copias", "copia-crear", "copia-descargar", "copia-restaurar", "copia-borrar",
    "archivos-listar", "archivos-subir", "archivos-descargar", "archivos-carpeta", "archivos-mover",
    "archivos-copiar", "archivos-descomprimir", "archivos-borrar", "archivos-comprimir", "archivos-permisos",
    "archivos-papelera", "archivos-recuperar", "archivos-vaciar",
}


@pytest.fixture
def sitio(mundo, tmp_path, monkeypatch):  # noqa: F811
    (tmp_path / "copias").mkdir()
    monkeypatch.setattr(rutas, "COPIAS", str(tmp_path / "copias"))
    mundo.sitio("example.org", publico=str(tmp_path / "srv" / "example.org" / "publico"))
    (tmp_path / "srv" / "example.org" / "publico").mkdir(parents=True)
    return mundo


# --- Lista cerrada ---


def test_la_lista_tiene_exactamente_las_nuevas():
    v19 = {"listar", "catalogo", "crear", "app", "entrar", "clave-admin", "revisar", "actualizar", "terminar", "ssl",
           "ftp", "tareas", "tareas-guardar", "tarea-ejecutar", "tarea-registro", "bases", "base-crear", "base-entrar",
           "base-borrar", "avanzado", "avanzado-php", "avanzado-ver", "avanzado-archivo", "avanzado-restaurar",
           "php-estado", "php-version", "paquete", "dns-ver", "dns-agregar", "dns-modificar", "dns-borrar"}
    import v111  # las de la v1.11 llegan juntas por su módulo (test_sitios_portal_v111.py)

    assert set(portal.ORDENES) == v19 | NUEVAS | set(v111.ORDENES)
    assert all(tipo == "sitio" for o, (tipo, _f) in portal.ORDENES.items() if o in NUEVAS)


@pytest.mark.parametrize("orden", ["disponibilidad-comprobar", "datos-noche", "ftp-montar", "avanzado-nginx",
                                   "php-instalar", "php-extension", "regenerar",
                                   "web-nginx", "archivos-", "copia", "copias-todas"])
def test_lo_del_sistema_y_del_superadministrador_no_esta(sitio, orden):
    assert codigo(orden, "example.org") == 400
    assert sitio.ayudante.llamadas == []


@pytest.mark.parametrize("orden", sorted(NUEVAS))
def test_alcance_de_las_nuevas(sitio, orden):
    sitio.sitio("example.com")
    assert codigo(orden, "example.com") == 404
    assert codigo(orden, "nada.example.org") == 404  # en su alcance, pero no existe
    sitio.sitio("mail.example.org")
    assert codigo(orden, "mail.example.org") == 403
    assert sitio.ayudante.llamadas == []


# --- Traducción ---

TRADUCCIONES = [
    ("web", {}, ["web", "example.org"]),
    ("web-purgar", {}, ["web-purgar", "example.org"]),
    ("web-privado-agregar", {"carpeta": "/privado", "usuario": "ana"}, ["web-privado-agregar", "example.org", "L3ByaXZhZG8", "ana"]),
    ("web-privado-agregar", {"carpeta": "/privado", "usuario": "ana", "clave": "clave-larga-1"},
     ["web-privado-agregar", "example.org", "L3ByaXZhZG8", "ana", "Y2xhdmUtbGFyZ2EtMQ"]),
    ("web-privado-quitar", {"carpeta": "/privado"}, ["web-privado-quitar", "example.org", "L3ByaXZhZG8"]),
    ("web-privado-quitar", {"carpeta": "/privado", "usuario": "ana"}, ["web-privado-quitar", "example.org", "L3ByaXZhZG8", "ana"]),
    ("ftp-cuentas", {}, ["ftp-cuentas", "example.org"]),
    ("ftp-cuenta-crear", {"nombre": "disenador", "carpeta": "/imagenes/"}, ["ftp-cuenta-crear", "example.org", "disenador", "aW1hZ2VuZXM"]),
    ("ftp-cuenta-clave", {"nombre": "disenador"}, ["ftp-cuenta-clave", "example.org", "disenador"]),
    ("ftp-cuenta-quitar", {"nombre": "disenador"}, ["ftp-cuenta-quitar", "example.org", "disenador"]),
    ("registros", {"tipo": "error", "lineas": 50}, ["registros", "example.org", "error", "50"]),
    ("registros", {"tipo": "acceso", "lineas": 1000, "filtro": "wp-login"}, ["registros", "example.org", "acceso", "1000", "d3AtbG9naW4"]),
    ("estadisticas", {}, ["estadisticas", "example.org"]),
    ("estadisticas-generar", {}, ["estadisticas-generar", "example.org"]),
    ("disponibilidad", {}, ["disponibilidad", "example.org"]),
    ("copia-borrar", {"id": "20261021-101010"}, ["copia-borrar", "example.org", "20261021-101010"]),
    ("archivos-listar", {}, ["archivos-listar", "example.org", "Lg"]),
    ("archivos-listar", {"ruta": "/wp-content"}, ["archivos-listar", "example.org", "d3AtY29udGVudA"]),
    ("archivos-carpeta", {"ruta": "nueva"}, ["archivos-carpeta", "example.org", "bnVldmE"]),
    ("archivos-borrar", {"ruta": "viejo.txt"}, ["archivos-borrar", "example.org", "dmllam8udHh0"]),
    ("archivos-mover", {"origen": "a.txt", "destino": "b.txt"}, ["archivos-mover", "example.org", "YS50eHQ", "Yi50eHQ"]),
    ("archivos-copiar", {"origen": "a.txt", "destino": "b.txt"}, ["archivos-copiar", "example.org", "YS50eHQ", "Yi50eHQ"]),
    ("archivos-descomprimir", {"origen": "a.zip", "destino": "."}, ["archivos-descomprimir", "example.org", "YS56aXA", "Lg"]),
    ("archivos-permisos", {"ruta": "a.txt", "modo": "640"}, ["archivos-permisos", "example.org", "YS50eHQ", "640"]),
    ("archivos-papelera", {}, ["archivos-papelera", "example.org"]),
    ("archivos-recuperar", {"id": "0123456789ab"}, ["archivos-recuperar", "example.org", "0123456789ab"]),
    ("archivos-vaciar", {}, ["archivos-vaciar", "example.org"]),
]


@pytest.mark.parametrize("orden,args,esperado", TRADUCCIONES)
def test_traduccion(sitio, orden, args, esperado):
    pedir(orden, "example.org", **args)
    assert sitio.ayudante.ultima == ["maquita-sitios"] + esperado


def test_funciones_con_json(sitio):
    redireccion = {"origen": "/viejo", "destino": "https://example.com/", "codigo": 302, "subrutas": True}
    pedir("web-redirecciones", "example.org", redirecciones=[redireccion])
    assert json.loads(de_b64(sitio.ayudante.ultima[3])) == [{**redireccion, "conservar_ruta": True}]
    pedir("web-errores", "example.org", paginas={"404": "/errores/404.html"})
    assert json.loads(de_b64(sitio.ayudante.ultima[3])) == {"404": "/errores/404.html"}
    pedir("web-hotlink", "example.org", hotlink={"activo": True, "permitidos": ["example.com"]})
    assert json.loads(de_b64(sitio.ayudante.ultima[3])) == {"activo": True, "permitidos": ["example.com"], "buscadores": True}
    pedir("web-bloqueo", "example.org", redes=["203.0.113.7", "2001:db8::/32"])
    assert json.loads(de_b64(sitio.ayudante.ultima[3])) == ["203.0.113.7", "2001:db8::/32"]
    pedir("web-optimizacion", "example.org", optimizacion={"cache_pagina": True, "cache_minutos": 30})
    assert json.loads(de_b64(sitio.ayudante.ultima[3])) == {"compresion": True, "estaticos": "30d", "cache_pagina": True,
                                                             "cache_minutos": 30}
    pedir("web-bloqueo", "example.org", redes=[])  # vaciar la lista también vale
    assert de_b64(sitio.ayudante.ultima[3]) == "[]"


# --- Argumentos raros ---

RAROS = [
    ("web-redirecciones", {"redirecciones": "no es lista"}),
    ("web-redirecciones", {"redirecciones": [{"origen": "/a", "destino": "/b", "codigo": 307}]}),
    ("web-redirecciones", {"redirecciones": [{"origen": "/a", "destino": "/b", "nginx": "return 200;"}]}),
    ("web-redirecciones", {"redirecciones": [{"origen": "/a\n", "destino": "/b"}]}),
    ("web-redirecciones", {"redirecciones": [{"origen": "/a", "destino": "/b"}] * 201}),
    ("web-errores", {"paginas": {"200": "/x.html"}}),
    ("web-errores", {"paginas": {"404": 7}}),
    ("web-hotlink", {"hotlink": {"activo": "sí"}}),
    ("web-hotlink", {"hotlink": {"activo": True, "regla": "x"}}),
    ("web-bloqueo", {"redes": ["0.0.0.0/0"]}),
    ("web-bloqueo", {"redes": ["::/0"]}),
    ("web-bloqueo", {"redes": ["no-es-ip"]}),
    ("web-bloqueo", {"redes": ["192.0.2.1"] * 501}),
    ("web-optimizacion", {"optimizacion": {"cache_minutos": 0}}),
    ("web-optimizacion", {"optimizacion": {"cache_minutos": True}}),
    ("web-optimizacion", {"optimizacion": {"estaticos": "2y"}}),
    ("web-privado-agregar", {"carpeta": "/p", "usuario": "ana; rm"}),
    ("web-privado-agregar", {"carpeta": "/p", "usuario": "ana", "clave": "corta"}),
    ("web-privado-agregar", {"carpeta": "", "usuario": "ana"}),
    ("web-privado-agregar", {"carpeta": "x" * 200, "usuario": "ana"}),
    ("web-privado-quitar", {"carpeta": "/p", "usuario": "../ana"}),
    ("ftp-cuenta-crear", {"nombre": "Ana", "carpeta": "x"}),
    ("ftp-cuenta-crear", {"nombre": "a", "carpeta": "x"}),
    ("ftp-cuenta-crear", {"nombre": "ana", "carpeta": None}),
    ("ftp-cuenta-clave", {"nombre": "ana\n"}),
    ("ftp-cuenta-quitar", {"nombre": "root"[:1]}),
    ("registros", {"tipo": "sistema", "lineas": 10}),
    ("registros", {"tipo": "error", "lineas": 1001}),
    ("registros", {"tipo": "error", "lineas": "10"}),
    ("registros", {"tipo": "error", "lineas": True}),
    ("registros", {"tipo": "error", "lineas": 10, "filtro": "a\nb"}),
    ("registros", {"tipo": "error", "lineas": 10, "filtro": "x" * 101}),
    ("copia-borrar", {"id": "../20261021-101010"}),
    ("copia-restaurar", {"id": "20261021-101010\n"}),
    ("copia-descargar", {"id": 20261021}),
    ("archivos-listar", {"ruta": "../../etc"}),
    ("archivos-listar", {"ruta": "a/../../b"}),
    ("archivos-listar", {"ruta": "a\\..\\b"}),
    ("archivos-listar", {"ruta": "a\x00b"}),
    ("archivos-borrar", {"ruta": "."}),
    ("archivos-borrar", {"ruta": "/"}),
    ("archivos-descargar", {"ruta": "x" * 1001}),
    ("archivos-mover", {"origen": "a", "destino": "../a"}),
    ("archivos-permisos", {"ruta": "a.txt", "modo": "777"}),
    ("archivos-permisos", {"ruta": "a.txt", "modo": 644}),
    ("archivos-recuperar", {"id": "0123456789ab0"}),
    ("archivos-comprimir", {"rutas": [], "destino": "x.zip"}),
    ("archivos-comprimir", {"rutas": ["../x"], "destino": "x.zip"}),
    ("archivos-comprimir", {"rutas": ["a"], "destino": None}),
    ("archivos-subir", {"ruta": "a.txt", "subida": "../" + SUBIDA}),
    ("archivos-subir", {"ruta": "a.txt", "subida": HEX + ".zip"}),
    ("archivos-subir", {"ruta": ".", "subida": SUBIDA}),
    ("archivos-subir", {"ruta": "a.txt", "subida": SUBIDA, "reemplazar": "sí"}),
]


@pytest.mark.parametrize("orden,args", RAROS)
def test_argumentos_raros(sitio, orden, args):
    (sitio.tmp / "subidas-portal" / SUBIDA).write_bytes(b"hola")
    assert codigo(orden, "example.org", **args) == 400
    assert sitio.ayudante.llamadas == []
    assert os.listdir(sitio.tmp / "subidas") == []


def test_no_se_ensenan_los_correos_del_servidor(sitio):
    sitio.ayudante.respuestas[("maquita-sitios", "disponibilidad")] = {"historial": [], "destinatarios": ["jefe@example.com"]}
    assert pedir("disponibilidad", "example.org")["datos"]["destinatarios"] == ["(los avisos generales del servidor)"]
    sitio.ayudante.respuestas[("maquita-sitios", "disponibilidad")] = {"destinatarios": ["web@example.org", "x@example.com"]}
    assert pedir("disponibilidad", "example.org")["datos"]["destinatarios"] == ["web@example.org"]


# --- Subidas al administrador de archivos ---


def test_subir_archivo_se_copia_y_respeta_la_cuota(sitio):
    origen = sitio.tmp / "subidas-portal" / SUBIDA
    origen.write_bytes(b"x" * 2 * 1024 * 1024)
    sitio.base.cuotas = {"example.org": {"max_sitios": 1, "disco_mb": 1, "bases_mb": 1024}}
    assert codigo("archivos-subir", "example.org", ruta="grande.bin", subida=SUBIDA) == 409
    assert not origen.exists() and sitio.ayudante.llamadas == []  # rechazada: no se deja
    origen.write_bytes(b"hola")
    sitio.base.cuotas["example.org"]["disco_mb"] = 100
    pedir("archivos-subir", "example.org", ruta="/docs/hola.txt", subida=SUBIDA, reemplazar=True)
    _p, orden, s, ruta, tomado, reemplazar = sitio.ayudante.ultima
    assert (orden, s, de_b64(ruta), reemplazar) == ("archivos-subir", "example.org", "docs/hola.txt", "reemplazar")
    assert tomado != SUBIDA and tomado.endswith(".subida")
    assert (sitio.tmp / "subidas" / tomado).read_bytes() == b"hola" and not origen.exists()


def test_subir_enlace_simbolico_rechazado(sitio):
    secreto = sitio.tmp / "secreto"
    secreto.write_text("clave")
    os.symlink(secreto, sitio.tmp / "subidas-portal" / SUBIDA)
    assert codigo("archivos-subir", "example.org", ruta="a.txt", subida=SUBIDA) == 400
    assert os.listdir(sitio.tmp / "subidas") == [] and sitio.ayudante.llamadas == []


def test_copiar_y_comprimir_sin_espacio(sitio):
    (sitio.tmp / "srv" / "example.org" / "publico" / "g.bin").write_bytes(b"x" * 2 * 1024 * 1024)
    sitio.base.cuotas = {"example.org": {"max_sitios": 1, "disco_mb": 1, "bases_mb": 1024}}
    assert codigo("archivos-copiar", "example.org", origen="g.bin", destino="h.bin") == 409
    assert codigo("archivos-descomprimir", "example.org", origen="a.zip", destino=".") == 409
    assert codigo("archivos-comprimir", "example.org", rutas=["g.bin"], destino="g.zip") == 409
    pedir("archivos-mover", "example.org", origen="g.bin", destino="h.bin")  # mover no crece
    pedir("archivos-borrar", "example.org", ruta="h.bin")  # y borrar libera
    assert [ll[1] for ll in sitio.ayudante.llamadas] == ["archivos-mover", "archivos-borrar"]


# --- Copias y su cuota ---


def _copia(tmp, ident, contenido):
    carpeta = tmp / "copias" / "example.org"
    carpeta.mkdir(exist_ok=True)
    fuente = tmp / f"fuente-{ident}"
    (fuente / "publico").mkdir(parents=True)
    (fuente / "publico" / "index.html").write_bytes(contenido)
    with tarfile.open(carpeta / f"{ident}.tar.gz", "w:gz") as tar:
        tar.add(fuente / "publico", arcname="publico")
    return carpeta / f"{ident}.tar.gz"


def test_las_copias_cuentan_en_el_disco(sitio):
    sitio.base.cuotas = {"example.org": {"max_sitios": 1, "disco_mb": 1, "bases_mb": 1024}}
    (sitio.tmp / "srv" / "example.org" / "publico" / "index.html").write_bytes(b"x" * 600 * 1024)
    assert codigo("copia-crear", "example.org") == 409  # sin copias: se estima por lo alto (600 KB + lo que hay)
    sitio.base.cuotas["example.org"]["disco_mb"] = 10
    pedir("copia-crear", "example.org")
    assert sitio.ayudante.ultima[1:] == ["copia-crear", "example.org"]
    _copia(sitio.tmp, "20261021-101010", os.urandom(3 * 1024 * 1024))  # no se comprime: ~3 MB
    datos = pedir("copias", "example.org")["datos"]
    assert datos["espacio"]["disco_mb"] == 10 and datos["espacio"]["ocupado_mb"] >= 3
    sitio.base.cuotas["example.org"]["disco_mb"] = 4
    assert codigo("copia-crear", "example.org") == 409  # 0,6 + 3 de la copia + 3 de la siguiente > 4


def test_restaurar_comprueba_lo_que_trae(sitio):
    sitio.base.cuotas = {"example.org": {"max_sitios": 1, "disco_mb": 7, "bases_mb": 1024}}
    _copia(sitio.tmp, "20261021-101010", b"pequena")
    _copia(sitio.tmp, "20261021-111111", os.urandom(3 * 1024 * 1024))
    pedir("copia-restaurar", "example.org", id="20261021-101010")
    assert sitio.ayudante.ultima[1:] == ["copia-restaurar", "example.org", "20261021-101010"]
    assert codigo("copia-restaurar", "example.org", id="20261021-111111") == 409
    assert codigo("copia-restaurar", "example.org", id="20261021-121212") == 404


# --- Entrega de descargas ---


def _descarga_preparada(sitio, orden, contenido, **extra):
    def responder(args):
        (sitio.tmp / "subidas" / (HEX + ".descarga")).write_bytes(contenido)
        return {"dominio": "example.org", "archivo": HEX + ".descarga", **extra}

    sitio.ayudante.respuestas[("maquita-sitios", orden)] = responder


@pytest.mark.parametrize("orden,args,nombre", [
    ("archivos-descargar", {"ruta": "wp-config.php"}, "wp-config.php"),
    ("copia-descargar", {"id": "20261021-101010"}, "example.org-20261021-101010.tar.gz"),
    ("estadisticas-informe", {}, "estadisticas-example.org.html"),
])
def test_descarga_pasa_a_la_carpeta_del_portal(sitio, orden, args, nombre):
    _descarga_preparada(sitio, orden, b"contenido", nombre="wp-config.php")
    datos = pedir(orden, "example.org", **args)["datos"]
    assert "archivo" not in datos and datos["nombre"] == nombre and datos["bytes"] == 9
    assert datos["descarga"] != HEX + ".descarga" and datos["descarga"].endswith(".descarga")
    entregada = sitio.tmp / "subidas-portal" / datos["descarga"]
    assert entregada.read_bytes() == b"contenido"
    info = entregada.stat()
    assert oct(info.st_mode & 0o777) == "0o600" and info.st_uid == os.getuid()
    assert os.listdir(sitio.tmp / "subidas") == []


def test_descarga_con_nombre_raro_del_ayudante(sitio):
    sitio.ayudante.respuestas[("maquita-sitios", "archivos-descargar")] = {"archivo": "../../etc/shadow"}
    assert codigo("archivos-descargar", "example.org", ruta="a") == 503
    assert os.listdir(sitio.tmp / "subidas-portal") == []


def test_descarga_que_es_un_enlace(sitio):
    secreto = sitio.tmp / "secreto"
    secreto.write_text("clave")

    def responder(args):
        os.symlink(secreto, sitio.tmp / "subidas" / (HEX + ".descarga"))
        return {"archivo": HEX + ".descarga"}

    sitio.ayudante.respuestas[("maquita-sitios", "archivos-descargar")] = responder
    assert codigo("archivos-descargar", "example.org", ruta="a") == 503
    assert os.listdir(sitio.tmp / "subidas-portal") == [] and os.listdir(sitio.tmp / "subidas") == []
    assert secreto.read_text() == "clave"
