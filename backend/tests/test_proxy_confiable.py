"""Proxy de confianza y lista blanca de fail2ban (deploy/hardening/proxy, ajuste 75, guardián).

Incidente de Andes (22/10/2026): las cárceles de los sitios banearon la IP del proxy TLS y el servidor quedó
sin webmail, portal ni sitios para Internet. Se prueba la validación de organizacion.env, los archivos que se
generan, el parche de los vhosts, el instalador (simular, idempotencia, vuelta atrás y desbaneo) y las
funciones del guardián.
"""

import importlib.util
import os
import shutil
import subprocess

import pytest

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
PROXY = os.path.join(REPO, "deploy", "hardening", "proxy")
INSTALADOR = os.path.join(PROXY, "instalar.sh")
AJUSTE = os.path.join(REPO, "deploy", "ajustes", "75-fail2ban-proxy.sh")
LIB_PROXY = os.path.join(REPO, "deploy", "vigilantes", "lib-proxy.sh")
GUARDIAN = os.path.join(REPO, "deploy", "vigilantes", "guardian-web-correo")

_spec = importlib.util.spec_from_file_location("ip_real", os.path.join(PROXY, "ip_real.py"))
ip_real = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ip_real)

hay_bash = pytest.mark.skipif(shutil.which("bash") is None, reason="sin bash")


# --- validación ----------------------------------------------------------------------------------------------
@pytest.mark.parametrize("valor, esperado", [
    ("192.0.2.51", "192.0.2.51"),
    ("192.0.2.51/32", "192.0.2.51"),
    ("203.0.113.0/24", "203.0.113.0/24"),
    ("2001:db8::1", "2001:db8::1"),
    ("2001:DB8::/32", "2001:db8::/32"),
])
def test_red_valida_y_canonica(valor, esperado):
    assert ip_real.red(valor) == esperado


@pytest.mark.parametrize("valor", [
    "proxy.example.org", "192.0.2.300", "192.0.2.1/24", "0.0.0.0/0", "10.0.0.0/7", "::/0",
    "192.0.2.1;rm", "192.0.2.1\n[sshd]", "192.0.2.1 enabled=false", "$(id)", "",
])
def test_red_rechaza_basura_y_redes_enormes(valor):
    with pytest.raises(ip_real.ErrorConfig):
        ip_real.red(valor)


def test_listas_y_modo():
    cfg = ip_real.configuracion({"FAIL2BAN_IGNORAR": "203.0.113.0/24, 198.51.100.9 203.0.113.0/24",
                                 "PROXY_CONFIABLE": "192.0.2.51"})
    assert cfg == {"ignorar": ["203.0.113.0/24", "198.51.100.9"], "proxy": ["192.0.2.51"], "modo": "proxy_protocol"}
    assert ip_real.configuracion({"PROXY_CONFIABLE": "192.0.2.51", "PROXY_MODO": "Cabecera"})["modo"] == "cabecera"
    # Sin proxy no hay modo, aunque se haya escrito.
    assert ip_real.configuracion({"PROXY_MODO": "cabecera"})["modo"] == ""
    with pytest.raises(ip_real.ErrorConfig):
        ip_real.configuracion({"PROXY_CONFIABLE": "192.0.2.51", "PROXY_MODO": "proxy_protocol; include x"})
    with pytest.raises(ip_real.ErrorConfig):
        ip_real.configuracion({"FAIL2BAN_IGNORAR": " ".join(f"192.0.2.{i}" for i in range(1, 70))})


# --- archivos generados --------------------------------------------------------------------------------------
def test_sin_variables_no_se_genera_nada():
    cfg = ip_real.configuracion({})
    assert all(v is None for v in ip_real.archivos(cfg, ["10.0.0.0/8"]).values())


def test_fail2ban_suma_lo_previo_y_el_proxy():
    cfg = ip_real.configuracion({"FAIL2BAN_IGNORAR": "203.0.113.0/24", "PROXY_CONFIABLE": "192.0.2.51"})
    texto = ip_real.contenido_fail2ban(cfg, ["127.0.0.1/8", "10.0.0.0/8"])
    assert "[DEFAULT]\nignoreip = 127.0.0.1/8 ::1 10.0.0.0/8 203.0.113.0/24 192.0.2.51\n" in texto
    # Solo FAIL2BAN_IGNORAR: fail2ban sí, nginx no.
    solo = ip_real.archivos(ip_real.configuracion({"FAIL2BAN_IGNORAR": "203.0.113.5"}))
    assert solo[ip_real.F2B_NUESTRO] and not solo[ip_real.NGINX_HTTP] and not solo[ip_real.SNIPPET]


