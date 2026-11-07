"""maquita-sitios-portal: el intermediario no se fía del portal (alcance, reservados, lista de órdenes,
cuotas, DNS protegido y subidas). Sin root ni base real: psql, rutas y ayudantes son dobles."""

import base64
import json
import os
import pwd
import socket
import sys

import pytest

RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(RAIZ, "deploy", "sitios", "portal", "lib"))

import alcance  # noqa: E402
import ayudantes  # noqa: E402
import bd  # noqa: E402
import conexion  # noqa: E402
import cuotas  # noqa: E402
import dns_protegido  # noqa: E402
import portal  # noqa: E402
import rutas  # noqa: E402
import sesion  # noqa: E402
from errores import ErrorPortal  # noqa: E402

FICHA = "f" * 43
MX = {"id": "0000000a", "nombre": "@", "tipo": "MX", "valor": "mail.example.org.", "ttl": 3600, "prioridad": 10}
WWW = {"id": "0000000b", "nombre": "www", "tipo": "A", "valor": "192.0.2.10", "ttl": 3600, "prioridad": None}
SPF = {"id": "0000000c", "nombre": "@", "tipo": "TXT", "valor": "v=spf1 mx -all", "ttl": 3600, "prioridad": None}


class Base:
    """Doble de la base del portal: sesión, cuotas, portales y dominios del servidor."""

    def __init__(self):
        self.admin = {"id": 7, "usuario": "ana", "activa": True, "cambiar_clave": False, "totp": True,
                      "dominios": ["example.org"]}
        self.cuotas = {}
        self.portales = ["portal.example.org"]
        self.dominios = ["example.org", "example.com"]

    def __call__(self, sql, variables=None, tabla=None):
        if sql == sesion.SQL_SESION:
            return self.admin
        if sql == sesion.SQL_SOPORTE:  # sin sesión de administrador se mira si es de soporte
            return None
        if sql == sesion.SQL_CUOTAS:
            pedidos = json.loads(variables["dominios"])
            return {d: c for d, c in self.cuotas.items() if d in pedidos}
        if sql == sesion.SQL_PORTALES:
            return self.portales
        if sql == sesion.SQL_DOMINIOS:
            return self.dominios
        raise AssertionError(f"consulta inesperada: {sql}")


class Ayudante:
    """Doble de maquita-sitios / maquita-dns: guarda cada llamada (ya validada) y responde lo previsto."""

    def __init__(self):
        self.llamadas = []
        self.respuestas = {}

    def __call__(self, orden, tiempo):
        programa, args = os.path.basename(orden[0]), orden[1:]
        self.llamadas.append([programa] + args)
        datos = self.respuestas.get((programa, args[0]), {"hecho": True})

        class R:
            returncode = 0
            stdout = json.dumps(datos(args) if callable(datos) else datos)
            stderr = ""

        return R()

    @property
    def ultima(self):
        return self.llamadas[-1]


@pytest.fixture
def mundo(tmp_path, monkeypatch):
    for nombre in ("meta", "srv", "nginx", "subidas-portal", "subidas", "bin"):
        (tmp_path / nombre).mkdir()
    (tmp_path / "correo.env").write_text("MAIL_HOST=servidor.example.org\n")
    for binario in ("maquita-sitios", "maquita-dns"):
        (tmp_path / "bin" / binario).write_text("#!/bin/sh\n")
    (tmp_path / "nginx" / "panel").write_text("server {\n    server_name panel.example.org;  # el panel\n}\n")
    (tmp_path / "nginx" / "sitio-example.org.conf").write_text("server { server_name example.org www.example.org; }\n")
    valores = {
        "META_SITIOS": "meta", "RAIZ_SITIOS": "srv", "NGINX_ACTIVOS": "nginx", "SUBIDAS_PORTAL": "subidas-portal",
        "SUBIDAS": "subidas", "ENTORNO_CORREO": "correo.env", "MAQUITA_SITIOS": "bin/maquita-sitios",
        "MAQUITA_DNS": "bin/maquita-dns", "MARIADB": "no-existe", "PSQL": "no-existe",
    }
    for clave, relativa in valores.items():
        monkeypatch.setattr(rutas, clave, str(tmp_path / relativa))
    monkeypatch.setattr(rutas, "MAQUITA_SUDO", os.path.join(RAIZ, "deploy", "sudoers", "maquita-sudo"))
    monkeypatch.setattr(rutas, "USUARIO_PORTAL", pwd.getpwuid(os.getuid()).pw_name)
    base, ayudante = Base(), Ayudante()
    monkeypatch.setattr(bd, "consultar", base)
    monkeypatch.setattr(bd, "entorno_portal", lambda ruta=None: {"PD_TOTP_OBLIGATORIO": "1"})
    monkeypatch.setattr(ayudantes, "_correr", ayudante)

    class Mundo:
        pass

    m = Mundo()
    m.tmp, m.base, m.ayudante = tmp_path, base, ayudante
    m.sitio = lambda nombre, **meta: (tmp_path / "meta" / f"{nombre}.json").write_text(
        json.dumps({"dominio": nombre, **meta}))
    return m


