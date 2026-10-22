"""maquita-sitios-portal, v1.11: alias desde el portal, aplicaciones Node.js y Python, git de los sitios PHP, CPU y
memoria, información del servidor y DNS dinámico; y las dos órdenes sin sesión (gancho de git y /nic/update), que
traen su propia prueba. Mismo mundo de dobles que test_sitios_portal.py: el validador de maquita-sudo es el real."""

import hashlib
import hmac
import ipaddress
import json
import os
import socket
import sys

import pytest

from tests.test_sitios_portal import RAIZ, FICHA, codigo, de_b64, mundo, pedir  # noqa: F401  (mundo es la fijación)

sys.path.insert(0, os.path.join(RAIZ, "deploy", "sitios", "portal", "lib"))  # ya lo hizo test_sitios_portal

import ddns  # noqa: E402
import portal  # noqa: E402
import publico  # noqa: E402
import red  # noqa: E402
import rutas  # noqa: E402
import v111  # noqa: E402
from errores import ErrorPortal  # noqa: E402

SECRETO = "s3creto-del-gancho-que-nadie-conoce-0123"
DOC = ipaddress.ip_network("203.0.113.0/24")
POR_SITIO = {"alias", "propia-crear", "propia-estado", "propia-accion", "propia-entorno", "propia-quitar",
             "git-estado", "git-configurar", "git-clave", "git-gancho", "git-desplegar", "git-volver", "git-quitar",
             "git-credencial", "git-credencial-guardar", "git-credencial-borrar", "recursos"}
POR_ZONA = {"ddns-ver", "ddns-crear", "ddns-clave", "ddns-borrar"}


@pytest.fixture
def m(mundo, tmp_path, monkeypatch):  # noqa: F811
    for nombre in ("ganchos", "ddns", "zonas", "ssh.d"):
        (tmp_path / nombre).mkdir()
    for clave, valor in {"GANCHOS": "ganchos", "DDNS": "ddns", "ZONAS_DNS": "zonas", "SSHD_D": "ssh.d",
                         "SSHD": "sshd_config", "VSFTPD": "vsftpd.conf", "PHP_BASE": "php-base",
                         "COPIAS": "copias"}.items():
        monkeypatch.setattr(rutas, clave, str(tmp_path / valor))
    mundo.sitio("example.org")
    return mundo


def pedir_publico(orden, dominio=None, **args):
    return portal.atender({"orden": orden, "dominio": dominio, "args": args})


def codigo_publico(orden, dominio=None, **args):
    with pytest.raises(ErrorPortal) as e:
        pedir_publico(orden, dominio, **args)
    return e.value.codigo


def json_de(texto):
    return json.loads(de_b64(texto))


# --- Lista y alcance ---


def test_la_lista_v111():
    assert set(v111.ORDENES) == POR_SITIO | POR_ZONA | {"servidor-info"}
    assert all(v111.ORDENES[o][0] == "sitio" for o in POR_SITIO)
    assert all(v111.ORDENES[o][0] == "zona" for o in POR_ZONA)
    assert v111.ORDENES["servidor-info"][0] == "ninguno"
    # Las de sin sesión no están en la lista de las de sesión (y al revés): ninguna se cuela por la otra puerta.
    assert not set(publico.ORDENES) & set(portal.ORDENES)


@pytest.mark.parametrize("orden", sorted(POR_SITIO))
def test_alcance_por_sitio(m, orden):
    m.sitio("example.com")
    assert codigo(orden, "example.com") == 404
    assert codigo(orden, "blog.example.com") == 404
    assert codigo(orden, "nada.example.org") == 404  # en su alcance, pero no existe
    m.sitio("mail.example.org")
    assert codigo(orden, "mail.example.org") == 403
    assert m.ayudante.llamadas == []


