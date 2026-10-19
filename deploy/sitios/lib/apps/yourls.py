"""YOURLS — acortador de enlaces propio, con estadísticas de clics (MIT). https://yourls.org

YOURLS no adjunta paquetes a sus versiones: se descarga el archivo de la última etiqueta estable desde
GitHub por HTTPS (verificación «HTTPS»). La configuración (user/config.php) la escribe el panel con la
clave del administrador ya cifrada; las tablas se crean con la misma petición que haría una persona en
admin/install.php. Los enlaces cortos los resuelve yourls-loader.php.
"""

import html
import os
import re
import secrets

from comun import ErrorSitio

from . import receta

NOMBRE = "YOURLS"
DESCRIPCION = "Acortador de enlaces propio (su-dominio/abc) con estadísticas de clics."
LICENCIA = "MIT"
CATEGORIA = "Utilidades"
VERIFICACION = "HTTPS"
RAIZ_WEB = ""

# Toda ruta sin punto que no sea un archivo o carpeta real es un enlace corto (también «abc+» para sus
# estadísticas). Va antes que «location /» y que el bloque de PHP de la plantilla general.
REGLAS_NGINX = r"""
    location ~ ^/(?:includes|user/languages)/ { deny all; }
    location ~ ^/user/.*\.php$$ { deny all; }
    location = /admin/index.php {
        limit_req zone=sitios_login burst=10 nodelay;
        limit_req zone=sitios_general burst=80 nodelay;
        include snippets/fastcgi-php.conf;
        fastcgi_pass unix:$socket;
    }
    location ~ ^/[^.]*$$ { try_files $$uri $$uri/ /yourls-loader.php$$is_args$$args; }
"""


def _cadena(texto):
    """Literal de PHP entre comillas simples."""
    return "'" + str(texto).replace("\\", "\\\\").replace("'", "\\'") + "'"


def _hash(clave):
    # Formato propio de YOURLS: «phpass:» + password_hash() con «$» cambiado por «!».
    return "phpass:" + receta.hash_clave(clave).replace("$", "!")


def instalar(meta, bd, bd_usuario, bd_clave, titulo, correo, admin_usuario, admin_clave):
    fuente = receta.github_etiqueta("YOURLS/YOURLS", "https://github.com/YOURLS/YOURLS/archive/refs/tags/{etiqueta}.tar.gz")
    receta.preparar(meta, fuente, "YOURLS")
    if not os.path.isfile(os.path.join(meta["publico"], "yourls-loader.php")):
        raise ErrorSitio("el paquete de YOURLS no tiene la estructura esperada")
    sitio_url = receta.url(meta)
    constantes = {
        "YOURLS_DB_USER": bd_usuario, "YOURLS_DB_PASS": bd_clave, "YOURLS_DB_NAME": bd, "YOURLS_DB_HOST": "localhost",
        "YOURLS_DB_PREFIX": "yourls_", "YOURLS_SITE": sitio_url, "YOURLS_LANG": "",
        "YOURLS_COOKIEKEY": secrets.token_urlsafe(48),
    }
    lineas = ["<?php", "// Generado por el panel de hospedaje."]
    lineas += [f"define( '{k}', {_cadena(v)} );" for k, v in constantes.items()]
    lineas += [
        "define( 'YOURLS_UNIQUE_URLS', true );", "define( 'YOURLS_PRIVATE', true );",
        "define( 'YOURLS_URL_CONVERT', 36 );", "define( 'YOURLS_DEBUG', false );",
        "define( 'YOURLS_HOURS_OFFSET', -5 ); // America/Guayaquil, sin horario de verano",
        f"$yourls_user_passwords = [ {_cadena(admin_usuario)} => {_cadena(_hash(admin_clave))} ];",
        "$yourls_reserved_URL = [ 'admin', 'api' ];", "",
    ]
    receta.escribir(meta, "user/config.php", "\n".join(lineas))
    # Portada pública sencilla: sin ella «/» iría al cargador, que redirige a «/» otra vez.
    receta.escribir(meta, "index.html", f"<!doctype html><meta charset=utf-8><title>{html.escape(titulo)}</title>"
                    f"<p style=\"font:1.2em sans-serif;text-align:center;margin-top:4em\">{html.escape(titulo)}</p>\n",
                    0o644)
    web = receta.Web(meta)
    try:
        codigo, cuerpo, _ = web.pedir("/admin/install.php", {"install": "1"})
    finally:
        web.cerrar()
    if codigo != "200" or "<ul class='error'>" in cuerpo or "<ul class='success'>" not in cuerpo:
        raise ErrorSitio(f"el instalador de YOURLS no terminó (HTTP {codigo})")
    receta.quitar(meta, "admin/install.php")
    return sitio_url + "/admin/"


def clave_admin(meta, usuario, nueva):
    """La clave vive cifrada en user/config.php: se reemplaza la línea del administrador."""
    ruta = os.path.join(meta["publico"], "user", "config.php")
    with open(ruta) as f:
        texto = f.read()
    linea = f"$yourls_user_passwords = [ {_cadena(usuario)} => {_cadena(_hash(nueva))} ];"
    texto, n = re.subn(r"^\$yourls_user_passwords = \[.*\];$", lambda _: linea, texto, flags=re.M)
    if n != 1:
        raise ErrorSitio("no se encontró el administrador en la configuración de YOURLS")
    receta.escribir(meta, "user/config.php", texto)