def pedir(orden, dominio=None, **args):
    return portal.atender({"ficha": FICHA, "orden": orden, "dominio": dominio, "args": args})


def codigo(orden, dominio=None, **args):
    with pytest.raises(ErrorPortal) as e:
        pedir(orden, dominio, **args)
    return e.value.codigo


def de_b64(texto):
    return base64.urlsafe_b64decode(texto + "=" * (-len(texto) % 4)).decode()


# --- Sesión ---


def test_sesion_se_comprueba_en_la_base(mundo):
    mundo.sitio("example.org")
    assert pedir("revisar", "example.org")["ok"]
    mundo.base.admin = None
    assert codigo("revisar", "example.org") == 403
    mundo.base.admin = {**Base().admin, "cambiar_clave": True}
    assert codigo("revisar", "example.org") == 403
    mundo.base.admin = {**Base().admin, "totp": False}
    assert codigo("revisar", "example.org") == 403
    mundo.base.admin = {**Base().admin, "activa": False}
    assert codigo("revisar", "example.org") == 403
    with pytest.raises(ErrorPortal) as e:
        portal.atender({"orden": "listar"})
    assert e.value.codigo == 403


# --- Alcance ---


@pytest.mark.parametrize("ajeno", ["example.com", "blog.example.com", "otroexample.org", "example.org.example.com",
                                   "no es un dominio", None, 42])
def test_otro_dominio_no_encontrado(mundo, ajeno):
    mundo.sitio("example.com")
    mundo.sitio("blog.example.com")
    assert codigo("revisar", ajeno) == 404
    assert codigo("crear", ajeno, www=True) == 404
    assert mundo.ayudante.llamadas == []


def test_subdominio_si(mundo):
    mundo.sitio("blog.example.org")
    pedir("revisar", "blog.example.org")
    assert mundo.ayudante.ultima == ["maquita-sitios", "revisar", "blog.example.org"]
    pedir("revisar", "www.blog.example.org")  # «www.» se quita
    assert mundo.ayudante.ultima == ["maquita-sitios", "revisar", "blog.example.org"]


def test_sitio_inexistente_no_encontrado(mundo):
    assert codigo("revisar", "nada.example.org") == 404


@pytest.mark.parametrize("reservado", [
    "mail.example.org", "imap.example.org", "smtp.example.org", "pop3.example.org", "autoconfig.example.org",
    "autodiscover.example.org", "mta-sts.example.org", "webmail.example.org", "correo.example.org",
    "_dmarc.example.org", "servidor.example.org", "portal.example.org", "panel.example.org",
])
def test_nombres_reservados(mundo, reservado):
    mundo.sitio(reservado)
    assert codigo("crear", reservado, www=False) == 403
    assert codigo("revisar", reservado) == 403
    assert mundo.ayudante.llamadas == []


def test_alias_de_otro_sitio_reservado(mundo):
    mundo.sitio("example.com", alias=["tienda.example.org"])
    assert codigo("crear", "tienda.example.org") == 403


