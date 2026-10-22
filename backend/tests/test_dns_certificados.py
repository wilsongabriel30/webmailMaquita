"""Certificado del correo (deploy/dns/lib/certificado*.py): servidor que no se llama mail.<dominio>,
avisos de configuración sin dejar el temporizador en «failed» y certificado propio por dominio (SNI).

Sin root ni red: certbot, openssl, postconf, nginx, postmap, doveconf y systemctl se simulan, y las
rutas de /etc van a una carpeta temporal.
"""

import os
import re
import sys

import pytest

RAIZ = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")
sys.path.insert(0, os.path.join(RAIZ, "deploy", "dns", "lib"))
certificado = pytest.importorskip("certificado")
import certificado_base as B  # noqa: E402
import certificado_dominios as D  # noqa: E402
import certificado_espera as E  # noqa: E402
import certificado_sni as S  # noqa: E402
import certificado_sni_nginx as N  # noqa: E402
import zona  # noqa: E402
from comun import ErrorDns  # noqa: E402

IP = "203.0.113.10"


class Sistema:
    """Simula los programas que llama el ayudante y guarda cada orden."""

    def __init__(self, raiz, host):
        self.raiz, self.host = raiz, host
        self.ordenes = []
        self.postconf = {"myhostname": host, "tls_server_sni_maps": "", "smtpd_tls_cert_file": "/etc/ssl/certs/ssl-cert-snakeoil.pem"}
        self.fallan = set()  # «nginx», «postfix», «doveconf» o el linaje de certbot que debe fallar
        self.dovecot = "2.4.1 (prueba)"

    def certbot(self, cmd):
        linaje = cmd[cmd.index("--cert-name") + 1]
        if linaje in self.fallan:
            raise ErrorDns("certbot: Some challenges have failed.")
        nombres = [cmd[i + 1] for i, a in enumerate(cmd) if a == "-d"]
        crear_linaje(self.raiz, linaje, nombres)
        return ""

    def __call__(self, cmd, entrada=None, tiempo=120):
        self.ordenes.append(list(cmd))
        prog = cmd[0]
        if prog == "postconf":
            if cmd[1] == "-h":
                return self.postconf.get(cmd[2], "") + "\n"
            if cmd[1] == "-e":
                for par in cmd[2:]:
                    k, v = par.split("=", 1)
                    self.postconf[k] = v
            if cmd[1] == "-X":
                self.postconf[cmd[2]] = ""
            return ""
        if prog == "certbot":
            return self.certbot(cmd)
        if prog == "openssl":
            with open(cmd[cmd.index("-in") + 1]) as f:
                nombres = f.read().split()
            return "notAfter=Jan 20 00:00:00 2027 GMT\nX509v3 Subject Alternative Name:\n    " + \
                ", ".join(f"DNS:{n}" for n in nombres) + "\n"
        if prog == "nginx" and "nginx" in self.fallan:
            raise ErrorDns("nginx: [emerg] prueba")
        if prog == "postfix" and "postfix" in self.fallan:
            raise ErrorDns("postfix: fatal: prueba")
        if prog == "doveconf" and "doveconf" in self.fallan:
            raise ErrorDns("doveconf: Fatal: prueba")
        if prog == "dovecot":
            return self.dovecot + "\n"
        if prog == "postmap":
            open(cmd[-1].split(":", 1)[1] + ".db", "w").close()
        return ""

    def de(self, prog):
        return [c for c in self.ordenes if c[0] == prog]


def crear_linaje(raiz, linaje, nombres):
    vivo = os.path.join(raiz, "live", linaje)
    os.makedirs(vivo, exist_ok=True)
    for archivo in ("cert.pem", "fullchain.pem", "privkey.pem"):
        with open(os.path.join(vivo, archivo), "w") as f:
            f.write(" ".join(nombres) + "\n")


