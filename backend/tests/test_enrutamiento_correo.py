"""Enrutamiento de correo por dominio (v1.11): MX de respaldo y reenvío a otro servidor.

Lo que más importa aquí es que el servidor NO quede como relé abierto:
- la validación del panel no admite comodines, ni destinatarios de otro dominio, ni destinos que
  sean el propio servidor;
- las consultas de los mapas de Postfix (las mismas que se instalan) solo aceptan el dominio exacto
  y, sin lista de destinatarios, a cualquier usuario de ESE dominio y de ningún otro; se ejecutan en
  SQLite con las tablas de la migración, buscando las claves en el orden en que las busca Postfix;
- el ajuste 68 se niega a aplicar si las restricciones de Postfix no rechazan destinos ajenos.

Solo example.org / example.com y direcciones de documentación (192.0.2.x, 198.51.100.x, 203.0.113.x).
"""

import importlib.util
import os
import re
import shutil
import sqlite3
import subprocess

import pytest

RAIZ = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
MAPAS = os.path.join(RAIZ, "deploy", "webmail", "configs", "postfix-pgsql")
AJUSTE = os.path.join(RAIZ, "deploy", "ajustes", "68-enrutamiento-de-correo.sh")

_spec = importlib.util.spec_from_file_location(
    "enrutamiento_validacion", os.path.join(RAIZ, "admin-panel", "backend", "app", "enrutamiento", "validacion.py"))
v = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(v)


# --- Validación del panel ---


def reenvio(**extra):
    return {"modo": "reenvio", "destino_host": "mx.example.com", "destino_puerto": 25, **extra}


def test_respaldo_y_reenvio_validos():
    assert v.normalizar("Example.ORG.", {"modo": "respaldo"})["dominio"] == "example.org"
    c = v.normalizar("example.org", reenvio(destino_puerto="587", tls_obligatorio=True))
    assert (c["destino_host"], c["destino_puerto"], c["tls_obligatorio"]) == ("mx.example.com", 587, True)
    assert v.siguiente_salto(c) == "smtp:[mx.example.com]:587"
    assert v.normalizar("example.org", reenvio(destino_host="[198.51.100.7]"))["destino_host"] == "198.51.100.7"
    assert v.normalizar("example.org", reenvio(destino_host="2001:db8::25"))["destino_host"] == "2001:db8::25"
    assert v.normalizar("example.org", reenvio(destino_puerto=None))["destino_puerto"] == 25


@pytest.mark.parametrize("dominio", ["*", "*.example.org", ".", "example", "-example.org", "exa mple.org",
                                     "example.org/24", "example..org", "%", "example.org,example.com"])
def test_dominios_sin_comodines(dominio):
    with pytest.raises(v.ErrorEnrutamiento):
        v.normalizar(dominio, {"modo": "respaldo"})


@pytest.mark.parametrize("destino", ["", "localhost", "smtp.localhost", "127.0.0.1", "[::1]", "0.0.0.0", "::",
                                     "224.0.0.1", "169.254.1.1", "240.0.0.1", "mx.example.com:25", "mx_example.com",
                                     "correo.example.org"])
def test_destinos_rechazados(destino):
    with pytest.raises(v.ErrorEnrutamiento):
        v.normalizar("example.org", reenvio(destino_host=destino), propios={"correo.example.org"})


@pytest.mark.parametrize("puerto", [0, 65536, "25a", -1, True, "1e3"])
def test_puertos_rechazados(puerto):
    with pytest.raises(v.ErrorEnrutamiento):
        v.normalizar("example.org", reenvio(destino_puerto=puerto))


@pytest.mark.parametrize("lista", [["ana@example.com"], ["ana@sub.example.org"], ["ana@example.org.example.com"],
                                   ["@example.org"], ["ana"], ["a b@example.org"], "ana@example.org;luis@example.com"])
def test_destinatarios_solo_del_dominio_exacto(lista):
    with pytest.raises(v.ErrorEnrutamiento):
        v.normalizar("example.org", {"modo": "respaldo", "verificar_destinatarios": True, "destinatarios": lista})


def test_destinatarios_se_normalizan_y_sin_repetidos():
    c = v.normalizar("example.org", {"modo": "respaldo", "verificar_destinatarios": True,
                                     "destinatarios": "Ana@Example.org; luis@example.org,ana@example.org"})
    assert c["destinatarios"] == ["ana@example.org", "luis@example.org"]