def test_nginx_proxy_protocol():
    cfg = ip_real.configuracion({"PROXY_CONFIABLE": "192.0.2.51 2001:db8::5"})
    a = ip_real.archivos(cfg)
    assert "set_real_ip_from 192.0.2.51;\nset_real_ip_from 2001:db8::5;\nreal_ip_header proxy_protocol;" in a[ip_real.NGINX_HTTP]
    assert "listen 4443 ssl proxy_protocol;\nlisten [::]:4443 ssl proxy_protocol;" in a[ip_real.SNIPPET]
    assert "listen 4443 ssl proxy_protocol default_server;" in a[ip_real.SNIPPET_DEFECTO]
    assert "listen 4444 ssl proxy_protocol;" in a[ip_real.SNIPPET_PORTAL]
    assert "[::]" not in ip_real.contenido_snippet(ip_real.configuracion({"PROXY_CONFIABLE": "192.0.2.51"}), 4443)


def test_nginx_cabecera_sin_puertos_nuevos():
    a = ip_real.archivos(ip_real.configuracion({"PROXY_CONFIABLE": "192.0.2.51", "PROXY_MODO": "cabecera"}))
    assert "real_ip_header X-Forwarded-For;\nreal_ip_recursive on;" in a[ip_real.NGINX_HTTP]
    # Sin puertos nuevos: los snippets solo llevan el corte de los baneados.
    for clave in (ip_real.SNIPPET, ip_real.SNIPPET_DEFECTO, ip_real.SNIPPET_PORTAL):
        assert "listen" not in a[clave] and "if ($maquita_baneado) { return 444; }" in a[clave]


def test_ignoreip_previos_lee_jail_local_y_otros_local(tmp_path):
    f2b = tmp_path / "etc/fail2ban"
    (f2b / "jail.d").mkdir(parents=True)
    (f2b / "jail.local").write_text("[DEFAULT]\nignoreip = 127.0.0.1/8 ::1 10.0.0.0/8\nbackend = systemd\n[sshd]\nenabled = true\n")
    (f2b / "jail.d/zz-andes-ignoreip.local").write_text("[DEFAULT]\nignoreip = 127.0.0.1/8 198.51.100.7 proxy.example.org\n")
    (f2b / "jail.d/sitios-web.conf").write_text("[DEFAULT]\nignoreip = 203.0.113.99\n")  # .conf: lo pisa jail.local
    (f2b / "jail.d/zz-maquita-ignorar.local").write_text("[DEFAULT]\nignoreip = 192.0.2.200\n")  # el nuestro, viejo
    previos = ip_real.ignoreip_previos(str(tmp_path))
    assert previos == ["127.0.0.0/8", "::1", "10.0.0.0/8", "198.51.100.7"]
    cfg = ip_real.configuracion({"PROXY_CONFIABLE": "192.0.2.51"})
    assert ip_real.ignorar_todas(cfg, previos) == ["127.0.0.1/8", "::1", "10.0.0.0/8", "198.51.100.7", "192.0.2.51"]


# --- vhosts --------------------------------------------------------------------------------------------------
SITIO = """server {
    listen 80;
    listen [::]:80;
    server_name sitio.example.com;
}

server {
    listen 443 ssl;
    listen [::]:443 ssl;
    http2 on;
    server_name sitio.example.com;
}
"""

WEBMAIL = """server {
    listen 443 ssl http2 default_server;
    server_name mail.example.org;
    location ^~ /webmail/ { root /x; }
}
server {
    listen 0.0.0.0:443 ssl;
    server_name autodiscover.example.org;
}
"""


def test_incluir_en_vhost_tras_cada_listen_ipv4():
    nuevo = ip_real.incluir_en_vhost(SITIO)
    assert "    listen 443 ssl;\n    include snippets/maquita-ip-real.con[f];" in nuevo
    assert nuevo.count("maquita-ip-real") == 1  # ni en el 80 ni en el [::]:443
    assert ip_real.incluir_en_vhost(nuevo) is None  # idempotente
    assert ip_real.incluir_en_vhost("server {\n    listen 80;\n}\n") is None


