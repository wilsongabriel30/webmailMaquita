"""v1.11: cortafuegos de aplicaciones web por sitio (OWASP CRS: modo, paranoia, exclusiones y visor de bloqueos) y
claves SSH de las cuentas SFTP. Mismo mundo sin root que test_sitios_funciones_web.py."""

import os
import subprocess

import pytest

from tests.test_sitios_funciones_web import (  # noqa: F401  (fijaciones)
    DOMINIO, NGINX_MAL, _PROPIOS, _b64, _modulos_de_sitios, entorno,
)

comun, nginx_web, sitio, waf_sitio, waf_bloqueos, claves_ssh, od = (_PROPIOS[n] for n in (
    "comun", "nginx_web", "sitio", "waf_sitio", "waf_bloqueos", "claves_ssh", "ordenes_desarrollo"))
ErrorSitio = comun.ErrorSitio


def _vhost(entorno):
    return (entorno / "disp" / f"sitio-{DOMINIO}.conf").read_text()


def _reglas(entorno):
    return (entorno / "waf" / f"{DOMINIO}.conf").read_text()


# --- Cortafuegos de aplicaciones web ---


def test_de_serie_bloquea_con_crs_completo_y_las_reglas_de_wordpress(entorno):
    vhost = _vhost(entorno)
    assert "modsecurity on;" in vhost
    assert f"modsecurity_rules_file {entorno}/waf/{DOMINIO}.conf;" in vhost
    reglas = _reglas(entorno).splitlines()
    assert reglas[1:5] == ["Include /etc/nginx/sitios-waf/base.conf", "SecRuleEngine On",
                           f"SecAuditLog {entorno}/waf-registros/{DOMINIO}.log", "Include /etc/modsecurity/crs/crs-setup.conf"]
    # Las excepciones de WordPress de siempre, antes de las reglas de CRS completas.
    perfil = reglas.index("Include /etc/nginx/sitios-waf/perfil-wordpress.conf")
    assert perfil < reglas.index("Include /usr/share/modsecurity-crs/rules/*.conf")
    assert "paranoia" not in _reglas(entorno)
    assert (entorno / "waf-registros" / f"{DOMINIO}.log").exists()


def test_el_perfil_de_wordpress_sigue_con_su_excepcion():
    raiz = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "deploy", "sitios", "nginx")
    with open(os.path.join(raiz, "waf-perfil-wordpress.conf")) as f:
        assert "setvar:tx.crs_exclusions_wordpress=1" in f.read()
    with open(os.path.join(raiz, "waf-wordpress.conf")) as f:
        assert "Include /etc/nginx/sitios-waf/perfil-wordpress.conf" in f.read()
    for perfil in waf_sitio.PERFILES:
        assert os.path.exists(os.path.join(raiz, f"waf-perfil-{perfil}.conf"))


def test_detectar_paranoia_2_y_exclusiones(entorno):
    od.despachar(["waf-guardar", DOMINIO, _b64({"modo": "detectar", "paranoia": 2, "exclusiones": [
        {"regla": 942100}, {"regla": 941100, "ruta": "/wp-admin/admin-ajax.php"}]})])
    reglas = _reglas(entorno).splitlines()
    assert "SecRuleEngine DetectionOnly" in reglas
    paranoia = next(i for i, l in enumerate(reglas) if "tx.paranoia_level=2" in l)
    assert reglas.index("Include /etc/modsecurity/crs/crs-setup.conf") < paranoia < reglas.index(
        "Include /usr/share/modsecurity-crs/rules/*.conf")
    por_ruta = next(i for i, l in enumerate(reglas) if "ctl:ruleRemoveById=941100" in l)
    assert '"@beginsWith /wp-admin/admin-ajax.php"' in reglas[por_ruta]
    assert por_ruta < reglas.index("Include /usr/share/modsecurity-crs/rules/*.conf")
    assert reglas[-1] == "SecRuleRemoveById 942100"
    estado = od.despachar(["waf", DOMINIO])
    assert estado["modo"] == "detectar" and estado["paranoia"] == 2 and len(estado["exclusiones"]) == 2


