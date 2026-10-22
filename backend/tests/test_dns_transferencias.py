"""Transferencias de zona a secundarios (allow-transfer, also-notify, TSIG y maestro oculto) de maquita-dns."""

import json
import os
import shutil
import subprocess
import sys

import pytest

sys.path.insert(
    0, os.path.join(os.path.dirname(__file__), "..", "..", "deploy", "dns", "lib")
)
T = pytest.importorskip("transferencias")
zona = pytest.importorskip("zona")
O = pytest.importorskip("ordenes_transferencias")
I = pytest.importorskip("importar_transferencias")
from comun import ErrorDns

DNS2, HE, RED6 = "198.51.100.53", "203.0.113.2", "2001:db8:53::/64"
SECRETO = "A" * 43 + "="


def _ruta(z):
    return f"/etc/bind/zonas/db.{z}"


def _bloques(texto):
    """{zona: cuerpo de su declaración}."""
    return dict(I.RE_ZONA.findall(texto))


# --- Validación ---


def test_sin_configurar_es_lo_de_siempre():
    texto = T.texto_lista(
        [("example.org", None)], T.defecto(), _ruta, "/etc/bind/maquita-tsig.key"
    )
    assert texto == (
        "// Generado por el panel (Zonas DNS). No editar a mano.\n"
        'zone "example.org" {\n    type primary;\n    file "/etc/bind/zonas/db.example.org";\n'
        "    allow-transfer { none; };\n    notify no;\n};\n"
    )


def test_servidor_sin_clave_transferencias_da_lo_de_siempre():
    assert T.de_servidor({"ip_correo": "192.0.2.10"}) == T.defecto()
    assert T.de_servidor(None) == T.defecto()


@pytest.mark.parametrize(
    "valor",
    [
        "0.0.0.0/0",
        "::/0",
        "198.51.100.0/33",
        "198.51.100.1/24",
        "ejemplo",
        "224.0.0.1",
        "0.0.0.0",
    ],
)
def test_transferir_rechaza(valor):
    with pytest.raises(ErrorDns):
        T.validar_transferir([valor])


def test_transferir_normaliza_y_quita_repetidas():
    assert T.validar_transferir(f"{DNS2}, {HE},{DNS2}/32,{RED6}") == [DNS2, HE, RED6]
    assert T.validar_transferir("ninguna") == []
    with pytest.raises(ErrorDns):
        T.validar_transferir([f"198.51.100.{i}" for i in range(21)])


def test_notificar_con_puerto():
    assert T.validar_notificar(
        f"{DNS2},{HE}:5353,[2001:db8::53]:5300,2001:db8::54,{HE}:53,{DNS2}"
    ) == [
        {"ip": DNS2, "puerto": None},
        {"ip": HE, "puerto": 5353},
        {"ip": "2001:db8::53", "puerto": 5300},
        {"ip": "2001:db8::54", "puerto": None},
        {"ip": HE, "puerto": None},
    ]
    assert [
        T.texto_destino(d)
        for d in T.validar_notificar(f"{HE}:5353,[2001:db8::53]:5300,{DNS2}:53")
    ] == [f"{HE}:5353", "[2001:db8::53]:5300", DNS2]


@pytest.mark.parametrize(
    "valor",
    [
        "198.51.100.53:0",
        "198.51.100.53:70000",
        "198.51.100.0/24",
        "[2001:db8::1]:x",
        "ns1.example.org",
    ],
)
def test_notificar_rechaza(valor):
    with pytest.raises(ErrorDns):
        T.validar_notificar([valor])


def test_tsig_solo_hmac_sha256_y_nombre_valido():
    with pytest.raises(ErrorDns):
        T.normalizar({"tsig": {"nombre": "x", "algoritmo": "hmac-md5"}})
    with pytest.raises(ErrorDns):
        T.nombre_tsig('mala"clave')
    assert T.normalizar({"tsig": {"nombre": "Xfr.Example.org."}})["tsig"] == {
        "nombre": "xfr.example.org",
        "algoritmo": "hmac-sha256",
    }
    assert T.RE_SECRETO.fullmatch(T.secreto_nuevo())