@pytest.mark.parametrize("orden", sorted(POR_ZONA))
def test_alcance_por_zona(m, orden):
    assert codigo(orden, "example.com", nombre="casa", id="0123abcd") == 404
    assert codigo(orden, "blog.example.org", nombre="casa", id="0123abcd") == 404  # la zona es el dominio exacto
    assert m.ayudante.llamadas == []


def test_las_del_sistema_siguen_fuera(m):
    for orden in ("git-desplegar-ahora", "recursos-recoger", "propia-puerto"):
        assert codigo(orden, "example.org") == 400
    assert m.ayudante.llamadas == []


def test_sin_sesion_no_hay_ordenes_de_sesion(m):
    """Sin ficha solo pasan las dos públicas; cualquier otra pide sesión."""
    for orden in sorted(POR_SITIO) + ["servidor-info", "ddns-crear"]:
        assert codigo_publico(orden, "example.org") == 403
    assert m.ayudante.llamadas == []


# --- Alias ---


def test_alias_se_traduce(m):
    m.sitio("example.org", alias=["tienda.example.org"])
    pedir("alias", "example.org", alias=["www.Tienda.example.org", "tienda.example.org", "example.org", "blog.example.org"])
    orden = m.ayudante.ultima
    assert orden[:3] == ["maquita-sitios", "alias", "example.org"]
    assert json_de(orden[3]) == ["tienda.example.org", "blog.example.org"]  # sin repetidos, sin www ni el propio


def test_alias_vacio_quita_todos(m):
    pedir("alias", "example.org", alias=[])
    assert json_de(m.ayudante.ultima[3]) == []


@pytest.mark.parametrize("ajeno", ["example.com", "tienda.example.com", "example.org.example.com", "otroexample.org"])
def test_alias_de_otro_dominio_no(m, ajeno):
    assert codigo("alias", "example.org", alias=[ajeno]) == 400
    assert m.ayudante.llamadas == []


@pytest.mark.parametrize("reservado", ["mail.example.org", "webmail.example.org", "autodiscover.example.org",
                                       "servidor.example.org", "portal.example.org", "panel.example.org"])
def test_alias_reservado(m, reservado):
    assert codigo("alias", "example.org", alias=[reservado]) == 403
    assert m.ayudante.llamadas == []


def test_alias_que_ya_es_un_sitio_o_de_otro(m):
    m.sitio("blog.example.org")
    assert codigo("alias", "example.org", alias=["blog.example.org"]) == 409
    m.sitio("tienda.example.org", alias=["shop.example.org"])
    assert codigo("alias", "example.org", alias=["shop.example.org"]) == 409
    assert m.ayudante.llamadas == []


@pytest.mark.parametrize("lista", [None, "tienda.example.org", [1], ["no es un nombre"], ["a.example.org"] * 11,
                                   ["../example.org"], ["x" * 70 + ".example.org"]])
def test_alias_formas_no_validas(m, lista):
    assert codigo("alias", "example.org", alias=lista) == 400
    assert m.ayudante.llamadas == []


# --- Aplicaciones Node.js y Python ---


@pytest.fixture
def publica(monkeypatch):
    """Las direcciones de documentación (203.0.113.x) hacen de «Internet» en las pruebas."""
    monkeypatch.setattr(red, "es_publica", lambda d: d in DOC)
    monkeypatch.setattr(socket, "getaddrinfo", lambda host, *a, **k: {
        "git.example.org": [(2, 1, 6, "", ("203.0.113.20", 0))],
        "interno.example.org": [(2, 1, 6, "", ("192.0.2.5", 0))],
        "local.example.org": [(2, 1, 6, "", ("127.0.0.1", 0))],
    }.get(host) or (_ for _ in ()).throw(socket.gaierror("no existe")))


def test_propia_crear_se_traduce(m, publica):
    pedir("propia-crear", "example.org", tipo="node", conf={"git": "https://git.example.org/ana/app.git", "rama": "main",
                                                          "entrada": "server.js", "spa": False, "modo": ""})
    orden = m.ayudante.ultima
    assert orden[:4] == ["maquita-sitios", "propia-crear", "example.org", "node"]
    assert json_de(orden[4]) == {"git": "https://git.example.org/ana/app.git", "rama": "main", "entrada": "server.js",
                                 "spa": False}


