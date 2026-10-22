"""Proxy de confianza: bloqueo en nginx de lo que banea fail2ban (acción maquita-nginx-baneo) y puertos del proxy
en el cortafuegos del panel solo para PROXY_CONFIABLE (ajuste 75)."""

import json
import os
import shutil
import stat
import subprocess
import sys

import pytest

from tests.test_proxy_confiable import PROXY, REPO, _correr, _raiz, ip_real

AYUDANTE = os.path.join(PROXY, "maquita-nginx-baneo")
hay_flock = pytest.mark.skipif(shutil.which("flock") is None or shutil.which("bash") is None, reason="sin flock")


# --- lo que se genera ----------------------------------------------------------------------------------------
@pytest.mark.parametrize("modo", ["proxy_protocol", "cabecera"])
def test_con_proxy_se_banea_tambien_en_nginx(modo):
    a = ip_real.archivos(ip_real.configuracion({"PROXY_CONFIABLE": "192.0.2.51", "PROXY_MODO": modo}))
    assert "geo $maquita_baneado {\n    default 0;\n    include maquita-baneados.conf;" in a[ip_real.NGINX_HTTP]
    assert "if ($maquita_baneado) { return 444; }" in a[ip_real.SNIPPET]
    jail = a["etc/fail2ban/jail.d/zz-maquita-proxy-baneo.local"]
    for carcel in ("sitios-escaneo", "sitios-abuso", "sitios-wp-login", "nginx-http-auth"):
        # Se suma a la acción que ya tenga la cárcel (el cortafuegos, el MikroTik…), no la sustituye.
        assert f"[{carcel}]\naction = %(known/action)s\n         maquita-nginx-baneo\n" in jail
    assert "actionban = <ayudante> banear <name> <ip>" in a["etc/fail2ban/action.d/maquita-nginx-baneo.conf"]
    assert a["usr/local/sbin/maquita-nginx-baneo"].startswith("#!/usr/bin/env bash")
    cortafuegos = a["etc/maquita-cortafuegos/proxy.json"]
    if modo == "proxy_protocol":
        assert json.loads(cortafuegos)["origenes"] == ["192.0.2.51"]
    else:
        assert cortafuegos is None  # el proxy entra por el 443, abierto como siempre


def test_sin_proxy_no_hay_baneo_en_nginx_y_la_accion_no_se_quita():
    a = ip_real.archivos(ip_real.configuracion({"FAIL2BAN_IGNORAR": "203.0.113.0/24"}))
    assert a["etc/fail2ban/jail.d/zz-maquita-proxy-baneo.local"] is None
    assert a["etc/maquita-cortafuegos/proxy.json"] is None
    # La acción y su ayudante no figuran: una cárcel que se para todavía los llama.
    assert "etc/fail2ban/action.d/maquita-nginx-baneo.conf" not in a and "usr/local/sbin/maquita-nginx-baneo" not in a


# --- el ayudante de la acción --------------------------------------------------------------------------------
def _ayudante_env(tmp_path, espera="0"):
    binarios = tmp_path / "bin"
    binarios.mkdir(exist_ok=True)
    registro = tmp_path / "ordenes.log"
    (binarios / "nginx").write_text(f'#!/bin/bash\necho "nginx $*" >> {registro}\n'
                                    '[ -z "${NGINX_FALLA:-}" ] || exit 1\n')
    (binarios / "systemctl").write_text(f'#!/bin/bash\necho "systemctl $*" >> {registro}\nexit 0\n')
    for b in binarios.iterdir():
        b.chmod(0o755)
    geo = tmp_path / "nginx/maquita-baneados.conf"
    geo.parent.mkdir(exist_ok=True)
    env = dict(os.environ, PATH=f"{binarios}:{os.environ.get('PATH', '')}", MAQUITA_BANEO_GEO=str(geo),
               MAQUITA_BANEO_ESTADO=str(tmp_path / "estado"), MAQUITA_BANEO_ESPERA=espera)
    return env, geo, registro