# --- Lista de órdenes ---


# «alias» y las aplicaciones propias («propia-…») sí están desde la v1.11 (test_sitios_portal_v111.py).
@pytest.mark.parametrize("orden", ["borrar", "inicio", "buscadores", "avisar", "tienda",
                                   "avanzado-nginx", "php-instalar", "php-repositorio",
                                   "php-extension", "cron", "regenerar", "estado", "crear-zona", "", None])
def test_ordenes_fuera_de_la_lista(mundo, orden):
    mundo.sitio("example.org")
    assert codigo(orden, "example.org") == 400
    assert mundo.ayudante.llamadas == []


@pytest.mark.parametrize("ruta", ["../etc/passwd", "/etc/passwd", "a/../../b", "", "a\nb"])
def test_ver_archivo_rutas_raras(mundo, ruta):
    mundo.sitio("example.org")
    assert codigo("avanzado-ver", "example.org", ruta=ruta) == 400
    assert mundo.ayudante.llamadas == []


# --- Traducción de cada orden ---

TRADUCCIONES = [
    ("catalogo", None, {}, ["catalogo"]),
    ("avanzado-ver", "example.org", {"ruta": "wp-config.php"}, ["avanzado-ver", "example.org", "d3AtY29uZmlnLnBocA"]),
    ("app", "example.org", {"aplicacion": "wordpress", "titulo": "Mi sitio", "correo": "Ana@Example.org"},
     ["app", "example.org", "wordpress", "TWkgc2l0aW8", "ana@example.org"]),
    ("entrar", "example.org", {}, ["entrar", "example.org"]),
    ("clave-admin", "example.org", {}, ["clave-admin", "example.org"]),
    ("revisar", "example.org", {}, ["revisar", "example.org"]),
    ("actualizar", "example.org", {}, ["actualizar", "example.org"]),
    ("terminar", "example.org", {}, ["terminar", "example.org"]),
    ("ssl", "example.org", {"correo": "ana@example.org"}, ["ssl", "example.org", "ana@example.org"]),
    ("ftp", "example.org", {"accion": "activar"}, ["ftp", "example.org", "activar"]),
    ("ftp", "example.org", {"accion": "desactivar"}, ["ftp", "example.org", "desactivar"]),
    ("tareas", "example.org", {}, ["tareas", "example.org"]),
    ("tarea-ejecutar", "example.org", {"id": "0123abcd"}, ["tarea-ejecutar", "example.org", "0123abcd"]),
    ("tarea-registro", "example.org", {"id": "0123abcd"}, ["tarea-registro", "example.org", "0123abcd"]),
    ("bases", "example.org", {}, ["bases", "example.org"]),
    ("base-crear", "example.org", {"motor": "postgresql"}, ["base-crear", "example.org", "postgresql"]),
    ("base-entrar", "example.org", {"base": "x_example1234_00ff", "herramienta": "adminer"},
     ["base-entrar", "example.org", "x_example1234_00ff", "adminer"]),
    ("base-borrar", "example.org", {"base": "x_example1234_00ff"}, ["base-borrar", "example.org", "x_example1234_00ff"]),
    ("avanzado", "example.org", {}, ["avanzado", "example.org"]),
    ("php-estado", "example.org", {}, ["php-estado", "example.org"]),
]


@pytest.mark.parametrize("orden,dominio,args,esperado", TRADUCCIONES)
def test_traduccion(mundo, orden, dominio, args, esperado):
    mundo.sitio("example.org")
    pedir(orden, dominio, **args)
    assert mundo.ayudante.ultima == ["maquita-sitios"] + esperado


def test_crear(mundo):
    pedir("crear", "example.org", www=False)
    assert mundo.ayudante.ultima == ["maquita-sitios", "crear", "example.org", "sin-www"]


def test_tareas_guardar_en_base64(mundo):
    mundo.sitio("example.org")
    lista = [{"horario": "0 3 * * *", "orden": "php artisan schedule:run", "descripcion": "Diario"}]
    pedir("tareas-guardar", "example.org", lista=lista)
    programa, orden, sitio, datos = mundo.ayudante.ultima
    assert (orden, sitio) == ("tareas-guardar", "example.org")
    assert json.loads(de_b64(datos)) == lista