@pytest.mark.parametrize("conf", [{"puerto_publico": 30000}, {"protocolo": "udp"}])
def test_propia_sin_puerto_publico(m, conf):
    assert codigo("propia-crear", "example.org", tipo="python", conf=conf) == 403
    assert m.ayudante.llamadas == []


@pytest.mark.parametrize("git", ["https://interno.example.org/a.git", "https://local.example.org/a.git",
                                 "https://192.0.2.7/a.git", "https://127.0.0.1/a.git", "https://[::1]/a.git",
                                 "https://no-existe.example.org/a.git", "http://git.example.org/a.git",
                                 "https://ana:clave@git.example.org/a.git", "https://git.example.org/../a.git",
                                 "file:///etc/passwd", "ssh://ana:clave@git.example.org/a.git",
                                 "git@interno.example.org:ana/a.git", "ext::sh -c id"])
def test_propia_git_solo_publico(m, publica, git):
    assert codigo("propia-crear", "example.org", tipo="node", conf={"git": git}) == 400
    assert m.ayudante.llamadas == []


@pytest.mark.parametrize("git", ["ssh://git@git.example.org/ana/app.git", "git@git.example.org:ana/app.git"])
def test_propia_git_privado_por_ssh(m, publica, git):
    """Repositorios privados: por SSH, con la autenticación del sitio (la clave nunca va en la dirección)."""
    pedir("propia-crear", "example.org", tipo="node", conf={"git": git})
    assert json_de(m.ayudante.ultima[4]) == {"git": git}


@pytest.mark.parametrize("tipo,conf", [("php", {}), (None, {}), ("node", {"desconocida": 1}), ("node", {"spa": "sí"}),
                                       ("node", {"entrada": "a\nb"}), ("node", "texto")])
def test_propia_formas_no_validas(m, tipo, conf):
    assert codigo("propia-crear", "example.org", tipo=tipo, conf=conf) == 400
    assert m.ayudante.llamadas == []


def test_propia_cuenta_para_el_disco(m):
    carpeta = m.tmp / "srv" / "example.org"
    carpeta.mkdir(parents=True)
    (carpeta / "grande.bin").write_bytes(b"x" * 2 * 1024 * 1024)
    m.base.cuotas = {"example.org": {"max_sitios": 1, "disco_mb": 1, "bases_mb": 1024}}
    assert codigo("propia-crear", "example.org", tipo="python", conf={}) == 409
    assert codigo("propia-accion", "example.org", accion="desplegar") == 409
    pedir("propia-accion", "example.org", accion="reiniciar")  # reiniciar no hace crecer nada
    assert m.ayudante.ultima == ["maquita-sitios", "propia-accion", "example.org", "reiniciar"]


def test_propia_entorno_y_quitar(m):
    pedir("propia-entorno", "example.org", variables={"CLAVE_API": "x-1", "GUARDADA": None})
    assert json_de(m.ayudante.ultima[3]) == {"CLAVE_API": "x-1", "GUARDADA": None}
    for variables in ({"minuscula": "x"}, {"PORT": 1}, {"A": "a\nb"}, {f"V{i}": "x" for i in range(51)}, ["A"]):
        assert codigo("propia-entorno", "example.org", variables=variables) == 400
    assert codigo("propia-accion", "example.org", accion="borrar") == 400
    assert codigo("propia-quitar", "example.org", confirmacion="example.com") == 400
    pedir("propia-quitar", "example.org", confirmacion="Example.org")
    assert m.ayudante.ultima == ["maquita-sitios", "propia-quitar", "example.org", "example.org"]


# --- Git de los sitios PHP ---