def _ay(env, *args):
    return subprocess.run(["bash", AYUDANTE, *args], capture_output=True, text=True, env=env, timeout=60)


def _entradas(geo):
    return [l for l in geo.read_text().splitlines() if not l.startswith("#")]


@hay_flock
def test_ayudante_banea_desbanea_y_para_por_carcel(tmp_path):
    env, geo, registro = _ayudante_env(tmp_path)
    assert _ay(env, "iniciar", "sitios-escaneo").returncode == 0
    assert _entradas(geo) == []
    assert _ay(env, "banear", "sitios-escaneo", "203.0.113.7").returncode == 0
    assert _ay(env, "banear", "sitios-escaneo", "203.0.113.7").returncode == 0  # idempotente
    assert _ay(env, "banear", "nginx-http-auth", "203.0.113.7").returncode == 0
    assert _ay(env, "banear", "nginx-http-auth", "2001:DB8:0::5").returncode == 0
    assert _entradas(geo) == ["2001:db8::5 1;", "203.0.113.7 1;"]  # unión sin repetidos, forma canónica
    assert "nginx -t -q" in registro.read_text() and "systemctl reload nginx" in registro.read_text()
    # Desbanear en una cárcel no lo quita mientras otra lo tenga.
    assert _ay(env, "desbanear", "sitios-escaneo", "203.0.113.7").returncode == 0
    assert _entradas(geo) == ["2001:db8::5 1;", "203.0.113.7 1;"]
    assert _ay(env, "parar", "nginx-http-auth").returncode == 0
    assert _entradas(geo) == []
    assert stat.S_IMODE(geo.stat().st_mode) == 0o644
    assert not [n for n in os.listdir(geo.parent) if n.startswith(".maquita-baneados")]  # sin temporales


@hay_flock
@pytest.mark.parametrize("args", [
    ("banear", "sitios-escaneo", "203.0.113.7; rm -rf /"),
    ("banear", "sitios-escaneo", "203.0.113.7\n0.0.0.0/0 1;"),
    ("banear", "sitios-escaneo", "192.0.2.0/24"),
    ("banear", "sitios-escaneo", "ejemplo.example.org"),
    ("banear", "../../etc/passwd", "203.0.113.7"),
    ("borrar", "sitios-escaneo", "203.0.113.7"),
])
def test_ayudante_rechaza_lo_que_no_es_ip_ni_carcel(tmp_path, args):
    env, geo, _ = _ayudante_env(tmp_path)
    r = _ay(env, *args)
    assert r.returncode != 0
    assert not geo.exists() or _entradas(geo) == []


@hay_flock
def test_ayudante_agrupa_las_recargas_de_baneos_simultaneos(tmp_path):
    env, geo, registro = _ayudante_env(tmp_path, espera="0.5")
    procesos = [subprocess.Popen(["bash", AYUDANTE, "banear", "sitios-abuso", f"198.51.100.{i}"], env=env)
                for i in range(1, 9)]
    assert all(p.wait(timeout=60) == 0 for p in procesos)
    assert sorted(_entradas(geo)) == sorted(f"198.51.100.{i} 1;" for i in range(1, 9))
    recargas = registro.read_text().count("systemctl reload nginx")
    assert 1 <= recargas <= 4, recargas


@hay_flock
def test_ayudante_sin_nginx_valido_no_recarga(tmp_path):
    env, geo, registro = _ayudante_env(tmp_path)
    env["NGINX_FALLA"] = "1"
    r = _ay(env, "banear", "sitios-escaneo", "203.0.113.8")
    assert r.returncode == 1 and "nginx -t falla" in r.stderr
    assert _entradas(geo) == ["203.0.113.8 1;"]  # queda apuntado para la próxima recarga
    assert "systemctl reload" not in registro.read_text()