def test_avanzado_php_y_restaurar_php_y_archivos(mundo):
    mundo.sitio("example.org")
    versiones = [{"id": "20261021-101010-001", "tipo": "php"}, {"id": "20261021-101010-002", "tipo": "nginx"},
                 {"id": "20261021-101010-003", "tipo": "archivo"}]
    mundo.ayudante.respuestas[("maquita-sitios", "avanzado")] = {
        "vhost": "server {}", "nginx_propias": "location /x {}", "archivos": ["wp-config.php"], "versiones": versiones}
    datos = pedir("avanzado", "example.org")["datos"]
    assert "nginx_propias" not in datos and datos["archivos"] == ["wp-config.php"]
    assert [v["id"] for v in datos["versiones"]] == ["20261021-101010-001", "20261021-101010-003"]
    pedir("avanzado-php", "example.org", ajustes={"memory_limit": "256"})
    assert json.loads(de_b64(mundo.ayudante.ultima[3])) == {"memory_limit": "256"}
    pedir("avanzado-restaurar", "example.org", version="20261021-101010-001")
    assert mundo.ayudante.ultima[1:] == ["avanzado-restaurar", "example.org", "20261021-101010-001"]
    assert codigo("avanzado-restaurar", "example.org", version="20261021-101010-002") == 403
    pedir("avanzado-restaurar", "example.org", version="20261021-101010-003")
    assert mundo.ayudante.ultima[1:] == ["avanzado-restaurar", "example.org", "20261021-101010-003"]


def test_php_solo_versiones_instaladas(mundo):
    mundo.sitio("example.org")
    mundo.ayudante.respuestas[("maquita-sitios", "php-estado")] = {
        "instaladas": ["8.4"], "disponibles": ["8.2", "8.4"], "repositorio": False, "en_uso": {"8.4": ["x"]},
        "notas": {"8.2": "sin soporte"}, "sitio": "8.4"}
    assert pedir("php-estado", "example.org")["datos"] == {"instaladas": ["8.4"], "sitio": "8.4", "notas": {}}
    assert codigo("php-version", "example.org", version="8.2") == 403
    pedir("php-version", "example.org", version="8.4")
    assert mundo.ayudante.ultima[1:] == ["php-version", "example.org", "8.4"]


def test_correo_de_otro_dominio_del_servidor(mundo):
    mundo.sitio("example.org")
    assert codigo("ssl", "example.org", correo="ana@example.com") == 400
    assert codigo("app", "example.org", aplicacion="wordpress", titulo="T", correo="x@example.com") == 400
    mundo.base.dominios = ["example.org"]  # example.com ya no es de este servidor: es una dirección de fuera
    pedir("ssl", "example.org", correo="ana@example.com")
    assert mundo.ayudante.ultima[1:] == ["ssl", "example.org", "ana@example.com"]


def test_argumentos_mal_formados(mundo):
    mundo.sitio("example.org")
    assert codigo("ftp", "example.org", accion="borrar") == 400
    assert codigo("tarea-ejecutar", "example.org", id="../x") == 400
    assert codigo("base-borrar", "example.org", base="mysql") == 400
    assert codigo("base-crear", "example.org", motor="sqlite") == 400
    assert codigo("app", "example.org", aplicacion="Word Press", titulo="T", correo="a@example.org") == 400
    assert mundo.ayudante.llamadas == []


def test_listar_filtra_y_suma_el_uso(mundo):
    mundo.ayudante.respuestas[("maquita-sitios", "listar")] = {"sitios": [
        {"dominio": "example.org", "ocupado_mb": 10.5}, {"dominio": "blog.example.org", "ocupado_mb": 1},
        {"dominio": "example.com", "ocupado_mb": 99}], "estado": {}}
    mundo.base.cuotas = {"example.org": {"max_sitios": 3, "disco_mb": 500, "bases_mb": 100}}
    datos = pedir("listar")["datos"]
    assert [s["dominio"] for s in datos["sitios"]] == ["example.org", "blog.example.org"]
    assert datos["dominios"] == [{"dominio": "example.org", "cuota": {"max_sitios": 3, "disco_mb": 500, "bases_mb": 100},
                                  "uso": {"sitios": 2, "disco_mb": 11.5, "bases_mb": 0}}]
    assert datos["dns"] is True