def test_git_configurar_se_traduce(m):
    pedir("git-configurar", "example.org", git={"repo": "git@git.example.org:ana/sitio.git", "rama": "",
                                                "carpeta": "dist", "raiz_web": "public", "exclusiones": [" uploads "]})
    orden = m.ayudante.ultima
    assert orden[:3] == ["maquita-sitios", "git-configurar", "example.org"]
    assert json_de(orden[3]) == {"repo": "git@git.example.org:ana/sitio.git", "rama": "main", "carpeta": "dist",
                                 "raiz_web": "public", "exclusiones": ["uploads"]}


@pytest.mark.parametrize("git", [None, "repo", {"repo": ""}, {"repo": "x", "otra": 1}, {"repo": "a\nb"},
                                 {"repo": "x", "exclusiones": ["a"] * 21}, {"repo": "x", "exclusiones": "a"},
                                 {"repo": "x", "rama": 5}])
def test_git_configurar_formas_no_validas(m, git):
    assert codigo("git-configurar", "example.org", git=git) == 400
    assert m.ayudante.llamadas == []


def test_git_ordenes_sencillas(m):
    pedir("git-desplegar", "example.org")
    assert m.ayudante.ultima == ["maquita-sitios", "git-desplegar", "example.org", "panel"]  # nunca «gancho» desde aquí
    pedir("git-gancho", "example.org", accion="activar")
    assert m.ayudante.ultima == ["maquita-sitios", "git-gancho", "example.org", "activar"]
    pedir("git-volver", "example.org", version="20261021-101010")
    assert m.ayudante.ultima == ["maquita-sitios", "git-volver", "example.org", "20261021-101010"]
    pedir("git-quitar", "example.org", confirmacion="example.org")
    assert m.ayudante.ultima == ["maquita-sitios", "git-quitar", "example.org", "example.org"]
    for orden, args in (("git-gancho", {"accion": "renovar"}), ("git-volver", {"version": "../x"}),
                        ("git-volver", {"version": "20261021-1010"}), ("git-quitar", {"confirmacion": "x"})):
        assert codigo(orden, "example.org", **args) == 400


def test_git_desplegar_cuenta_para_el_disco(m):
    carpeta = m.tmp / "srv" / "example.org"
    carpeta.mkdir(parents=True)
    (carpeta / "grande.bin").write_bytes(b"x" * 2 * 1024 * 1024)
    m.base.cuotas = {"example.org": {"max_sitios": 1, "disco_mb": 1, "bases_mb": 1024}}
    assert codigo("git-desplegar", "example.org") == 409
    assert m.ayudante.llamadas == []


# --- Gancho de git (sin sesión) ---


def _gancho(m, sitio="example.org", gancho=True, rama="main", secreto=SECRETO):
    m.sitio(sitio, git_php={"gancho": gancho, "rama": rama, "repo": "git@git.example.org:a/b.git"})
    if secreto:
        (m.tmp / "ganchos" / f"{sitio}.json").write_text(json.dumps({"secreto": secreto}))


def _cuerpo(m, datos, nombre="0123456789abcdef0123456789abcdef.gancho"):
    texto = datos if isinstance(datos, bytes) else json.dumps(datos).encode()
    (m.tmp / "subidas-portal" / nombre).write_bytes(texto)
    return nombre, texto


def _firma(texto, secreto=SECRETO):
    return hmac.new(secreto.encode(), texto, hashlib.sha256).hexdigest()


def test_gancho_github_despliega(m):
    _gancho(m)
    nombre, texto = _cuerpo(m, {"ref": "refs/heads/main", "after": "a" * 40})
    r = pedir_publico("gancho-git", "example.org", subida=nombre, firma="sha256=" + _firma(texto), evento="push")
    assert r["datos"]["estado"] == "en curso" and r["datos"]["http"] == 202
    assert m.ayudante.ultima == ["maquita-sitios", "git-desplegar", "example.org", "gancho"]
    assert os.listdir(m.tmp / "subidas-portal") == []  # el cuerpo se borra al leerlo


