"""Piwigo — galería de fotos para organizaciones y personas (GPLv2+). https://piwigo.org

Paquete oficial de piwigo.org (su enlace de descarga de la última versión). El proyecto no publica suma
de sus paquetes: se descarga solo por HTTPS de su origen y se anota la suma del archivo instalado. Se
recorre su instalador web (install.php, un único formulario) desde el servidor; después se borra
install.php y la carpeta install/ (que solo usan la instalación y las actualizaciones) no se sirve.
"""

import os
import re
import time

from comun import ErrorSitio, ejecutar

from . import receta

NOMBRE = "Piwigo"
DESCRIPCION = "Galería de fotos: álbumes, etiquetas, permisos por grupo y descarga de imágenes."
LICENCIA = "GPLv2+"
CATEGORIA = "Archivos y galerías"
VERIFICACION = "HTTPS"
RAIZ_WEB = ""
BD = "mariadb"
DESCARGA = "https://piwigo.org/download/dlcounter.php?code=latest"

REGLAS_NGINX = r"""
    location = /identification.php {
        limit_req zone=sitios_login burst=10 nodelay;
        limit_req zone=sitios_general burst=80 nodelay;
        include snippets/fastcgi-php.conf;
        fastcgi_pass unix:$socket;
    }
    location ~ ^/(?:include|install|local/config|doc|docs|tools|_data/(?:logs|templates_c|cache))/ { deny all; }
    location ~ ^/(?:_data|upload|galleries|local|language|themes|template-extension)/.*\.php$$ { deny all; }
    location ~* \.(?:tpl|inc\.php)$$ { deny all; }
    location ~ ^/(?:README\.md|SECURITY\.md|COPYING\.txt|LICENSE\.txt)$$ { deny all; }
"""


def _version(meta):
    with open(f"{meta['publico']}/include/constants.php") as f:
        m = re.search(r"define\('PHPWG_VERSION', '([0-9.]+)'\)", f.read())
    if not m:
        raise ErrorSitio("el paquete de Piwigo no tiene la estructura esperada")
    return m.group(1)


def instalar(meta, bd, bd_usuario, bd_clave, titulo, correo, admin_usuario, admin_clave):
    receta.preparar(meta, receta.Fuente("última", DESCARGA, None, "sha256", "HTTPS"), "Piwigo")
    meta["app_version"] = _version(meta)
    web = receta.Web(meta)
    try:
        for _ in range(10):
            # PHP-FPM se recarga al crear o cambiar sitios: se espera a que el grupo del sitio responda.
            codigo, html, _ = web.pedir("/install.php?language=es_ES")
            if codigo not in ("502", "503", "504"):
                break
            time.sleep(3)
        if codigo != "200" or "admin_pass1" not in html:
            raise ErrorSitio(f"el instalador de Piwigo no respondió (HTTP {codigo})")
        codigo, html, _ = web.pedir("/install.php?language=es_ES", {
            "dbhost": "localhost", "dbuser": bd_usuario, "dbpasswd": bd_clave, "dbname": bd, "prefix": "piwigo_",
            "admin_name": admin_usuario, "admin_pass1": admin_clave, "admin_pass2": admin_clave,
            "admin_mail": correo, "install": "Iniciar la instalación"})
    finally:
        web.cerrar()
    hay = ""
    if os.path.isfile(f"{meta['publico']}/local/config/database.inc.php"):
        hay = ejecutar(["mariadb", "--protocol=socket", "-u", "root", "-N", bd, "-e",
                        f"SELECT COUNT(*) FROM piwigo_users WHERE username = {receta.literal(admin_usuario)};"]).strip()
    if hay != "1":
        avisos = "; ".join(re.findall(r'<li>([^<]{3,200})</li>', html))[:300]
        raise ErrorSitio(f"el instalador de Piwigo no terminó (HTTP {codigo}) {avisos}".strip())
    os.chmod(f"{meta['publico']}/local/config/database.inc.php", 0o640)
    receta.quitar(meta, "install.php")
    receta.sql(meta, f"UPDATE piwigo_config SET value = {receta.literal(titulo)} WHERE param = 'gallery_title';")
    return receta.url(meta) + "/identification.php"


def clave_admin(meta, usuario, nueva):
    """Piwigo guarda el hash de phpass (su propia clase); se calcula con ella."""
    hash_ = ejecutar([receta.cli_php(meta), "-r", "require 'include/passwordhash.class.php'; $h = new PasswordHash(13, true); "
                      "echo $h->HashPassword(stream_get_contents(STDIN));"],
                     entrada=nueva, como=meta["usuario"], cwd=meta["publico"])
    if not hash_.startswith("$P$"):
        raise ErrorSitio("no se pudo calcular la contraseña")
    receta.sql(meta, f"UPDATE piwigo_users SET password = {receta.literal(hash_)} WHERE username = {receta.literal(usuario)};")