# --- Cuotas ---


def test_cuota_de_sitios(mundo):
    mundo.sitio("example.org")
    assert codigo("crear", "blog.example.org") == 409  # por defecto, 1 sitio
    mundo.base.cuotas = {"example.org": {"max_sitios": 2, "disco_mb": 2048, "bases_mb": 1024}}
    pedir("crear", "blog.example.org")
    assert codigo("crear", "example.org") == 409  # ya existe


def test_cuota_de_disco(mundo):
    mundo.sitio("example.org")
    carpeta = mundo.tmp / "srv" / "example.org" / "publico"
    carpeta.mkdir(parents=True)
    (carpeta / "grande.bin").write_bytes(b"x" * 2 * 1024 * 1024)
    mundo.base.cuotas = {"example.org": {"max_sitios": 1, "disco_mb": 1, "bases_mb": 1024}}
    assert codigo("app", "example.org", aplicacion="wordpress", titulo="T", correo="a@example.org") == 409
    mundo.base.cuotas["example.org"]["disco_mb"] = 100
    pedir("app", "example.org", aplicacion="wordpress", titulo="T", correo="a@example.org")


def test_cuota_de_bases(mundo, monkeypatch):
    mundo.sitio("example.org")
    monkeypatch.setattr(cuotas, "bases_mb", lambda sitios: 2000.0)
    assert codigo("base-crear", "example.org", motor="mariadb") == 409
    monkeypatch.setattr(cuotas, "bases_mb", lambda sitios: 10.0)
    pedir("base-crear", "example.org", motor="mariadb")


# --- DNS ---


@pytest.fixture
def zona(mundo):
    mundo.ayudante.respuestas[("maquita-dns", "ver")] = {"zona": "example.org", "registros": [MX, WWW, SPF]}
    return mundo


def test_dns_ver_marca_los_protegidos(zona):
    registros = pedir("dns-ver", "example.org")["datos"]["registros"]
    assert {r["id"]: r["protegido"] for r in registros} == {MX["id"]: True, WWW["id"]: False, SPF["id"]: True}


def test_dns_solo_el_dominio_exacto(zona):
    assert codigo("dns-ver", "blog.example.org") == 404
    assert codigo("dns-ver", "example.com") == 404


@pytest.mark.parametrize("registro", [
    {"nombre": "@", "tipo": "MX", "valor": "mx.example.com"},
    {"nombre": "@", "tipo": "TXT", "valor": "v=spf1 include:example.com -all"},
    {"nombre": "default._domainkey", "tipo": "TXT", "valor": "v=DKIM1; p=abc"},
    {"nombre": "_dmarc", "tipo": "TXT", "valor": "v=DMARC1; p=none"},
    {"nombre": "mail", "tipo": "A", "valor": "203.0.113.5"},
    {"nombre": "mail.example.org.", "tipo": "A", "valor": "203.0.113.5"},
    {"nombre": "autodiscover", "tipo": "CNAME", "valor": "example.com"},
    {"nombre": "_mta-sts", "tipo": "TXT", "valor": "v=STSv1; id=1"},
    {"nombre": "_smtp._tls", "tipo": "TXT", "valor": "v=TLSRPTv1"},
    {"nombre": "_imaps._tcp", "tipo": "SRV", "valor": "0 993 mail"},
    {"nombre": "@", "tipo": "NS", "valor": "ns1.example.com"},
    {"nombre": "@", "tipo": "CAA", "valor": "issue example.com"},
])
def test_dns_protegido_no_se_crea(zona, registro):
    assert codigo("dns-agregar", "example.org", registro=registro) == 403
    assert codigo("dns-modificar", "example.org", id=WWW["id"], registro=registro) == 403
    assert [ll for ll in zona.ayudante.llamadas if ll[1] != "ver"] == []