def test_apagado_quita_modsecurity_del_sitio(entorno):
    waf_sitio.guardar(DOMINIO, {"modo": "apagado"})
    assert "modsecurity off;" in _vhost(entorno) and "modsecurity_rules_file" not in _vhost(entorno)
    assert not (entorno / "waf" / f"{DOMINIO}.conf").exists()
    waf_sitio.guardar(DOMINIO, {"modo": "bloquear", "paranoia": 1, "exclusiones": []})
    assert "SecRuleEngine On" in _reglas(entorno)
    assert "waf" not in (comun.leer_meta(DOMINIO).get("web") or {})  # los de serie no se guardan


@pytest.mark.parametrize("datos", [
    {"modo": "apagar"}, {"modo": "bloquear", "paranoia": 3}, {"paranoia": True}, {"paranoia": "2"},
    {"exclusiones": [{"regla": "942100"}]}, {"exclusiones": [{"regla": 42}]}, {"exclusiones": [{"regla": 1234567}]},
    {"exclusiones": [{"regla": 949110}]}, {"exclusiones": [{"regla": 980130}]}, {"exclusiones": [{"regla": 901001}]},
    {"exclusiones": [{"regla": True}]}, {"exclusiones": [{"regla": 942100, "otra": 1}]},
    {"exclusiones": [{"regla": 942100}] * 51}, {"nginx": "x"}, ["bloquear"],
])
def test_ajustes_no_validos(entorno, datos):
    antes = _reglas(entorno)
    with pytest.raises(ErrorSitio):
        waf_sitio.guardar(DOMINIO, datos)
    assert _reglas(entorno) == antes


@pytest.mark.parametrize("ruta", ['/a" "id:1,phase:1,allow', "/a;", "/a b", "a", "/a\nSecRuleEngine Off", "/../etc",
                                  "/a//b", "/á", "/a$b", "/a{b}", "/" + "a" * 250])
def test_ruta_de_exclusion_con_inyeccion(entorno, ruta):
    with pytest.raises(ErrorSitio):
        waf_sitio.guardar(DOMINIO, {"exclusiones": [{"regla": 942100, "ruta": ruta}]})
    assert "942100" not in _reglas(entorno)


def test_si_nginx_rechaza_vuelve_todo_atras(entorno, monkeypatch):
    antes, vhost = _reglas(entorno), _vhost(entorno)
    monkeypatch.setattr(nginx_web, "NGINX_PRUEBA", NGINX_MAL)
    with pytest.raises(ErrorSitio, match="nginx rechazó"):
        waf_sitio.guardar(DOMINIO, {"modo": "detectar"})
    assert _reglas(entorno) == antes and _vhost(entorno) == vhost
    assert "waf" not in (comun.leer_meta(DOMINIO).get("web") or {})


def test_baja_del_sitio_quita_reglas_y_registro(entorno):
    waf_sitio.quitar(DOMINIO)
    assert not (entorno / "waf" / f"{DOMINIO}.conf").exists()
    assert not (entorno / "waf-registros" / f"{DOMINIO}.log").exists()


SERIAL = """---AbC123xY---A--
[21/Oct/2026:10:00:00 +0000] 169788 192.0.2.50 54321 198.51.100.1 443
---AbC123xY---B--
GET /buscar?q=1%27+OR+1=1&clave=secreta HTTP/1.1
Host: example.org
---AbC123xY---F--
HTTP/1.1 403
---AbC123xY---H--
ModSecurity: Warning. detected SQLi using libinjection. [file "x"] [line "1"] [id "942100"] [rev ""] [msg "SQL Injection Attack Detected via libinjection"] [data "Matched Data: s&1 found within ARGS:q: 1' OR 1=1"] [severity "2"]
ModSecurity: Access denied with code 403 (phase 2). [file "x"] [id "949110"] [msg "Inbound Anomaly Score Exceeded (Total Score: 5)"]
---AbC123xY---Z--

---Zz99Zz99---A--
[21/Oct/2026:10:05:00 +0000] 169789 203.0.113.9 5555 198.51.100.1 443
---Zz99Zz99---B--
POST /wp-admin/admin-ajax.php HTTP/1.1
---Zz99Zz99---F--
HTTP/1.1 200
---Zz99Zz99---H--
ModSecurity: Warning. Matched [id "941100"] [msg "XSS Attack Detected via libinjection"]
---Zz99Zz99---Z--
"""