def test_gancho_gitea_y_gitlab(m):
    _gancho(m)
    nombre, texto = _cuerpo(m, {"ref": "refs/heads/main"})
    pedir_publico("gancho-git", "example.org", subida=nombre, firma=_firma(texto), evento="push")  # Gitea: hex sin prefijo
    nombre, _ = _cuerpo(m, {"ref": "refs/heads/main"})
    pedir_publico("gancho-git", "example.org", subida=nombre, ficha_gitlab=SECRETO, evento="Push Hook")
    assert [ll[1] for ll in m.ayudante.llamadas] == ["git-desplegar", "git-desplegar"]


@pytest.mark.parametrize("caso", ["firma_mala", "otro_secreto", "sin_firma", "gitlab_malo", "sin_secreto", "gancho_apagado",
                                  "no_existe", "nombre_raro", "subida_rara", "secreto_corto"])
def test_gancho_rechazos_iguales(m, caso):
    _gancho(m, gancho=caso != "gancho_apagado", secreto={"sin_secreto": None, "secreto_corto": "corto"}.get(caso, SECRETO))
    nombre, texto = _cuerpo(m, {"ref": "refs/heads/main"})
    args = {"subida": nombre, "firma": "sha256=" + _firma(texto)}
    sitio = "example.org"
    if caso == "firma_mala":
        args["firma"] = "sha256=" + "0" * 64
    elif caso == "otro_secreto":
        args["firma"] = "sha256=" + _firma(texto, "otro-secreto-de-otro-sitio-0123456789")
    elif caso == "sin_firma":
        args.pop("firma")
    elif caso == "gitlab_malo":
        args = {"subida": nombre, "ficha_gitlab": SECRETO[:-1]}
    elif caso == "no_existe":
        sitio = "nada.example.org"
    elif caso == "nombre_raro":
        sitio = "../example.org"
    elif caso == "subida_rara":
        args["subida"] = "../../etc/passwd"
    with pytest.raises(ErrorPortal) as e:
        pedir_publico("gancho-git", sitio, **args)
    assert e.value.codigo == 403 and e.value.texto == publico.NO_VALE
    assert m.ayudante.llamadas == []
    # Lo que llegó se borra siempre (con un nombre raro, el intermediario ni lo busca: lo borra el portal).
    assert os.listdir(m.tmp / "subidas-portal") == ([nombre] if caso == "subida_rara" else [])


def test_gancho_ping_otra_rama_y_otros_eventos(m):
    _gancho(m, rama="produccion")
    for datos, evento, estado in (({"zen": "hola"}, "ping", "listo"), ({"ref": "refs/heads/main"}, "push", "ignorado"),
                                  ({"ref": "refs/tags/produccion"}, "push", "ignorado"),
                                  ({"ref": "refs/heads/produccion"}, "issues", "ignorado")):
        nombre, texto = _cuerpo(m, datos)
        r = pedir_publico("gancho-git", "example.org", subida=nombre, firma=_firma(texto), evento=evento)
        assert r["datos"]["estado"] == estado
    assert m.ayudante.llamadas == []


def test_gancho_sin_json_y_ocupado(m):
    _gancho(m)
    nombre, texto = _cuerpo(m, b"payload=%7B%7D")
    assert codigo_publico("gancho-git", "example.org", subida=nombre, firma=_firma(texto)) == 400
    m.ayudante.respuestas[("maquita-sitios", "git-desplegar")] = {"error": "ya hay un despliegue en curso para este sitio"}
    nombre, texto = _cuerpo(m, {"ref": "refs/heads/main"})
    r = pedir_publico("gancho-git", "example.org", subida=nombre, firma=_firma(texto))
    assert r["datos"]["estado"] == "ocupado" and r["datos"]["http"] == 409