# --- instalador: acción, archivo de nginx y cortafuegos del panel --------------------------------------------
def _con_cortafuegos(raiz, tmp_path, lee_proxy=True):
    (raiz / "etc/maquita-cortafuegos").mkdir(parents=True, exist_ok=True)
    (raiz / "etc/maquita-cortafuegos/reglas.json").write_text("{}")
    lib = raiz / "usr/local/lib/maquita-cortafuegos"
    lib.mkdir(parents=True, exist_ok=True)
    (lib / "config.py").write_text('PROXY_RUTA = "proxy.json"\n' if lee_proxy else "# versión anterior\n")
    sbin = raiz / "usr/local/sbin"
    sbin.mkdir(parents=True, exist_ok=True)
    (sbin / "maquita-cortafuegos").write_text(f'#!/bin/bash\necho "cortafuegos $*" >> {tmp_path}/ordenes.log\n'
                                              'echo \'{"recargado": true}\'\n')
    (sbin / "maquita-cortafuegos").chmod(0o755)


@pytest.mark.skipif(shutil.which("bash") is None, reason="sin bash")
def test_instalador_abre_4443_y_4444_solo_al_proxy_y_lo_quita(tmp_path):
    raiz, binarios, registro = _raiz(tmp_path)
    _con_cortafuegos(raiz, tmp_path)
    org = raiz / "etc/maquita-mail/organizacion.env"
    org.write_text("PROXY_CONFIABLE=192.0.2.51\n")
    rc, salida = _correr(raiz, binarios)
    assert rc == 0 and "Listo" in salida, salida
    proxy = raiz / "etc/maquita-cortafuegos/proxy.json"
    assert json.loads(proxy.read_text())["origenes"] == ["192.0.2.51"]
    assert stat.S_IMODE(proxy.stat().st_mode) == 0o600
    assert "cortafuegos recargar" in registro.read_text()
    assert "Aviso" not in salida
    # La acción, su ayudante (ejecutable) y el archivo de los baneados, que «geo» necesita.
    assert (raiz / "etc/fail2ban/action.d/maquita-nginx-baneo.conf").is_file()
    assert os.access(raiz / "usr/local/sbin/maquita-nginx-baneo", os.X_OK)
    assert (raiz / "etc/nginx/maquita-baneados.conf").is_file()
    assert "maquita-nginx-baneo" in (raiz / "etc/fail2ban/jail.d/zz-maquita-proxy-baneo.local").read_text()

    rc, salida = _correr(raiz, binarios)
    assert rc == 0 and salida.startswith("Sin cambios"), salida

    # Modo cabecera: el proxy entra por el 443; los puertos dedicados se cierran.
    org.write_text("PROXY_CONFIABLE=192.0.2.51\nPROXY_MODO=cabecera\n")
    rc, salida = _correr(raiz, binarios)
    assert rc == 0 and "quitar /etc/maquita-cortafuegos/proxy.json" in salida, salida
    assert not proxy.exists()
    assert (raiz / "etc/fail2ban/jail.d/zz-maquita-proxy-baneo.local").exists()  # el baneo en nginx sigue

    # Sin PROXY_CONFIABLE: fuera el baneo en nginx; la acción y el ayudante se quedan.
    org.write_text("FAIL2BAN_IGNORAR=203.0.113.0/24\n")
    rc, salida = _correr(raiz, binarios)
    assert rc == 0 and "Listo" in salida, salida
    assert not (raiz / "etc/fail2ban/jail.d/zz-maquita-proxy-baneo.local").exists()
    assert (raiz / "usr/local/sbin/maquita-nginx-baneo").exists()