def test_incluir_en_vhost_webmail_un_solo_default_server():
    nuevo = ip_real.incluir_en_vhost(WEBMAIL, defecto=True)
    assert nuevo.count("maquita-ip-real-defecto.con[f]") == 1
    assert nuevo.count("snippets/maquita-ip-real.con[f]") == 1
    assert nuevo.index("defecto") < nuevo.index("autodiscover")


def test_incluir_en_vhost_portal_y_puertos_propios():
    portal = "server {\n    listen 8444 ssl;\n    http2 on;\n}\n"
    assert "include snippets/maquita-ip-real-portal.con[f];" in ip_real.incluir_en_vhost(portal)
    # Un vhost que ya escucha en el puerto del proxy (parche a mano) no se toca.
    assert ip_real.incluir_en_vhost("server {\n    listen 443 ssl;\n    listen 4443 ssl proxy_protocol;\n}\n") is None


def test_plantillas_del_repositorio_ya_lo_incluyen():
    def leer(*partes):
        with open(os.path.join(REPO, *partes), encoding="utf-8") as f:
            return f.read()
    assert "include snippets/maquita-ip-real-defecto.con[f];" in leer("deploy/webmail/nginx/webmail.conf")
    assert "include snippets/maquita-ip-real.con[f];" in leer("deploy/sitios/lib/plantillas.py")
    assert "include snippets/maquita-ip-real.con[f];" in leer("deploy/webmail/nginx/autodiscover-dominios.conf")
    assert "include snippets/maquita-ip-real.con[f];" in leer("deploy/webmail/autoconfig/nginx-autoconfig.conf.plantilla")
    assert "include snippets/maquita-ip-real-portal.con[f];" in leer("panel-dominio/deploy/nginx-panel-dominio.conf")
    # Los instaladores lo aplican después de escribir jail.local y los vhosts.
    assert "deploy/hardening/proxy/instalar.sh" in leer("deploy/webmail/instalar.sh")
    assert "deploy/hardening/proxy/instalar.sh" in leer("deploy/sitios/instalar.sh")


def test_dentro_de_las_redes_protegidas():
    assert ip_real.dentro(["192.0.2.51", "198.51.100.1", "203.0.113.4", "basura", "2001:db8::9"],
                          ["192.0.2.51", "203.0.113.0/24", "2001:db8::/32"]) == ["192.0.2.51", "203.0.113.4", "2001:db8::9"]


# --- el instalador, de punta a punta, con nginx y fail2ban simulados --------------------------------------
def _raiz(tmp_path):
    raiz = tmp_path / "raiz"
    for d in ("etc/nginx/sites-available", "etc/nginx/sites-enabled", "etc/nginx/conf.d", "etc/nginx/snippets",
              "etc/fail2ban/jail.d", "etc/maquita-mail"):
        (raiz / d).mkdir(parents=True)
    (raiz / "etc/fail2ban/jail.local").write_text("[DEFAULT]\nignoreip = 127.0.0.1/8 ::1\n")
    (raiz / "etc/nginx/sites-available/mail.example.org").write_text(WEBMAIL)
    (raiz / "etc/nginx/sites-available/sitio.example.com").write_text(SITIO)
    for n in ("mail.example.org", "sitio.example.com"):
        os.symlink(f"../sites-available/{n}", raiz / f"etc/nginx/sites-enabled/{n}")
    binarios = tmp_path / "bin"
    binarios.mkdir()
    registro = tmp_path / "ordenes.log"
    (binarios / "nginx").write_text(f'#!/bin/bash\necho "nginx $*" >> {registro}\n'
                                    '[ -z "${NGINX_FALLA:-}" ] || { echo "emerg: prueba" >&2; exit 1; }\n')
    (binarios / "fail2ban-client").write_text(
        f'#!/bin/bash\necho "fail2ban-client $*" >> {registro}\n'
        'case "$1" in\n'
        '  ping) echo "Server replied: pong" ;;\n'
        '  status) if [ -z "${2:-}" ]; then echo "|- Number of jail: 2"; echo "\\`- Jail list: sshd, sitios-escaneo";\n'
        '          elif [ "$2" = sitios-escaneo ]; then echo "   \\`- Banned IP list: ${BANEADAS:-}"; else echo "   \\`- Banned IP list:"; fi ;;\n'
        '  get) if [ -n "${SIN_ACCION:-}" ]; then echo "iptables-multiport"; else echo "iptables-multiport, maquita-nginx-baneo"; fi ;;\n'
        'esac\nexit 0\n')
    (binarios / "systemctl").write_text(f'#!/bin/bash\necho "systemctl $*" >> {registro}\nexit 0\n')
    for b in binarios.iterdir():
        b.chmod(0o755)
    return raiz, binarios, registro