def _plantillas(raiz, host):
    """Los vhosts reales del repositorio, como los deja la instalación."""
    disp = os.path.join(raiz, "sites-available")
    os.makedirs(disp, exist_ok=True)
    with open(os.path.join(RAIZ, "deploy", "webmail", "nginx", "webmail.conf")) as f:
        texto = f.read().replace("mail.tudominio.com", host).replace("tudominio.com", "example.org")
    with open(os.path.join(disp, host), "w") as f:
        f.write(texto)
    with open(os.path.join(RAIZ, "deploy", "webmail", "nginx", "autodiscover-dominios.conf")) as f:
        texto = f.read().replace("mail.tudominio.com", host).replace("tudominio.com", "example.org")
    with open(os.path.join(disp, "autodiscover-dominios"), "w") as f:
        f.write(texto)
    with open(os.path.join(RAIZ, "panel-dominio", "deploy", "nginx-panel-dominio.conf")) as f:
        texto = f.read().replace("correo.ejemplo.org", host)
    with open(os.path.join(disp, "panel-dominio"), "w") as f:
        f.write(texto)


@pytest.fixture
def entorno(tmp_path, monkeypatch):
    def preparar(host="hosting.example.org", zonas=("example.org", "example.com"), org="", resuelven=()):
        raiz = str(tmp_path)
        sistema = Sistema(raiz, host)
        for modulo in (certificado, B, S):
            monkeypatch.setattr(modulo, "ejecutar", sistema)
        monkeypatch.setattr(S.subprocess, "run", lambda *a, **k: None)
        monkeypatch.setattr(B, "LIVE", os.path.join(raiz, "live"))
        monkeypatch.setattr(B, "WEBROOT", os.path.join(raiz, "certbot"))
        monkeypatch.setattr(N, "DISPONIBLES", os.path.join(raiz, "sites-available"))
        monkeypatch.setattr(N, "ACTIVOS", os.path.join(raiz, "sites-enabled"))
        monkeypatch.setattr(D, "SITIOS_ACTIVOS", os.path.join(raiz, "sites-enabled"))
        monkeypatch.setattr(certificado, "SITIOS", os.path.join(raiz, "sites-available"))
        snippet = os.path.join(raiz, "snippets", "correo-nombres.conf")
        os.makedirs(os.path.dirname(snippet))
        monkeypatch.setattr(certificado, "NOMBRES_NGINX", snippet)
        monkeypatch.setattr(N, "NOMBRES_NGINX", snippet)
        monkeypatch.setattr(S, "MAPA", os.path.join(raiz, "postfix", "sni-correo"))
        monkeypatch.setattr(S, "GANCHO", os.path.join(raiz, "hooks", "sni-correo.sh"))
        monkeypatch.setattr(S, "DOVECOT_DIR", os.path.join(raiz, "dovecot"))
        monkeypatch.setattr(S, "RESPALDOS_NGINX", os.path.join(raiz, "respaldos"))
        os.makedirs(os.path.join(raiz, "sites-enabled"))
        os.makedirs(os.path.join(raiz, "dovecot", "maquita.d"))
        with open(os.path.join(raiz, "dovecot", "dovecot.conf"), "w") as f:
            f.write("ssl = yes\n!include_try /etc/dovecot/maquita.d/*.conf\n")
        monkeypatch.setenv("ORG_FICHERO", os.path.join(raiz, "organizacion.env"))
        with open(os.path.join(raiz, "organizacion.env"), "w") as f:
            f.write(org)
        monkeypatch.setenv("MAQUITA_CERTIFICADOS_ESTADO", os.path.join(raiz, "estado", "certificados.json"))
        monkeypatch.setattr(zona, "listar", lambda: [{"zona": z} for z in zonas])
        monkeypatch.setattr(certificado, "servidor", lambda: {"ip_correo": IP})
        monkeypatch.setattr(certificado, "_ip_publica", lambda ip: True)  # IP de documentación (RFC 5737)
        apuntan = set(resuelven)
        monkeypatch.setattr(B, "apunta", lambda nombre, ip: nombre in apuntan)
        usados = []
        monkeypatch.setattr(certificado, "_usar_en_servicios", lambda h: usados.append(h))
        sistema.apuntan, sistema.usados = apuntan, usados
        _plantillas(raiz, host)
        return sistema

    return preparar