def test_gancho_subida_ajena_o_grande(m):
    _gancho(m)
    nombre, texto = _cuerpo(m, b"x" * (1024 * 1024 + 1))
    assert codigo_publico("gancho-git", "example.org", subida=nombre, firma=_firma(texto)) == 413
    os.link(m.tmp / "ganchos" / "example.org.json", m.tmp / "subidas-portal" / "ffffffffffffffffffffffffffffffff.gancho")
    assert codigo_publico("gancho-git", "example.org", subida="ffffffffffffffffffffffffffffffff.gancho",
                          firma="0" * 64) == 403  # un enlace duro a lo de root no se acepta
    assert m.ayudante.llamadas == []


# --- Información del servidor y recursos ---


def test_servidor_info(m):
    (m.tmp / "php-base").write_text("8.4\n")
    (m.tmp / "vsftpd.conf").write_text("listen=YES\nssl_enable=YES\npasv_min_port=40000\npasv_max_port=40100\n")
    (m.tmp / "ssh.d" / "sitios.conf").write_text("# del sitio\nPort 2222\n")
    (m.tmp / "sshd_config").write_text("Port 22\n")
    (m.tmp / "zonas" / "example.org.json").write_text("{}")
    m.base.admin["dominios"] = ["example.org", "example.net"]
    m.ayudante.respuestas[("maquita-sitios", "php-estado")] = {
        "instaladas": ["8.2", "8.4"], "disponibles": ["8.5"], "en_uso": {"8.4": 9},
        "notas": {"8.2": "sin soporte de seguridad", "8.5": "nueva"}}
    m.ayudante.respuestas[("maquita-dns", "servidor-ver")] = {
        "ip_correo": "192.0.2.10", "ip_web": "192.0.2.11", "ns": [{"nombre": "ns1", "ip": "192.0.2.12"},
                                                                  {"nombre": "ns2", "ip": "192.0.2.13"}]}
    datos = pedir("servidor-info")["datos"]
    assert datos["servidor"] == "servidor.example.org"
    assert datos["ip_compartida"] == "192.0.2.11"
    assert datos["servidores_de_nombres"] == {"example.org": ["ns1.example.org", "ns2.example.org"]}  # example.net no está aquí
    assert datos["php"] == {"instaladas": ["8.2", "8.4"], "de_serie": "8.4", "notas": {"8.2": "sin soporte de seguridad"}}
    assert datos["ftp"] == {"puerto": 21, "cifrado": True, "pasivos": "40000-40100"}
    assert datos["sftp"] == {"puerto": 2222}
    assert set(datos["cuotas"]) == {"example.org", "example.net"}
    assert ["maquita-dns", "servidor-ver"] in m.ayudante.llamadas
    texto = json.dumps(datos)
    assert "en_uso" not in texto and "example.com" not in texto and "192.0.2.12" not in texto


def test_servidor_info_sin_dns_ni_ftp(m):
    os.remove(rutas.MAQUITA_DNS)
    datos = pedir("servidor-info")["datos"]
    assert datos["ip_compartida"] is None and datos["servidores_de_nombres"] == {}
    assert datos["ftp"] is None and datos["sftp"] == {"puerto": 22}


def test_recursos(m):
    pedir("recursos", "example.org")
    assert m.ayudante.ultima == ["maquita-sitios", "recursos", "example.org"]


# --- DNS dinámico ---


@pytest.fixture
def zona(m):
    registros = [{"id": "0000000a", "nombre": "@", "tipo": "MX", "valor": "mail.example.org.", "ttl": 3600},
                 {"id": "0000000b", "nombre": "www", "tipo": "A", "valor": "192.0.2.10", "ttl": 3600, "sistema": True},
                 {"id": "0000000c", "nombre": "alias", "tipo": "CNAME", "valor": "otro.example.com.", "ttl": 3600},
                 {"id": "0000000d", "nombre": "casa", "tipo": "A", "valor": "198.51.100.1", "ttl": 300}]
    m.registros = registros
    m.ayudante.respuestas[("maquita-dns", "ver")] = lambda args: {"zona": "example.org", "registros": registros}
    return m