def _correr(raiz, binarios, *args, script=INSTALADOR, **extra):
    env = dict(os.environ, PROXY_RAIZ=str(raiz), APP_DIR=str(raiz / "app"),
               PATH=f"{binarios}:{os.environ.get('PATH', '/usr/bin:/bin')}", **extra)
    r = subprocess.run(["bash", script, *args], capture_output=True, text=True, env=env, timeout=60)
    return r.returncode, r.stdout + r.stderr


@hay_bash
def test_instalador_simula_aplica_y_es_idempotente(tmp_path):
    raiz, binarios, registro = _raiz(tmp_path)
    rc, salida = _correr(raiz, binarios, "--simular")
    assert rc == 0 and salida.startswith("Sin cambios"), salida

    (raiz / "etc/maquita-mail/organizacion.env").write_text(
        'FAIL2BAN_IGNORAR="203.0.113.0/24"\nPROXY_CONFIABLE=192.0.2.51\n')
    vhost_antes = (raiz / "etc/nginx/sites-available/sitio.example.com").read_text()
    rc, salida = _correr(raiz, binarios, "--simular", BANEADAS="192.0.2.51 198.51.100.66")
    assert rc == 0 and salida.startswith("Pendiente"), salida
    assert "desbanear 192.0.2.51" in salida and "198.51.100.66" not in salida
    assert not (raiz / "etc/fail2ban/jail.d/zz-maquita-ignorar.local").exists()  # simular no escribe
    assert (raiz / "etc/nginx/sites-available/sitio.example.com").read_text() == vhost_antes

    rc, salida = _correr(raiz, binarios, BANEADAS="192.0.2.51")
    assert rc == 0 and "Listo" in salida, salida
    assert "ignoreip = 127.0.0.1/8 ::1 203.0.113.0/24 192.0.2.51" in \
        (raiz / "etc/fail2ban/jail.d/zz-maquita-ignorar.local").read_text()
    assert "real_ip_header proxy_protocol;" in (raiz / "etc/nginx/conf.d/maquita-ip-real.conf").read_text()
    assert "maquita-ip-real.con[f]" in (raiz / "etc/nginx/sites-available/sitio.example.com").read_text()
    assert "maquita-ip-real-defecto.con[f]" in (raiz / "etc/nginx/sites-available/mail.example.org").read_text()
    assert (raiz / "etc/nginx/sites-enabled/sitio.example.com").is_symlink()  # el enlace sigue siendo enlace
    # Copias fuera de sites-enabled.
    copias = os.listdir(raiz / "etc/nginx/respaldos")
    assert any(c.startswith("etc_nginx_sites-available_sitio.example.com.ajuste-75-") for c in copias)
    assert not [n for n in os.listdir(raiz / "etc/nginx/sites-enabled") if "ajuste" in n or "bak" in n]
    ordenes = registro.read_text()
    assert "nginx -t" in ordenes and "fail2ban-client -t" in ordenes
    assert "fail2ban-client unban 192.0.2.51" in ordenes and "systemctl reload nginx" in ordenes

    rc, salida = _correr(raiz, binarios)
    assert rc == 0 and salida.startswith("Sin cambios"), salida

    # Una cárcel en marcha sin la acción de nginx (reload no cambia sus acciones): se reinicia esa cárcel.
    rc, salida = _correr(raiz, binarios, SIN_ACCION="1")
    assert rc == 0 and salida.startswith("Listo: la acción de nginx en las cárceles sitios-escaneo"), salida
    assert "fail2ban-client reload --restart sitios-escaneo" in registro.read_text()

    # Sin las variables, lo generado se retira (los include de los vhosts se quedan: sin archivo no hacen nada).
    (raiz / "etc/maquita-mail/organizacion.env").write_text("ORG_DOMINIO=example.org\n")
    rc, salida = _correr(raiz, binarios)
    assert rc == 0 and "Listo" in salida, salida
    assert not (raiz / "etc/fail2ban/jail.d/zz-maquita-ignorar.local").exists()
    assert not (raiz / "etc/nginx/conf.d/maquita-ip-real.conf").exists()