@pytest.mark.skipif(shutil.which("bash") is None, reason="sin bash")
def test_instalador_sin_cortafuegos_o_anterior_solo_avisa(tmp_path):
    raiz, binarios, _ = _raiz(tmp_path)
    (raiz / "etc/maquita-mail/organizacion.env").write_text("PROXY_CONFIABLE=192.0.2.51\n")
    rc, salida = _correr(raiz, binarios, "--simular")
    assert rc == 0 and "Aviso: este servidor no usa el cortafuegos del panel" in salida
    assert "proxy.json" not in salida

    raiz2, binarios2, _ = _raiz(tmp_path / "dos")
    _con_cortafuegos(raiz2, tmp_path / "dos", lee_proxy=False)
    (raiz2 / "etc/maquita-mail/organizacion.env").write_text("PROXY_CONFIABLE=192.0.2.51\n")
    rc, salida = _correr(raiz2, binarios2, "--simular")
    assert rc == 0 and "no lee proxy.json" in salida, salida


@pytest.mark.skipif(shutil.which("bash") is None, reason="sin bash")
def test_instalador_vuelve_atras_si_el_cortafuegos_falla(tmp_path):
    raiz, binarios, _ = _raiz(tmp_path)
    _con_cortafuegos(raiz, tmp_path)
    (raiz / "usr/local/sbin/maquita-cortafuegos").write_text('#!/bin/bash\necho \'{"error": "x"}\'; exit 1\n')
    (raiz / "etc/maquita-mail/organizacion.env").write_text("PROXY_CONFIABLE=192.0.2.51\n")
    rc, salida = _correr(raiz, binarios)
    assert rc == 1 and "el cortafuegos rechaza" in salida, salida
    assert not (raiz / "etc/maquita-cortafuegos/proxy.json").exists()
    assert not (raiz / "etc/nginx/conf.d/maquita-ip-real.conf").exists()
    assert not (raiz / "etc/nginx/maquita-baneados.conf").exists()


# --- el cortafuegos del panel: lee proxy.json ----------------------------------------------------------------
@pytest.fixture
def cortafuegos(tmp_path, monkeypatch):
    lib = os.path.join(REPO, "deploy", "cortafuegos", "lib")
    previos = {n: sys.modules.pop(n) for n in ("config", "reglas") if n in sys.modules}
    sys.path.insert(0, lib)
    try:
        import config
        import reglas
    finally:
        sys.path.remove(lib)
        for n in ("config", "reglas"):
            sys.modules.pop(n, None)
        sys.modules.update(previos)
    monkeypatch.setattr(config, "BASES_DIR", str(tmp_path / "bases.d"))
    monkeypatch.setattr(config, "APPS_DIR", str(tmp_path / "apps.d"))
    monkeypatch.setattr(config, "PROXY_RUTA", str(tmp_path / "proxy.json"))
    return config, reglas, tmp_path / "proxy.json"


def test_cortafuegos_abre_los_puertos_del_proxy_solo_a_sus_origenes(cortafuegos):
    config, reglas, ruta = cortafuegos
    conf = config.por_defecto(admin=["192.0.2.1"])
    assert "4443" not in reglas.texto(conf)  # sin proxy.json, nada
    ruta.write_text(json.dumps({"origenes": ["192.0.2.51", "2001:db8::5", "0.0.0.0/0", "::/0", "x; iptables -F"]}))
    assert config.proxy() == []  # un valor malo invalida el archivo entero: nunca abre de más
    ruta.write_text(json.dumps({"origenes": ["192.0.2.51", "2001:db8::5", "0.0.0.0/0"]}))
    assert config.proxy() == ["192.0.2.51/32", "2001:db8::5/128"]
    v4, v6 = reglas.texto(conf), reglas.texto(conf, v6=True)
    assert '-A CORTAFUEGOS -s 192.0.2.51/32 -p tcp -m multiport --dports 4443,4444 -m comment --comment "proxy de confianza" -j ACCEPT' in v4
    assert "-s 2001:db8::5/128 -p tcp -m multiport --dports 4443,4444" in v6
    for texto in (v4, v6):
        assert not [l for l in texto.splitlines() if "4443" in l and " -s " not in l]