def _crear(zona_, nombre="casa"):
    return pedir("ddns-crear", "example.org", nombre=nombre)["datos"]


def test_ddns_crear_y_ver(zona):
    datos = _crear(zona, "Casa.example.org")
    ficha = datos["creada"]
    assert ficha["nombre"] == "casa" and ficha["zona"] == "example.org" and ficha["usuario"].startswith("ddns-")
    assert len(datos["clave"]) >= 20 and datos["ruta"] == "/nic/update"
    visto = pedir("ddns-ver", "example.org")["datos"]
    assert [f["nombre"] for f in visto["fichas"]] == ["casa"]
    assert datos["clave"] not in json.dumps(visto) and "clave_hash" not in json.dumps(visto)
    guardado = json.loads((zona.tmp / "ddns" / "fichas.json").read_text())
    assert datos["clave"] not in json.dumps(guardado)  # solo el hash
    assert oct(os.stat(zona.tmp / "ddns" / "fichas.json").st_mode)[-3:] == "600"
    assert pedir("ddns-ver", "example.org")["datos"]["fichas"][0]["usuario"] == ficha["usuario"]
    assert _codigo_crear(zona, "casa") == 409  # repetida


def _codigo_crear(zona_, nombre):
    return codigo("ddns-crear", "example.org", nombre=nombre)


@pytest.mark.parametrize("nombre,esperado", [
    ("mail", 403), ("webmail", 403), ("autodiscover", 403), ("ns1", 403), ("_dmarc", 400), ("x._domainkey", 400),
    ("www", 409), ("alias", 409), ("@", 400), ("*", 400), ("", 400), ("a..b", 400), ("-a", 400), ("a" * 64, 400),
])
def test_ddns_nombres_no_admitidos(zona, nombre, esperado):
    assert _codigo_crear(zona, nombre) == esperado
    assert not (zona.tmp / "ddns" / "fichas.json").exists()


def test_ddns_no_para_un_sitio(zona):
    zona.sitio("tienda.example.org")
    assert _codigo_crear(zona, "tienda") == 409
    zona.sitio("blog.example.com", alias=["blog.example.org"])
    assert _codigo_crear(zona, "blog") == 409


def test_ddns_actualizar(zona):
    datos = _crear(zona, "oficina")
    usuario, clave = datos["creada"]["usuario"], datos["clave"]
    r = pedir_publico("ddns-actualizar", usuario=usuario, clave=clave, hostname="oficina.example.org", myip="203.0.113.5")
    assert r["datos"]["respuesta"] == "good 203.0.113.5"
    programa, orden, zona_, texto = zona.ayudante.ultima
    assert (programa, orden, zona_) == ("maquita-dns", "agregar", "example.org")
    assert json_de(texto) == {"nombre": "oficina", "tipo": "A", "valor": "203.0.113.5", "ttl": 60}
    llamadas = len(zona.ayudante.llamadas)
    r = pedir_publico("ddns-actualizar", usuario=usuario, clave=clave, hostname="oficina.example.org", myip="203.0.113.5")
    assert r["datos"]["respuesta"] == "nochg 203.0.113.5" and len(zona.ayudante.llamadas) == llamadas
    # Sin myip, la IP desde la que llega la petición; IPv6 va a su propio registro AAAA.
    r = pedir_publico("ddns-actualizar", usuario=usuario, clave=clave, hostname="oficina.example.org",
                      ip_cliente="2001:db8::7")
    assert r["datos"]["respuesta"] == "good 2001:db8::7" and json_de(zona.ayudante.ultima[3])["tipo"] == "AAAA"


def test_ddns_cambia_el_registro_que_ya_hay(zona):
    datos = _crear(zona, "casa")
    pedir_publico("ddns-actualizar", usuario=datos["creada"]["usuario"], clave=datos["clave"], hostname="casa.example.org",
                  myip="198.51.100.9")
    assert zona.ayudante.ultima[:4] == ["maquita-dns", "modificar", "example.org", "0000000d"]