@hay_bash
def test_instalador_vuelve_atras_si_nginx_rechaza(tmp_path):
    raiz, binarios, _ = _raiz(tmp_path)
    (raiz / "etc/maquita-mail/organizacion.env").write_text("PROXY_CONFIABLE=192.0.2.51\n")
    antes = (raiz / "etc/nginx/sites-available/sitio.example.com").read_text()
    rc, salida = _correr(raiz, binarios, NGINX_FALLA="1")
    assert rc == 1 and "nginx rechaza" in salida, salida
    assert (raiz / "etc/nginx/sites-available/sitio.example.com").read_text() == antes
    assert not (raiz / "etc/nginx/conf.d/maquita-ip-real.conf").exists()
    assert not (raiz / "etc/fail2ban/jail.d/zz-maquita-ignorar.local").exists()


@hay_bash
def test_instalador_con_valor_malo_no_toca_nada(tmp_path):
    raiz, binarios, registro = _raiz(tmp_path)
    (raiz / "etc/maquita-mail/organizacion.env").write_text('PROXY_CONFIABLE="192.0.2.51;\\ninclude /etc/passwd"\n')
    rc, salida = _correr(raiz, binarios)
    assert rc == 1 and "PROXY_CONFIABLE" in salida, salida
    assert not (raiz / "etc/fail2ban/jail.d/zz-maquita-ignorar.local").exists()
    assert not registro.exists() or "nginx -t" not in registro.read_text()


@hay_bash
def test_ajuste_75_delega_en_el_instalador(tmp_path):
    raiz, binarios, _ = _raiz(tmp_path)
    (raiz / "etc/maquita-mail/organizacion.env").write_text("FAIL2BAN_IGNORAR=198.51.100.0/24\n")
    env = dict(os.environ, PROXY_RAIZ=str(raiz), APP_DIR=REPO, PATH=f"{binarios}:{os.environ.get('PATH', '')}")
    r = subprocess.run(["bash", AJUSTE, "--simular"], capture_output=True, text=True, env=env, timeout=60)
    assert r.returncode == 0 and r.stdout.startswith("Pendiente"), r.stdout + r.stderr
    assert "zz-maquita-ignorar.local" in r.stdout


# --- guardián ------------------------------------------------------------------------------------------------
@hay_bash
def test_guardian_y_scripts_sin_errores_de_sintaxis():
    for s in (INSTALADOR, AJUSTE, LIB_PROXY, GUARDIAN):
        assert subprocess.run(["bash", "-n", s]).returncode == 0, s
    with open(GUARDIAN, encoding="utf-8") as f:
        texto = f.read()
    assert "desde Internet no responde" in texto and "lib-proxy.sh" in texto
    # El nombre público se prueba sin --resolve (DNS normal).
    linea = next(l for l in texto.splitlines() if '"https://$PUBLICO/webmail/"' in l)
    assert "--resolve" not in linea


@hay_bash
def test_lib_proxy_detecta_al_proxy_baneado(tmp_path):
    _, binarios, _ = _raiz(tmp_path)
    env_backend = tmp_path / "backend.env"
    env_backend.write_text('MAIL_HOST="mail.example.org"\n')
    orden = (f'vig_servidor() {{ echo servidor.example.org; }}; . {LIB_PROXY}; '
             'vig_nombre_publico; vig_redes_protegidas; vig_baneadas_protegidas')
    env = dict(os.environ, PATH=f"{binarios}:{os.environ.get('PATH', '')}", MAQUITA_BACKEND_ENV=str(env_backend),
               FAIL2BAN_IGNORAR="203.0.113.0/24", PROXY_CONFIABLE="192.0.2.51",
               BANEADAS="198.51.100.3 192.0.2.51 203.0.113.9")
    r = subprocess.run(["bash", "-c", orden], capture_output=True, text=True, env=env, timeout=30)
    assert r.returncode == 0, r.stderr
    assert r.stdout.splitlines() == ["mail.example.org", "203.0.113.0/24 192.0.2.51",
                                     "192.0.2.51 sitios-escaneo", "203.0.113.9 sitios-escaneo"]
    # Sin MAIL_HOST, el nombre del servidor; sin redes protegidas, nada que mirar.
    env.update(MAQUITA_BACKEND_ENV=str(tmp_path / "no-existe"), FAIL2BAN_IGNORAR="", PROXY_CONFIABLE="")
    r = subprocess.run(["bash", "-c", orden], capture_output=True, text=True, env=env, timeout=30)
    assert r.stdout.split() == ["servidor.example.org"]
