"""«http2 on;» con un nginx anterior a 1.25.1 (Debian 12, Ubuntu 22.04): forma antigua en el listen."""

import importlib.util
import os
import subprocess

RAIZ = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")
_spec = importlib.util.spec_from_file_location(
    "nginx_http2", os.path.join(RAIZ, "deploy", "sitios", "lib", "nginx_http2.py"))
nginx_http2 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(nginx_http2)

VHOST = """server {
    listen 443 ssl;
    listen [::]:443 ssl;
    http2 on;
    server_name example.org;
}
"""


def test_nginx_moderno_no_cambia():
    assert nginx_http2.adaptar(VHOST, (1, 26, 3)) == VHOST
    assert nginx_http2.adaptar(VHOST, (1, 25, 1)) == VHOST


def test_nginx_antiguo_usa_listen_http2():
    texto = nginx_http2.adaptar(VHOST, (1, 22, 1))
    assert "http2 on;" not in texto
    assert "    listen 443 ssl http2;\n" in texto
    assert "    listen [::]:443 ssl http2;\n" in texto


def test_sin_version_o_sin_http2_no_cambia():
    assert nginx_http2.adaptar("server { listen 443 ssl; }\n", (1, 18, 0)) == "server { listen 443 ssl; }\n"
    nginx_http2.version.cache_clear()


def test_guion_con_nginx_antiguo(tmp_path):
    falso = tmp_path / "bin"
    falso.mkdir()
    (falso / "nginx").write_text("#!/bin/sh\necho 'nginx version: nginx/1.22.1' >&2\n")
    (falso / "nginx").chmod(0o755)
    archivo = tmp_path / "vhost.conf"
    archivo.write_text(VHOST)
    entorno = dict(os.environ, PATH=f"{falso}:{os.environ['PATH']}")
    subprocess.run(["bash", os.path.join(RAIZ, "deploy", "tools", "nginx-http2-compatible.sh"), str(archivo)],
                   check=True, env=entorno)
    assert archivo.read_text() == nginx_http2.adaptar(VHOST, (1, 22, 1))
    (falso / "nginx").write_text("#!/bin/sh\necho 'nginx version: nginx/1.26.3' >&2\n")
    archivo.write_text(VHOST)
    subprocess.run(["bash", os.path.join(RAIZ, "deploy", "tools", "nginx-http2-compatible.sh"), str(archivo)],
                   check=True, env=entorno)
    assert archivo.read_text() == VHOST