# --- Texto para BIND ---


def test_con_transferencias_y_avisos():
    conf = T.normalizar(
        {"transferir_a": [DNS2, HE], "notificar_a": [DNS2, f"{HE}:5353"]}
    )
    bloque = T.bloque_zona("example.org", _ruta("example.org"), conf)
    assert f"allow-transfer {{ {DNS2}; {HE}; }};" in bloque
    assert "notify explicit;" in bloque
    assert f"also-notify {{ {DNS2}; {HE} port 5353; }};" in bloque
    assert "none" not in bloque


def test_con_tsig_pide_ip_y_clave():
    conf = T.normalizar(
        {"transferir_a": [DNS2], "notificar_a": [DNS2], "tsig": {"nombre": "xfr"}}
    )
    texto = T.texto_lista(
        [("example.org", None)], conf, _ruta, "/etc/bind/maquita-tsig.key"
    )
    assert 'include "/etc/bind/maquita-tsig.key";' in texto
    assert f'allow-transfer {{ !{{ !{DNS2}; any; }}; key "xfr"; }};' in texto
    assert f'also-notify {{ {DNS2} key "xfr"; }};' in texto
    solo_clave = T.normalizar({"tsig": {"nombre": "xfr"}, "notificar_a": [DNS2]})
    assert 'allow-transfer { key "xfr"; };' in T.bloque_zona(
        "example.org", "f", solo_clave
    )


def test_ajuste_propio_de_zona_sobrescribe_solo_lo_suyo():
    conf = T.normalizar({"transferir_a": [DNS2], "notificar_a": [DNS2]})
    texto = T.texto_lista(
        [("example.org", None), ("example.com", {"transferir_a": [HE]})],
        conf,
        _ruta,
        "k",
    )
    org, com = texto.split('zone "example.com"')
    assert f"allow-transfer {{ {DNS2}; }};" in org
    assert (
        f"allow-transfer {{ {HE}; }};" in com and f"also-notify {{ {DNS2}; }};" in com
    )
    sin = T.texto_lista(
        [("example.com", {"transferir_a": [], "notificar_a": []})], conf, _ruta, "k"
    )
    assert "allow-transfer { none; };" in sin and "notify no;" in sin