def test_verificar_sin_lista_tls_en_respaldo_y_booleanos_estrictos():
    with pytest.raises(v.ErrorEnrutamiento, match="al menos un destinatario"):
        v.normalizar("example.org", {"modo": "respaldo", "verificar_destinatarios": True})
    with pytest.raises(v.ErrorEnrutamiento, match="TLS"):
        v.normalizar("example.org", {"modo": "respaldo", "tls_obligatorio": True})
    with pytest.raises(v.ErrorEnrutamiento):
        v.normalizar("example.org", {"modo": "respaldo", "activo": "sí"})
    with pytest.raises(v.ErrorEnrutamiento, match="Modo"):
        v.normalizar("example.org", {"modo": "relay"})


# --- Mapas de Postfix contra las tablas de la migración (SQLite) ---


def consulta(archivo):
    with open(os.path.join(MAPAS, archivo), encoding="utf-8") as f:
        return re.search(r"^query\s*=\s*(.+)$", f.read(), re.M).group(1)


@pytest.fixture
def bd():
    con = sqlite3.connect(":memory:")
    con.executescript("""
        CREATE TABLE domain (domain TEXT PRIMARY KEY, active BOOLEAN NOT NULL DEFAULT true);
        CREATE TABLE enrutamiento_correo (dominio TEXT PRIMARY KEY REFERENCES domain(domain), modo TEXT NOT NULL,
            destino_host TEXT, destino_puerto INTEGER, tls_obligatorio BOOLEAN NOT NULL DEFAULT false,
            verificar_destinatarios BOOLEAN NOT NULL DEFAULT false, activo BOOLEAN NOT NULL DEFAULT true);
        CREATE TABLE enrutamiento_destinatarios (direccion TEXT PRIMARY KEY, dominio TEXT NOT NULL);
        INSERT INTO domain VALUES ('example.org', true), ('example.com', true), ('local.example.org', true),
                                  ('apagado.example.com', false), ('pausado.example.com', true);
        INSERT INTO enrutamiento_correo (dominio, modo) VALUES ('example.org', 'respaldo');
        INSERT INTO enrutamiento_correo VALUES ('example.com', 'reenvio', 'mx.example.com', 2525, true, true, true);
        INSERT INTO enrutamiento_correo (dominio, modo) VALUES ('apagado.example.com', 'respaldo');
        INSERT INTO enrutamiento_correo (dominio, modo, activo) VALUES ('pausado.example.com', 'respaldo', false);
        INSERT INTO enrutamiento_destinatarios VALUES ('ventas@example.com', 'example.com');
    """)
    return con


def buscar(con, archivo, clave):
    # Postfix escapa la clave antes de sustituir %s; aquí todas son direcciones simples sin comillas.
    assert "'" not in clave
    filas = con.execute(consulta(archivo).replace("%s", clave)).fetchall()
    return filas[0][0] if filas else None


def acepta_sin_autenticar(con, direccion):
    """Lo que haría Postfix con un cliente de Internet: relay_domains con el dominio, después
    relay_recipient_maps con «usuario@dominio» y luego «@dominio» (y nunca otro dominio)."""
    direccion = direccion.lower()
    dominio = direccion.rsplit("@", 1)[1]
    if buscar(con, "pgsql-virtual-domains.cf", dominio):
        return "local"
    if not buscar(con, "pgsql-enrutamiento-dominios.cf", dominio):
        return None
    if buscar(con, "pgsql-enrutamiento-destinatarios.cf", direccion) or \
       buscar(con, "pgsql-enrutamiento-destinatarios.cf", "@" + dominio):
        return "relé"
    return None


def test_mx_de_respaldo_acepta_su_dominio_y_nada_mas(bd):
    assert acepta_sin_autenticar(bd, "cualquiera@example.org") == "relé"
    assert acepta_sin_autenticar(bd, "Ana@EXAMPLE.ORG") == "relé"
    assert buscar(bd, "pgsql-enrutamiento-transporte.cf", "example.org") is None  # sigue al MX principal


@pytest.mark.parametrize("direccion", [
    "ana@sub.example.org", "ana@example.org.example.com", "ana@example.net", "ana@org", "ana@xample.org",
    "otro@example.com", "ana@apagado.example.com",
])
def test_no_es_un_rele_abierto(bd, direccion):
    assert acepta_sin_autenticar(bd, direccion) is None