def _certbots(sistema, linaje):
    return [c for c in sistema.de("certbot") if c[c.index("--cert-name") + 1] == linaje]


def _leer(ruta):
    with open(ruta) as f:
        return f.read()


# --- 1. Servidor que no se llama mail.<dominio> -----------------------------------------------------


def test_servidor_hosting_es_el_linaje_y_el_dominio_sale_de_la_zona(entorno):
    s = entorno(resuelven={"hosting.example.org", "mail.example.org", "mail.example.com"})
    assert B.principal() == ("hosting.example.org", "example.org")
    r = certificado.automatico()
    assert r["accion"] == "emitido"
    (orden,) = _certbots(s, "hosting.example.org")
    assert orden[orden.index("-m") + 1] == "postmaster@example.org"
    nombres = [orden[i + 1] for i, a in enumerate(orden) if a == "-d"]
    assert nombres[0] == "hosting.example.org" and "mail.example.com" in nombres  # modo compartido: lo de siempre


def test_dominio_principal_de_organizacion_env(entorno):
    entorno(org='ORG_DOMINIO="example.com"\n')
    assert B.principal() == ("hosting.example.org", "example.com")
    # mail.<dominio> manda siempre: a quien ya funcionaba no le cambia nada.
    assert B.dominio_principal("mail.example.org") == "example.org"


def test_dominio_principal_sin_zona_ni_organizacion(entorno):
    entorno(zonas=())
    assert B.dominio_principal("correo.example.net") == "example.net"


def test_error_de_configuracion_es_aviso_con_codigo_cero(entorno):
    s = entorno()
    s.postconf["myhostname"] = "localhost"
    r = certificado.automatico()
    assert r["accion"] == "aviso" and "localhost" in r["motivo"]
    assert "localhost" in E.aviso()["texto"]
    assert not s.de("certbot")


def test_modo_no_valido_es_aviso(entorno):
    entorno(org="CERTIFICADO_MODO=individual\n", resuelven={"hosting.example.org"})
    r = certificado.automatico()
    assert r["accion"] == "aviso" and "CERTIFICADO_MODO" in r["motivo"]


def test_main_de_maquita_dns_sale_con_cero_ante_un_aviso(entorno, monkeypatch, capsys):
    import importlib.machinery
    import importlib.util

    s = entorno()
    s.postconf["myhostname"] = "localhost"
    cargador = importlib.machinery.SourceFileLoader("maquita_dns", os.path.join(RAIZ, "deploy", "dns", "maquita-dns"))
    spec = importlib.util.spec_from_loader("maquita_dns", cargador)
    mdns = importlib.util.module_from_spec(spec)
    cargador.exec_module(mdns)
    monkeypatch.setattr(mdns.os, "geteuid", lambda: 0)
    assert mdns.main(["maquita-dns", "certificado-auto"]) == 0
    assert '"accion": "aviso"' in capsys.readouterr().out


# --- DANE: la clave no cambia nunca -------------------------------------------------------------------


def test_toda_peticion_a_certbot_conserva_la_clave_ecdsa(entorno):
    s = entorno(org="CERTIFICADO_MODO=por-dominio\n",
                resuelven={"hosting.example.org", "mail.example.org", "mail.example.com", "autoconfig.example.com"})
    certificado.automatico()
    ordenes = s.de("certbot")
    assert len(ordenes) == 2
    for orden in ordenes:
        assert "--reuse-key" in orden and orden[orden.index("--key-type") + 1] == "ecdsa"
        assert "--webroot" in orden and "delete" not in orden and "revoke" not in orden