def test_dns_protegido_no_se_cambia_ni_borra(zona):
    assert codigo("dns-borrar", "example.org", id=MX["id"]) == 403
    assert codigo("dns-modificar", "example.org", id=SPF["id"], registro={"nombre": "@", "tipo": "TXT", "valor": "hola"}) == 403
    assert codigo("dns-borrar", "example.org", id="ffffffff") == 404


def test_dns_registros_de_la_web(zona):
    pedir("dns-agregar", "example.org", registro={"nombre": "blog", "tipo": "A", "valor": "198.51.100.7", "sistema": True})
    programa, orden, z, datos = zona.ayudante.ultima
    assert (programa, orden, z) == ("maquita-dns", "agregar", "example.org")
    assert json.loads(de_b64(datos)) == {"nombre": "blog", "tipo": "A", "valor": "198.51.100.7"}
    pedir("dns-modificar", "example.org", id=WWW["id"], registro={"nombre": "www", "tipo": "CNAME", "valor": "@"})
    assert zona.ayudante.ultima[1:3] == ["modificar", "example.org"] and zona.ayudante.ultima[3] == WWW["id"]
    pedir("dns-borrar", "example.org", id=WWW["id"])
    assert zona.ayudante.ultima == ["maquita-dns", "borrar-registro", "example.org", WWW["id"]]


def test_dns_blog_mail_no_es_mail():
    assert not dns_protegido.es_protegido({"nombre": "blog.mail", "tipo": "A"}, "example.org")
    assert dns_protegido.es_protegido({"nombre": "_25._tcp.mail", "tipo": "TXT"}, "example.org")


# --- Subidas ---

NOMBRE = "0123456789abcdef0123456789abcdef.zip"


def test_paquete_se_copia_y_se_borra_la_subida(mundo):
    mundo.sitio("example.org")
    origen = mundo.tmp / "subidas-portal" / NOMBRE
    origen.write_bytes(b"PK\x03\x04contenido")
    pedir("paquete", "example.org", subida=NOMBRE, con_bd=False)
    programa, orden, sitio, archivo, bd_ = mundo.ayudante.ultima
    assert (orden, sitio, bd_) == ("paquete", "example.org", "sin-bd")
    assert archivo != NOMBRE and archivo.endswith(".zip")
    copia = mundo.tmp / "subidas" / archivo
    assert copia.read_bytes() == b"PK\x03\x04contenido" and oct(copia.stat().st_mode & 0o777) == "0o600"
    assert not origen.exists()


@pytest.mark.parametrize("extension, cabeza", [("7z", b"7z\xbc\xaf\x27\x1c"), ("rar", b"Rar!\x1a\x07\x01\x00")])
def test_paquete_7z_o_rar_llega_con_su_extension(mundo, extension, cabeza):
    mundo.sitio("example.org")
    nombre = NOMBRE.replace(".zip", "." + extension)
    (mundo.tmp / "subidas-portal" / nombre).write_bytes(cabeza + b"contenido")
    pedir("paquete", "example.org", subida=nombre, con_bd=False)
    programa, orden, sitio, archivo, bd_ = mundo.ayudante.ultima
    assert (orden, sitio, bd_) == ("paquete", "example.org", "sin-bd")
    assert archivo != nombre and archivo.endswith("." + extension)  # maquita-sitios decide por la extensión qué abre
    assert (mundo.tmp / "subidas" / archivo).read_bytes() == cabeza + b"contenido"


def test_paquete_con_respaldo(mundo):
    mundo.sitio("example.org")
    (mundo.tmp / "subidas-portal" / NOMBRE).write_bytes(b"PK")
    respaldo = "fedcba9876543210fedcba9876543210.sql.gz"
    (mundo.tmp / "subidas-portal" / respaldo).write_bytes(b"\x1f\x8b")
    pedir("paquete", "example.org", subida=NOMBRE, respaldo=respaldo)
    assert mundo.ayudante.ultima[4] == "con-bd" and mundo.ayudante.ultima[5].endswith(".sql.gz")