def test_visor_de_bloqueos_formato_serial(entorno):
    with open(waf_sitio.registro(DOMINIO), "w") as f:
        f.write("restos de una transacción cortada\n---Cortada1---H--\n[id \"920000\"]\n---Cortada1---Z--\n" + SERIAL)
    r = od.despachar(["waf-bloqueos", DOMINIO, "10"])
    assert [s["ip"] for s in r["sucesos"]] == ["203.0.113.9", "192.0.2.50"]  # el más reciente primero
    ultimo, bloqueo = r["sucesos"]
    assert ultimo["accion"] == "detectado" and ultimo["reglas"] == [{"id": 941100, "mensaje": "XSS Attack Detected via libinjection"}]
    assert bloqueo["accion"] == "bloqueado" and bloqueo["codigo"] == 403 and bloqueo["metodo"] == "GET"
    assert bloqueo["ruta"] == "/buscar"  # sin la consulta: puede llevar contraseñas o datos personales
    assert [x["id"] for x in bloqueo["reglas"]] == [942100]  # sin la regla de puntuación
    assert "secreta" not in str(r) and "Matched Data" not in str(r)


def test_visor_de_bloqueos_formato_json(entorno):
    linea = ('{"transaction":{"client_ip":"198.51.100.20","time_stamp":"Tue Oct 21 10:00:00 2026",'
             '"request":{"method":"GET","uri":"/x.php?id=1"},"response":{"http_code":403},'
             '"messages":[{"message":"SQL Injection","details":{"ruleId":"942100"}}]}}\n')
    with open(waf_sitio.registro(DOMINIO), "w") as f:
        f.write(linea + "no es json\n")
    suceso = waf_bloqueos.ultimos(DOMINIO)["sucesos"][0]
    assert suceso["ip"] == "198.51.100.20" and suceso["ruta"] == "/x.php" and suceso["accion"] == "bloqueado"
    assert suceso["reglas"][0]["id"] == 942100


def test_visor_sin_registro(entorno):
    os.remove(waf_sitio.registro(DOMINIO))
    assert waf_bloqueos.ultimos(DOMINIO)["sucesos"] == []


# --- Claves SSH ---


def _clave(tmp_path, tipo, bits=None, comentario="ana@example.org"):
    ruta = tmp_path / f"clave-{tipo}-{bits}"
    orden = ["ssh-keygen", "-q", "-t", tipo, "-N", "", "-C", comentario, "-f", str(ruta)] + (["-b", str(bits)] if bits else [])
    subprocess.run(orden, check=True)
    return (tmp_path / f"clave-{tipo}-{bits}.pub").read_text().strip()


@pytest.fixture
def cuentas(entorno):
    meta = comun.leer_meta(DOMINIO)
    meta["ftp"] = True
    meta["ftp_cuentas"] = [{"nombre": "disenio", "usuario": "disenio_example1234", "carpeta": "imagenes"}]
    comun.guardar_meta(meta)
    return entorno


def test_claves_aceptadas_y_archivo_con_restrict(cuentas, tmp_path):
    ed = _clave(tmp_path, "ed25519")
    r = od.despachar(["ssh-clave-agregar", DOMINIO, "principal", _b64(ed)])
    assert r["agregada"]["tipo"] == "ssh-ed25519" and r["agregada"]["huella"].startswith("SHA256:")
    claves_ssh.agregar(DOMINIO, "disenio", _clave(tmp_path, "ecdsa", 256))
    claves_ssh.agregar(DOMINIO, "principal", _clave(tmp_path, "rsa", 3072))
    archivo = (cuentas / "claves-ssh" / "webexample1234").read_text().splitlines()
    assert len(archivo) == 2 and all(l.startswith("restrict ") for l in archivo)
    assert archivo[0] == "restrict " + ed
    assert (cuentas / "claves-ssh" / "disenio_example1234").read_text().startswith("restrict ecdsa-sha2-nistp256 ")