# --- 2. Certificado por dominio -----------------------------------------------------------------------


def test_por_dominio_pendiente_y_luego_activo_sin_intervencion(entorno):
    s = entorno(org="CERTIFICADO_MODO=por-dominio\n", resuelven={"hosting.example.org", "mail.example.org"})
    r = certificado.automatico()
    assert [d["estado"] for d in r["dominios"]] == ["pendiente"]
    assert not _certbots(s, "mail.example.com")
    servidor = _certbots(s, "hosting.example.org")[0]
    assert "mail.example.com" not in servidor  # el certificado del servidor no lleva al cliente
    # Mientras tanto, el webmail del servidor lo atiende con el certificado del servidor (provisional).
    assert "mail.example.com" in _leer(certificado.NOMBRES_NGINX)

    s.apuntan |= {"mail.example.com", "autodiscover.example.com"}
    r = certificado.automatico()
    (dominio,) = r["dominios"]
    assert dominio["estado"] == "emitido"
    (orden,) = _certbots(s, "mail.example.com")
    assert [orden[i + 1] for i, a in enumerate(orden) if a == "-d"] == ["mail.example.com", "autodiscover.example.com"]
    assert orden[orden.index("-m") + 1] == "postmaster@example.org"

    cadena, llave = B.rutas("mail.example.com")
    # nginx: bloque propio para el webmail, el portal 8444 y la autoconfiguración, enlazado en sites-enabled.
    generado = _leer(os.path.join(N.DISPONIBLES, "correo-dominio-example.com"))
    assert os.path.islink(os.path.join(N.ACTIVOS, "correo-dominio-example.com"))
    assert generado.count(f"ssl_certificate {cadena};") == 3
    assert "server_name mail.example.com;" in generado and "server_name autodiscover.example.com;" in generado
    assert "listen 8444 ssl;" in generado
    assert "default_server" not in generado and "correo-nombres.conf" not in generado
    assert "mail.example.com" not in _leer(certificado.NOMBRES_NGINX)
    # Postfix: mapa SNI compilado con -F y restart (reload no relee el mapa).
    assert _leer(S.MAPA).splitlines()[-1] == f"mail.example.com {llave} {cadena}"
    assert ["postmap", "-F", f"hash:{S.MAPA}"] in s.ordenes
    assert s.postconf["tls_server_sni_maps"] == f"hash:{S.MAPA}"
    assert ["systemctl", "restart", "postfix"] in s.ordenes
    # Dovecot 2.4.
    dov = _leer(os.path.join(S.DOVECOT_DIR, "maquita.d", S.DOVECOT_ARCHIVO))
    assert f"local_name mail.example.com {{\n  ssl_server_cert_file = {cadena}\n  ssl_server_key_file = {llave}\n}}" in dov
    # Gancho de renovación.
    gancho = _leer(S.GANCHO)
    assert "postmap -F" in gancho and "systemctl restart postfix" in gancho and "RENEWED_LINEAGE" in gancho
    assert r["sni"]["errores"] == []

    # Pasada siguiente sin cambios: no se pide ni se recarga nada.
    antes = len(s.ordenes)
    r = certificado.automatico()
    assert r["dominios"][0]["estado"] == "activo"
    nuevas = s.ordenes[antes:]
    assert not [c for c in nuevas if c[0] in ("certbot", "systemctl", "postmap")]