@pytest.mark.parametrize("cambio,esperado", [
    ({"clave": "otra-clave"}, "badauth"), ({"usuario": "ddns-00000000"}, "badauth"), ({"usuario": "ana"}, "badauth"),
    ({"clave": ""}, "badauth"), ({"hostname": "otra.example.org"}, "nohost"), ({"hostname": "casa.example.com"}, "nohost"),
    ({"hostname": "casa.example.org,otra.example.org"}, "nohost"), ({"hostname": "no es un nombre"}, "notfqdn"),
    ({"hostname": None}, "notfqdn"), ({"myip": "127.0.0.1"}, "dnserr"), ({"myip": "no-es-ip"}, "dnserr"),
    ({"myip": "fe80::1"}, "dnserr"), ({"myip": "224.0.0.1"}, "dnserr"),
])
def test_ddns_rechazos(zona, cambio, esperado):
    datos = _crear(zona, "casa")
    args = {"usuario": datos["creada"]["usuario"], "clave": datos["clave"], "hostname": "casa.example.org",
            "myip": "203.0.113.5", **cambio}
    llamadas = len(zona.ayudante.llamadas)
    assert pedir_publico("ddns-actualizar", **args)["datos"]["respuesta"] == esperado
    assert len(zona.ayudante.llamadas) == llamadas  # no se tocó la zona


def test_ddns_limite_de_frecuencia(zona):
    datos = _crear(zona, "casa")
    args = {"usuario": datos["creada"]["usuario"], "clave": datos["clave"], "hostname": "casa.example.org"}
    respuestas = [pedir_publico("ddns-actualizar", myip=f"203.0.113.{i + 1}", **args)["datos"]["respuesta"] for i in range(12)]
    assert respuestas[:10] == [f"good 203.0.113.{i + 1}" for i in range(10)]
    assert respuestas[10:] == ["abuse", "abuse"]


def test_ddns_clave_nueva_y_borrar(zona):
    datos = _crear(zona, "casa")
    ident, usuario, vieja = datos["creada"]["id"], datos["creada"]["usuario"], datos["clave"]
    nueva = pedir("ddns-clave", "example.org", id=ident)["datos"]["clave"]
    assert nueva != vieja
    args = {"usuario": usuario, "hostname": "casa.example.org", "myip": "203.0.113.5"}
    assert pedir_publico("ddns-actualizar", clave=vieja, **args)["datos"]["respuesta"] == "badauth"
    assert pedir_publico("ddns-actualizar", clave=nueva, **args)["datos"]["respuesta"].startswith("good")
    assert codigo("ddns-clave", "example.org", id="ffffffff") == 404
    assert codigo("ddns-borrar", "example.org", id="nada") == 400
    pedir("ddns-borrar", "example.org", id=ident)
    assert pedir_publico("ddns-actualizar", clave=nueva, **args)["datos"]["respuesta"] == "badauth"


def test_ddns_ficha_de_otra_zona_no_se_toca(zona):
    """Una ficha de example.com (de otro administrador) no se ve ni se cambia desde example.org."""
    with ddns.cerrojo():
        fichas = ddns.cargar()
        ajena, _ = ddns.nueva(fichas, "example.com", "casa")
        ddns.guardar(fichas)
    assert pedir("ddns-ver", "example.org")["datos"]["fichas"] == []
    assert codigo("ddns-clave", "example.org", id=ajena["id"]) == 404
    assert codigo("ddns-borrar", "example.org", id=ajena["id"]) == 404
    assert ddns.cargar()[0]["id"] == ajena["id"]


def test_ficha_de_sesion_no_hace_falta_para_lo_publico(m):
    """Con ficha o sin ella, lo público se atiende igual: la prueba es la suya, no la sesión."""
    m.base.admin = None
    assert portal.atender({"ficha": FICHA, "orden": "ddns-actualizar", "args": {"usuario": "ana"}})["datos"] == {
        "respuesta": "badauth"}