@pytest.mark.skipif(
    not shutil.which("named-checkconf"), reason="sin BIND en esta máquina"
)
def test_bind_acepta_lo_generado(tmp_path):
    clave = tmp_path / "tsig.key"
    tsig = {"nombre": "xfr", "algoritmo": "hmac-sha256"}
    clave.write_text(T.texto_clave(tsig, T.secreto_nuevo()))
    conf = T.normalizar(
        {
            "transferir_a": [DNS2, RED6],
            "notificar_a": [DNS2, "[2001:db8::53]:5300"],
            "tsig": tsig,
        }
    )
    lista = T.texto_lista(
        [("example.org", None), ("example.com", {"transferir_a": [HE]})],
        conf,
        lambda z: str(tmp_path / f"db.{z}"),
        str(clave),
    )
    lista += T.texto_lista(
        [("example.net", None)], T.defecto(), lambda z: str(tmp_path / f"db.{z}"), "k"
    )
    (tmp_path / "named.conf").write_text(lista)
    r = subprocess.run(
        ["named-checkconf", str(tmp_path / "named.conf")],
        capture_output=True,
        text=True,
        check=False,
    )
    assert r.returncode == 0, r.stdout + r.stderr
    secundario = tmp_path / "secundario.conf"
    secundario.write_text(
        T.para_el_secundario(tsig, T.secreto_de(clave.read_text()), "192.0.2.10")
    )
    r = subprocess.run(
        ["named-checkconf", str(secundario)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert r.returncode == 0, r.stdout + r.stderr


# --- Maestro oculto ---


SRV = {
    "ip_correo": "192.0.2.10",
    "ns": [{"nombre": "ns1", "ip": DNS2}, {"nombre": "ns2", "ip": HE}],
}


def test_maestro_oculto_exige_secundarios_y_ns_ajenos():
    conf = T.normalizar(
        {"transferir_a": [DNS2, HE], "notificar_a": [DNS2, HE], "maestro_oculto": True}
    )
    T.comprobar_maestro_oculto(conf, SRV)
    with pytest.raises(ErrorDns, match="192.0.2.10"):
        T.comprobar_maestro_oculto(
            conf, dict(SRV, ns=SRV["ns"] + [{"nombre": "ns3", "ip": "192.0.2.10"}])
        )
    with pytest.raises(ErrorDns, match="--notificar-a"):
        T.comprobar_maestro_oculto(
            T.normalizar({"transferir_a": [DNS2], "maestro_oculto": True}), SRV
        )
    T.comprobar_maestro_oculto(
        T.defecto(), dict(SRV, ns=[{"nombre": "ns1", "ip": "192.0.2.10"}])
    )


# --- Órdenes (con BIND simulado) ---


@pytest.fixture
def servidor(tmp_path, monkeypatch):
    datos = tmp_path / "datos"
    datos.mkdir()
    (datos / "servidor.json").write_text(json.dumps(SRV))
    for z in ("example.org", "example.com"):
        (datos / f"{z}.json").write_text(
            json.dumps({"zona": z, "serial": 1, "registros": []})
        )
    lista, clave = tmp_path / "maquita-zonas.conf", tmp_path / "maquita-tsig.key"
    ordenes = []
    estado = {"rechazar": False}

    def ejecutar(cmd, entrada=None, tiempo=120):
        ordenes.append(cmd)
        if cmd == ["named-checkconf"] and estado["rechazar"]:
            raise ErrorDns("named-checkconf: error de prueba")
        return ""

    def escribir(ruta, texto, modo=0o644, grupo=None):
        with open(ruta, "w") as f:
            f.write(texto)

    for m in (zona, O, I):
        for nombre, valor in (
            ("DATOS", str(datos)),
            ("LISTA_BIND", str(lista)),
            ("TSIG_BIND", str(clave)),
            ("SERVIDOR", str(datos / "servidor.json")),
            ("ejecutar", ejecutar),
            ("escribir", escribir),
        ):
            if hasattr(m, nombre):
                monkeypatch.setattr(m, nombre, valor)
    monkeypatch.setattr(
        zona.grp, "getgrnam", lambda _n: type("G", (), {"gr_gid": os.getgid()})()
    )
    return {
        "datos": datos,
        "lista": lista,
        "clave": clave,
        "ordenes": ordenes,
        "estado": estado,
    }


def test_mostrar_sin_configurar(servidor):
    salida = O.orden_cli([])
    assert salida["transferencias"] == T.defecto()
    assert salida["zonas_con_ajuste_propio"] == {}


def test_transferir_y_notificar_regenera_y_recarga(servidor):
    salida = O.orden_cli(
        ["--transferir-a", f"{DNS2},{HE}", "--notificar-a", f"{DNS2},{HE}"]
    )
    assert salida["transferencias"]["transferir_a"] == [DNS2, HE]
    texto = servidor["lista"].read_text()
    assert texto.count(f"allow-transfer {{ {DNS2}; {HE}; }};") == 2
    assert ["named-checkconf"] in servidor["ordenes"] and [
        "rndc",
        "reconfig",
    ] in servidor["ordenes"]
    assert ["rndc", "notify", "example.org"] in servidor["ordenes"]
    guardado = json.loads((servidor["datos"] / "servidor.json").read_text())
    assert guardado["ip_correo"] == SRV["ip_correo"] and guardado["transferencias"][
        "transferir_a"
    ] == [DNS2, HE]


def test_bind_rechaza_y_todo_vuelve_atras(servidor):
    O.orden_cli(["--transferir-a", DNS2])
    antes_lista = servidor["lista"].read_text()
    antes_srv = (servidor["datos"] / "servidor.json").read_text()
    servidor["estado"]["rechazar"] = True
    with pytest.raises(ErrorDns, match="BIND rechaza"):
        O.orden_cli(["--transferir-a", HE, "--tsig", "generar"])
    assert servidor["lista"].read_text() == antes_lista
    assert (servidor["datos"] / "servidor.json").read_text() == antes_srv
    assert not servidor["clave"].exists()


def test_tsig_generar_mostrar_y_quitar(servidor):
    salida = O.orden_cli(
        ["--transferir-a", DNS2, "--notificar-a", DNS2, "--tsig", "generar"]
    )
    assert "secreto" not in json.dumps(salida["transferencias"])
    assert "aviso" in salida
    secreto = T.secreto_de(servidor["clave"].read_text())
    assert secreto and secreto not in json.dumps(salida)
    assert secreto not in (servidor["datos"] / "servidor.json").read_text()
    assert 'key "transferencias-maquita"' in servidor["lista"].read_text()
    con = O.orden_cli(["--mostrar-secreto"])
    assert con["transferencias"]["tsig"]["secreto"] == secreto
    assert (
        'server 192.0.2.10 { keys { "transferencias-maquita"; }; };'
        in con["transferencias"]["tsig"]["para_el_secundario"]
    )
    O.orden_cli(["--tsig", "quitar"])
    assert not servidor["clave"].exists()
    assert (
        "key" not in servidor["lista"].read_text()
        and f"{DNS2};" in servidor["lista"].read_text()
    )


def test_quitar_transferencias_vuelve_a_lo_de_siempre(servidor):
    O.orden_cli(["--transferir-a", DNS2, "--notificar-a", DNS2])
    O.orden_cli(["--quitar-transferencias"])
    texto = servidor["lista"].read_text()
    assert (
        "allow-transfer { none; };" in texto
        and "notify no;" in texto
        and DNS2 not in texto
    )


def test_zona_propia_y_heredar(servidor):
    O.orden_cli(["--transferir-a", DNS2])
    salida = O.orden_cli(["--zona", "example.com", "--transferir-a", HE])
    assert salida["zonas_con_ajuste_propio"]["example.com"]["transferir_a"] == [HE]
    bloques = _bloques(servidor["lista"].read_text())
    assert f"allow-transfer {{ {HE}; }};" in bloques["example.com"]
    assert f"allow-transfer {{ {DNS2}; }};" in bloques["example.org"]
    salida = O.orden_cli(["--zona", "example.com", "--heredar"])
    assert salida["zonas_con_ajuste_propio"] == {}
    assert HE not in servidor["lista"].read_text()


def test_maestro_oculto_rechazado_si_el_ns_es_este_servidor(servidor):
    srv = dict(
        SRV, ns=[{"nombre": "ns1", "ip": "192.0.2.10"}, {"nombre": "ns2", "ip": HE}]
    )
    (servidor["datos"] / "servidor.json").write_text(json.dumps(srv))
    with pytest.raises(ErrorDns, match="maestro oculto"):
        O.orden_cli(
            ["--transferir-a", HE, "--notificar-a", HE, "--maestro-oculto", "si"]
        )
    assert "transferencias" not in json.loads(
        (servidor["datos"] / "servidor.json").read_text()
    )


@pytest.mark.parametrize(
    "args",
    [
        ["--algo"],
        ["--transferir-a"],
        ["--heredar"],
        ["--zona", "example.org"],
        ["--zona", "example.org", "--heredar", "--transferir-a", DNS2],
        ["--tsig", "otra"],
        ["--tsig-nombre", "xfr"],
        ["--maestro-oculto", "quizas"],
        ["--transferir-a", DNS2, "--transferir-a", HE],
    ],
)
def test_opciones_rechazadas(servidor, args):
    with pytest.raises(ErrorDns):
        O.orden_cli(args)


def test_panel(servidor):
    salida = O.orden_panel(
        {
            "transferir_a": [DNS2],
            "notificar_a": [f"{HE}:5353"],
            "maestro_oculto": False,
            "tsig": "mantener",
        }
    )
    assert salida["transferencias"]["notificar_a"] == [f"{HE}:5353"]
    with pytest.raises(ErrorDns):
        O.orden_panel({"transferir_a": [DNS2], "tsig": "mostrar"})


# --- Importar lo que ya estaba parcheado a mano ---


def _declaracion(z, cuerpo):
    return f'zone "{z}" {{\n    type primary;\n    file "/etc/bind/zonas/db.{z}";\n{cuerpo}}};\n'


# Lo que dejaba zona.py parcheado a mano: dos zonas con secundarios y una sin ellos.
CON_SECUNDARIOS = f"    allow-transfer {{ {DNS2}; {HE}; }};\n    also-notify {{ {DNS2}; {HE} port 5353; }};\n    notify yes;\n"
PARCHEADO = (
    "// Generado por el panel (Zonas DNS). No editar a mano.\n"
    + _declaracion("example.org", CON_SECUNDARIOS)
    + _declaracion("example.net", CON_SECUNDARIOS)
    + _declaracion("example.com", "    allow-transfer { none; };\n    notify no;\n")
)


def test_importar_sin_nada_que_importar(servidor):
    servidor["lista"].write_text(
        T.texto_lista([("example.org", None)], T.defecto(), _ruta, "k")
    )
    assert I.importar(simular=True)["estado"] == "sin-cambios"


def test_importar_lo_parcheado(servidor):
    servidor["lista"].write_text(PARCHEADO)
    simulado = I.importar(simular=True)
    assert simulado["estado"] == "pendiente" and simulado["global"]["transferir_a"] == [
        DNS2,
        HE,
    ]
    assert simulado["global"]["notificar_a"] == [DNS2, f"{HE}:5353"]
    assert simulado["zonas_con_ajuste_propio"] == ["example.com"]
    assert servidor["lista"].read_text() == PARCHEADO
    assert "transferencias" not in json.loads(
        (servidor["datos"] / "servidor.json").read_text()
    )
    assert I.importar()["estado"] == "listo"
    bloques = _bloques(servidor["lista"].read_text())
    assert f"also-notify {{ {DNS2}; {HE} port 5353; }};" in bloques["example.org"]
    assert (
        "allow-transfer { none; };" in bloques["example.com"]
        and "notify no;" in bloques["example.com"]
    )
    assert I.importar(simular=True)["estado"] == "sin-cambios"


def test_importar_con_clave_pide_revisar(servidor):
    servidor["lista"].write_text(PARCHEADO.replace(f"{DNS2}; {HE}; }}", 'key "xfr"; }'))
    assert I.importar(simular=True)["estado"] == "revisar"


def test_guardar_servidor_conserva_transferencias(servidor, monkeypatch):
    import importlib.machinery
    import importlib.util

    O.orden_cli(["--transferir-a", DNS2])
    ruta = os.path.join(
        os.path.dirname(__file__), "..", "..", "deploy", "dns", "maquita-dns"
    )
    cargador = importlib.machinery.SourceFileLoader("maquita_dns_cli", ruta)
    md = importlib.util.module_from_spec(
        importlib.util.spec_from_loader("maquita_dns_cli", cargador)
    )
    cargador.exec_module(md)
    monkeypatch.setattr(md, "SERVIDOR", str(servidor["datos"] / "servidor.json"))
    monkeypatch.setattr(zona, "cambiar_ips", lambda _a, _s: [])
    salida = md.guardar_servidor({"ip_correo": "192.0.2.10", "ns": SRV["ns"]})
    assert "transferencias" not in salida
    guardado = json.loads((servidor["datos"] / "servidor.json").read_text())
    assert guardado["transferencias"]["transferir_a"] == [DNS2]