def test_espera_creciente_tras_un_fallo(entorno):
    s = entorno(org="CERTIFICADO_MODO=por-dominio\n",
                resuelven={"hosting.example.org", "mail.example.org", "mail.example.com"})
    s.fallan.add("mail.example.com")
    r = certificado.automatico()
    assert r["dominios"][0]["estado"] == "error" and "1 h" in r["dominios"][0]["motivo"]
    r = certificado.automatico()
    assert r["dominios"][0]["estado"] == "en-espera"
    assert len(_certbots(s, "mail.example.com")) == 1  # no se reintenta en bucle
    # Vencida la espera, se reintenta y la siguiente es el doble.
    datos = E.leer()
    datos["linajes"]["mail.example.com"]["proximo"] = 0
    E._guardar(datos)
    r = certificado.automatico()
    assert len(_certbots(s, "mail.example.com")) == 2 and "2 h" in r["dominios"][0]["motivo"]
    s.fallan.clear()
    datos = E.leer()
    datos["linajes"]["mail.example.com"]["proximo"] = 0
    E._guardar(datos)
    assert certificado.automatico()["dominios"][0]["estado"] == "emitido"
    assert E.de_linaje("mail.example.com")["fallos"] == 0


def test_transicion_retira_del_servidor_los_nombres_del_cliente_con_la_misma_clave(entorno):
    s = entorno(org="CERTIFICADO_MODO=por-dominio\n",
                resuelven={"hosting.example.org", "mail.example.org", "mail.example.com"})
    # Antes, en modo compartido, el certificado del servidor ya cubría al cliente.
    crear_linaje(s.raiz, "hosting.example.org", ["hosting.example.org", "mail.example.org", "mail.example.com"])
    s.fallan.add("mail.example.com")
    certificado.automatico()
    # Sin certificado propio todavía, el cliente sigue en el del servidor: no se pide nada al servidor.
    assert not _certbots(s, "hosting.example.org")
    assert "mail.example.com" in certificado._candidatos_servidor("hosting.example.org", "example.org", "por-dominio")

    s.fallan.clear()
    datos = E.leer()
    datos["linajes"]["mail.example.com"]["proximo"] = 0
    E._guardar(datos)
    certificado.automatico()  # emite el del cliente
    r = certificado.automatico()  # y el del servidor se reduce
    assert r["accion"] == "emitido" and r["retirados"] == ["mail.example.com"]
    (orden,) = _certbots(s, "hosting.example.org")
    assert "mail.example.com" not in orden and "--reuse-key" in orden


def test_nginx_que_falla_vuelve_atras_y_no_detiene_postfix(entorno):
    s = entorno(org="CERTIFICADO_MODO=por-dominio\n")
    crear_linaje(s.raiz, "mail.example.com", ["mail.example.com"])
    s.fallan.add("nginx")
    res = S.instalar("hosting.example.org", {"example.com": ["mail.example.com"]})
    assert any(e.startswith("nginx:") and "configuración anterior" in e for e in res["errores"])
    assert not os.path.exists(os.path.join(N.DISPONIBLES, "correo-dominio-example.com"))
    assert not os.path.lexists(os.path.join(N.ACTIVOS, "correo-dominio-example.com"))
    assert ["systemctl", "reload", "nginx"] not in s.ordenes
    assert "postfix" in res["cambios"] and "dovecot" in res["cambios"]


def test_postfix_check_que_falla_deja_el_parametro_como_estaba(entorno):
    s = entorno()
    crear_linaje(s.raiz, "mail.example.com", ["mail.example.com"])
    s.fallan.add("postfix")
    with pytest.raises(ErrorDns):
        S.postfix({"example.com": ["mail.example.com"]})
    assert s.postconf["tls_server_sni_maps"] == ""
    assert not os.path.exists(S.MAPA)
    assert ["systemctl", "restart", "postfix"] not in s.ordenes


def test_mapa_sni_ajeno_no_se_toca(entorno):
    s = entorno()
    s.postconf["tls_server_sni_maps"] = "hash:/etc/postfix/vmail_sni"
    with pytest.raises(B.ErrorConfiguracion):
        S.postfix({"example.com": ["mail.example.com"]})
    assert not os.path.exists(S.MAPA)


def test_dovecot_23_usa_la_sintaxis_antigua(entorno):
    entorno()
    texto = S.texto_dovecot({"example.com": []}, (2, 3))
    cadena, llave = B.rutas("mail.example.com")
    assert f"ssl_cert = <{cadena}" in texto and f"ssl_key = <{llave}" in texto
    assert "ssl_server_cert_file" not in texto