def test_enrutamiento_en_pausa_vuelve_a_los_buzones_locales(bd):
    assert acepta_sin_autenticar(bd, "ana@pausado.example.com") == "local"
    assert buscar(bd, "pgsql-enrutamiento-dominios.cf", "pausado.example.com") is None


def test_con_verificacion_solo_la_lista(bd):
    assert acepta_sin_autenticar(bd, "ventas@example.com") == "relé"
    assert buscar(bd, "pgsql-enrutamiento-destinatarios.cf", "@example.com") is None
    assert buscar(bd, "pgsql-enrutamiento-destinatarios.cf", "ventas@example.org") is None


def test_comodin_de_dominio_solo_si_no_hay_verificacion(bd):
    assert buscar(bd, "pgsql-enrutamiento-destinatarios.cf", "@example.org") == "OK"
    bd.execute("UPDATE enrutamiento_correo SET verificar_destinatarios = true WHERE dominio = 'example.org'")
    assert acepta_sin_autenticar(bd, "cualquiera@example.org") is None


def test_reenvio_transporte_y_tls(bd):
    config = v.normalizar("example.com", reenvio(destino_puerto=2525, tls_obligatorio=True,
                                                  verificar_destinatarios=True, destinatarios=["ventas@example.com"]))
    assert buscar(bd, "pgsql-enrutamiento-transporte.cf", "example.com") == v.siguiente_salto(config)
    assert buscar(bd, "pgsql-enrutamiento-tls.cf", "[mx.example.com]:2525") == "encrypt"
    assert buscar(bd, "pgsql-enrutamiento-tls.cf", "[mx.example.com]:25") is None
    bd.execute("UPDATE enrutamiento_correo SET tls_obligatorio = false WHERE dominio = 'example.com'")
    assert buscar(bd, "pgsql-enrutamiento-tls.cf", "[mx.example.com]:2525") is None


def test_dominio_enrutado_sale_de_los_buzones_locales(bd):
    assert buscar(bd, "pgsql-virtual-domains.cf", "local.example.org") == "local.example.org"
    assert buscar(bd, "pgsql-virtual-domains.cf", "example.org") is None
    assert buscar(bd, "pgsql-virtual-domains.cf", "pausado.example.com") == "pausado.example.com"
    assert acepta_sin_autenticar(bd, "ana@local.example.org") == "local"


def test_la_migracion_crea_lo_que_leen_los_mapas():
    with open(os.path.join(RAIZ, "migrations", "2026-10-21-enrutamiento-correo.sql"), encoding="utf-8") as f:
        sql = f.read()
    for tabla in ("enrutamiento_correo", "enrutamiento_destinatarios"):
        assert f"CREATE TABLE IF NOT EXISTS {tabla}" in sql
    for columna in ("modo", "destino_host", "destino_puerto", "tls_obligatorio", "verificar_destinatarios", "activo"):
        assert columna in sql


def test_instalador_y_ajuste_usan_los_mismos_mapas():
    with open(os.path.join(RAIZ, "deploy", "webmail", "instalar.sh"), encoding="utf-8") as f:
        instalar = f.read()
    with open(AJUSTE, encoding="utf-8") as f:
        ajuste = f.read()
    for parametro, mapa in [("relay_domains", "dominios"), ("relay_recipient_maps", "destinatarios"),
                            ("transport_maps", "transporte"), ("smtp_tls_policy_maps", "tls")]:
        assert f'"{parametro} = pgsql:/etc/postfix/pgsql/pgsql-enrutamiento-{mapa}.cf"' in instalar
        assert f"{parametro}:pgsql-enrutamiento-{mapa}.cf" in ajuste
        assert os.path.exists(os.path.join(MAPAS, f"pgsql-enrutamiento-{mapa}.cf"))


# --- Ajuste 68 sobre una configuración de Postfix de prueba ---

necesita_postconf = pytest.mark.skipif(not shutil.which("postconf"), reason="sin postconf en este equipo")
CONSULTA_DOMINIOS = "query = SELECT domain FROM domain WHERE domain='%s' AND active = true"


@pytest.fixture
def postfix(tmp_path):
    (tmp_path / "master.cf").write_text("")
    (tmp_path / "pgsql").mkdir()
    (tmp_path / "pgsql" / "dominios.cf").write_text(
        f"hosts = localhost\nuser = mailserver\npassword = clave-de-prueba\ndbname = maildb\n{CONSULTA_DOMINIOS}\n")
    (tmp_path / "main.cf").write_text(
        f"compatibility_level = 3.6\nvirtual_mailbox_domains = pgsql:{tmp_path}/pgsql/dominios.cf\n"
        "mynetworks = 127.0.0.0/8 [::1]/128\n")
    return tmp_path