def test_rsa_debil_rechazada(cuentas, tmp_path):
    with pytest.raises(ErrorSitio, match="débil"):
        claves_ssh.agregar(DOMINIO, "principal", _clave(tmp_path, "rsa", 2048))
    assert not (cuentas / "claves-ssh" / "webexample1234").exists()


@pytest.mark.parametrize("cambio", [
    lambda c: 'command="/bin/sh" ' + c,                 # opciones delante: no se aceptan
    lambda c: "restrict " + c,
    lambda c: c + "\nssh-ed25519 AAAA otra",            # dos claves
    lambda c: c.replace("ssh-ed25519", "ssh-rsa"),      # tipo declarado distinto del de dentro
    lambda c: c.replace("ssh-ed25519", "ssh-dss"),
    lambda c: c.split()[0] + " " + c.split()[1][:30],   # incompleta
    lambda c: c.split()[0] + " " + c.split()[1][:-4] + "@@@@",
    lambda c: "-----BEGIN OPENSSH PRIVATE KEY-----",
    lambda c: "",
])
def test_claves_raras_rechazadas(cuentas, tmp_path, cambio):
    with pytest.raises(ErrorSitio):
        claves_ssh.agregar(DOMINIO, "principal", cambio(_clave(tmp_path, "ed25519")))
    assert comun.leer_meta(DOMINIO).get("claves_ssh") in (None, [])


def test_comentario_raro_se_descarta(cuentas, tmp_path):
    ed = _clave(tmp_path, "ed25519")
    tipo, datos = ed.split()[:2]
    claves_ssh.agregar(DOMINIO, "principal", f"{tipo} {datos} $(reboot) \\ ;")
    assert (cuentas / "claves-ssh" / "webexample1234").read_text() == f"restrict {tipo} {datos}\n"


def test_repetida_cuenta_ajena_y_borrar(cuentas, tmp_path):
    ed = _clave(tmp_path, "ed25519")
    r = claves_ssh.agregar(DOMINIO, "principal", ed)
    with pytest.raises(ErrorSitio, match="ya está"):
        claves_ssh.agregar(DOMINIO, "principal", ed)
    with pytest.raises(ErrorSitio, match="no es de este sitio"):
        claves_ssh.agregar(DOMINIO, "otra", ed)
    with pytest.raises(ErrorSitio):
        claves_ssh.borrar(DOMINIO, "../../x")
    claves_ssh.borrar(DOMINIO, r["agregada"]["id"])
    assert not (cuentas / "claves-ssh" / "webexample1234").exists()


def test_sin_acceso_activado_la_clave_no_vale(cuentas, tmp_path):
    claves_ssh.agregar(DOMINIO, "principal", _clave(tmp_path, "ed25519"))
    meta = comun.leer_meta(DOMINIO)
    meta["ftp"] = False
    claves_ssh.sincronizar(meta)
    assert not (cuentas / "claves-ssh" / "webexample1234").exists()
    assert claves_ssh.listar(DOMINIO)["claves"][0]["activa"] is True  # en el meta seguía activo
    meta["ftp"] = True
    claves_ssh.sincronizar(meta)
    assert (cuentas / "claves-ssh" / "webexample1234").exists()


def test_baja_de_una_cuenta_adicional_quita_sus_claves(cuentas, tmp_path):
    claves_ssh.agregar(DOMINIO, "disenio", _clave(tmp_path, "ed25519"))
    meta = comun.leer_meta(DOMINIO)
    claves_ssh.quitar_cuenta(meta, "disenio", "disenio_example1234")
    assert meta["claves_ssh"] == [] and not (cuentas / "claves-ssh" / "disenio_example1234").exists()