def test_dovecot_con_conf_d_de_debian(entorno, tmp_path):
    entorno()
    os.makedirs(os.path.join(S.DOVECOT_DIR, "conf.d"))
    with open(os.path.join(S.DOVECOT_DIR, "dovecot.conf"), "w") as f:
        f.write("!include conf.d/*.conf\n")
    assert S.destino_dovecot().endswith("conf.d/" + S.DOVECOT_ARCHIVO)


def test_mapa_compilado_se_rehace_si_el_certificado_es_mas_nuevo(entorno):
    s = entorno()
    crear_linaje(s.raiz, "mail.example.com", ["mail.example.com"])
    activos = {"example.com": ["mail.example.com"]}
    assert S.postfix(activos) is True
    assert S.postfix(activos) is False
    os.utime(S.MAPA + ".db", (1, 1))  # renovación sin gancho: el certificado es más nuevo que el mapa
    assert S.postfix(activos) is True


def test_mta_sts_del_cliente_pasa_a_su_certificado(entorno):
    s = entorno()
    ruta = os.path.join(N.DISPONIBLES, "mta-sts.example.com")
    with open(ruta, "w") as f:
        f.write("server {\n    listen 443 ssl;\n    server_name mta-sts.example.com;\n"
                "    ssl_certificate /etc/letsencrypt/live/hosting.example.org/fullchain.pem;\n"
                "    ssl_certificate_key /etc/letsencrypt/live/hosting.example.org/privkey.pem;\n}\n")
    cambios = N.planificar("hosting.example.org", {"example.com": ["mail.example.com", "mta-sts.example.com"]})
    cadena, llave = B.rutas("mail.example.com")
    assert f"ssl_certificate {cadena};" in cambios[ruta] and f"ssl_certificate_key {llave};" in cambios[ruta]
    assert s  # sin órdenes: solo se planifica


def test_archivo_generado_de_zona_borrada_se_retira(entorno):
    entorno()
    ruta = os.path.join(N.DISPONIBLES, "correo-dominio-example.net")
    with open(ruta, "w") as f:
        f.write(N.MARCA + ": viejo\n")
    assert N.planificar("hosting.example.org", {}) == {ruta: None}


def test_bloques_server_ignora_llaves_en_comentarios_y_comillas():
    texto = ('upstream a { server 127.0.0.1:1; }\n# server { comentario }\nserver {\n    listen 443 ssl;\n'
             '    server_name x.example.org;\n    return 200 "{texto}";\n    location / { if ($a) { return 403; } }\n}\n')
    (bloque,) = N.bloques_server(texto)
    assert texto[bloque[0]:bloque[1]].startswith("server {") and texto[bloque[0]:bloque[1]].endswith("}")
    assert N.elegir(texto, 443, "x.example.org")


def test_adaptar_quita_opciones_unicas_de_listen():
    bloque = ("server {\n    listen 443 ssl http2 default_server reuseport backlog=4096;\n"
              "    listen [::]:443 ssl ipv6only=on;\n    server_name a.example.org;\n}")
    nuevo = N.adaptar(bloque, ["mail.example.com"], "/c.pem", "/k.pem")
    assert "listen 443 ssl http2;" in nuevo and "listen [::]:443 ssl;" in nuevo
    assert "ssl_certificate /c.pem;" in nuevo and "ssl_certificate_key /k.pem;" in nuevo
    assert re.search(r"server_name mail\.example\.com;", nuevo)


def test_compartido_no_toca_sni(entorno):
    s = entorno(resuelven={"hosting.example.org", "mail.example.org", "mail.example.com"})
    r = certificado.automatico()
    assert "dominios" not in r and not s.de("postmap") and not os.path.exists(S.MAPA)
    assert "modo" in certificado.estado() and certificado.estado()["modo"] == "compartido"