def correr(conf, *args):
    return subprocess.run(["bash", AJUSTE, *args], capture_output=True, text=True,
                          env={**os.environ, "POSTFIX_CONF": str(conf)}, timeout=60)


def parametro(conf, nombre):
    return subprocess.run(["postconf", "-c", str(conf), "-nh", nombre], capture_output=True, text=True).stdout.strip()


@necesita_postconf
def test_ajuste_simular_no_toca_nada(postfix):
    antes = (postfix / "main.cf").read_text()
    r = correr(postfix, "--simular")
    assert r.returncode == 0, r.stderr
    assert "Pendiente:" in r.stdout and "relay_domains" in r.stdout
    assert (postfix / "main.cf").read_text() == antes
    assert not (postfix / "pgsql" / "pgsql-enrutamiento-dominios.cf").exists()


@necesita_postconf
def test_ajuste_aplica_respalda_y_es_idempotente(postfix):
    (postfix / "main.cf").write_text((postfix / "main.cf").read_text() + "transport_maps = hash:/etc/postfix/transport\n")
    r = correr(postfix)
    assert r.returncode == 0, r.stderr
    assert "Listo:" in r.stdout
    pg = postfix / "pgsql"
    assert parametro(postfix, "relay_domains") == f"pgsql:{pg}/pgsql-enrutamiento-dominios.cf"
    assert parametro(postfix, "relay_recipient_maps") == f"pgsql:{pg}/pgsql-enrutamiento-destinatarios.cf"
    assert parametro(postfix, "transport_maps") == f"pgsql:{pg}/pgsql-enrutamiento-transporte.cf, hash:/etc/postfix/transport"
    assert parametro(postfix, "smtp_tls_policy_maps") == f"pgsql:{pg}/pgsql-enrutamiento-tls.cf"
    instalado = (pg / "pgsql-enrutamiento-destinatarios.cf").read_text()
    assert "password = clave-de-prueba" in instalado and "__DB_PASS__" not in instalado
    assert consulta("pgsql-enrutamiento-destinatarios.cf") in instalado
    dominios = (pg / "dominios.cf").read_text()
    assert dominios.count("enrutamiento_correo") == 1 and CONSULTA_DOMINIOS + " AND NOT EXISTS" in dominios
    assert list(postfix.glob("main.cf.bak.*")) and list(pg.glob("dominios.cf.bak.*"))
    r = correr(postfix, "--simular")
    assert r.returncode == 0 and r.stdout.startswith("Sin cambios"), r.stdout


@necesita_postconf
@pytest.mark.parametrize("linea", [
    "smtpd_relay_restrictions = permit",
    "smtpd_relay_restrictions = permit_mynetworks, permit",
    "smtpd_relay_restrictions = permit_mynetworks, permit, reject_unauth_destination",
    "mynetworks = 0.0.0.0/0",
    "mynetworks = 127.0.0.0/8, [::]/0",
])
def test_ajuste_no_se_aplica_si_quedaria_un_rele_abierto(postfix, linea):
    (postfix / "main.cf").write_text((postfix / "main.cf").read_text() + linea + "\n")
    antes = (postfix / "main.cf").read_text()
    for args in ((), ("--simular",)):
        r = correr(postfix, *args)
        assert r.returncode == 1 and "No se aplica" in r.stderr
    assert (postfix / "main.cf").read_text() == antes


@necesita_postconf
def test_ajuste_no_reescribe_una_consulta_de_dominios_rara(postfix):
    rara = CONSULTA_DOMINIOS + " ORDER BY domain"
    (postfix / "pgsql" / "dominios.cf").write_text(f"hosts = localhost\n{rara}\n")
    r = correr(postfix)
    assert r.returncode == 1 and "a mano" in r.stderr
    assert (postfix / "pgsql" / "dominios.cf").read_text() == f"hosts = localhost\n{rara}\n"


@necesita_postconf
def test_ajuste_sin_mapas_pgsql_no_hace_nada(tmp_path):
    (tmp_path / "master.cf").write_text("")
    (tmp_path / "main.cf").write_text("virtual_mailbox_domains = example.org\n")
    r = correr(tmp_path)
    assert r.returncode == 0 and r.stdout.startswith("Sin cambios")