def test_subida_enlace_simbolico_rechazada(mundo):
    mundo.sitio("example.org")
    secreto = mundo.tmp / "secreto"
    secreto.write_text("clave")
    os.symlink(secreto, mundo.tmp / "subidas-portal" / NOMBRE)
    assert codigo("paquete", "example.org", subida=NOMBRE) == 400
    assert os.listdir(mundo.tmp / "subidas") == [] and mundo.ayudante.llamadas == []


def test_subida_enlace_duro_rechazada(mundo):
    mundo.sitio("example.org")
    otro = mundo.tmp / "otro"
    otro.write_bytes(b"PK")
    os.link(otro, mundo.tmp / "subidas-portal" / NOMBRE)
    assert codigo("paquete", "example.org", subida=NOMBRE) == 400
    assert otro.exists() and os.listdir(mundo.tmp / "subidas") == []


@pytest.mark.parametrize("nombre", ["../secreto.zip", "x.zip", NOMBRE.replace(".zip", ".php"), None])
def test_subida_con_nombre_no_valido(mundo, nombre):
    mundo.sitio("example.org")
    assert codigo("paquete", "example.org", subida=nombre) == 400


def test_subida_se_borra_si_se_rechaza(mundo):
    origen = mundo.tmp / "subidas-portal" / NOMBRE
    origen.write_bytes(b"PK")
    assert codigo("paquete", "example.com", subida=NOMBRE) == 404
    assert not origen.exists()


# --- psql y conexión ---


def test_psql_recibe_los_valores_como_variables(tmp_path, monkeypatch):
    """Los valores van con -v y el SQL por la entrada: la ficha nunca se pega en el texto del SQL."""
    falso = tmp_path / "psql"
    traza = tmp_path / "traza"
    falso.write_text(f"#!/bin/sh\nprintf '%s\\n' \"$@\" > {traza}.args\ncat > {traza}.sql\n"
                     "echo '{\"id\": 1, \"usuario\": \"ana\", \"activa\": true, \"totp\": true, \"dominios\": []}'\n")
    falso.chmod(0o755)
    entorno = tmp_path / "panel-dominio.env"
    entorno.write_text("PD_DB_PASS=\"secreta\"\nPD_DB_NAME=maildb\n")
    monkeypatch.setattr(rutas, "PSQL", str(falso))
    monkeypatch.setattr(rutas, "ENTORNO_PORTAL", str(entorno))
    admin = sesion.verificar(FICHA + "'; DROP TABLE pd_admins; --")
    assert admin["usuario"] == "ana"
    args = (tmp_path / "traza.args").read_text().splitlines()
    sql = (tmp_path / "traza.sql").read_text()
    assert ":'ficha'" in sql and "DROP" not in sql
    variable = next(a for a in args if a.startswith("ficha="))
    assert len(variable) == len("ficha=") + 64  # sha256, nunca la ficha
    assert "secreta" not in " ".join(args)


def test_peticion_demasiado_grande():
    import io

    with pytest.raises(ErrorPortal) as e:
        conexion.leer_peticion(io.BytesIO(b"{" + b" " * conexion.MAXIMO + b"}\n"))
    assert e.value.codigo == 413
    with pytest.raises(ErrorPortal) as e:
        conexion.leer_peticion(io.BytesIO(b"[1, 2]\n"))
    assert e.value.codigo == 400


def test_quien_llama_lo_dice_el_nucleo(monkeypatch):
    a, b = socket.socketpair(socket.AF_UNIX, socket.SOCK_STREAM)
    try:
        assert conexion.usuario_del_par(b.fileno()) == os.getuid()
    finally:
        a.close()
        b.close()
    monkeypatch.setattr(rutas, "USUARIO_PORTAL", "usuario-que-no-existe")
    assert conexion.par_autorizado(0)
    assert not conexion.par_autorizado(os.getuid()) or os.getuid() == 0


def test_reservados_sin_portal_empresa(mundo):
    assert alcance.nombres_de_nginx() == {"panel.example.org"}
