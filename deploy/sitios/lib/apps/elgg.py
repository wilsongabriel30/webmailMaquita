"""Elgg — red social para comunidades y organizaciones (GPLv2). https://elgg.org

Paquete oficial adjunto a la versión de GitHub (elgg/elgg, SHA-256 calculada por GitHub), que ya trae
vendor/. Instalación por su propia línea de órdenes (vendor/bin/elgg-cli install) con un archivo de
parámetros temporal en la carpeta privada; los datos (dataroot) quedan fuera de la web. Solo se ejecutan
index.php y upgrade.php: el instalador web no hace falta y se niega.
"""

import os
import pwd
import shutil

from comun import ErrorSitio

from . import receta

NOMBRE = "Elgg"
DESCRIPCION = "Red social propia: perfiles, grupos, blogs, foros, archivos y mensajes entre miembros."
LICENCIA = "GPLv2"
CATEGORIA = "Foros y comunidad"
VERIFICACION = "GitHub"
RAIZ_WEB = ""
BD = "mariadb"

REGLAS_NGINX = r"""
    location = /action/login {
        limit_req zone=sitios_login burst=10 nodelay;
        limit_req zone=sitios_general burst=80 nodelay;
        try_files $$uri /index.php?$$args;
    }
    # Recursos de la caché simple: si aún no están generados, los produce index.php.
    location ^~ /cache/ { expires 7d; try_files $$uri /index.php?$$args; }
    location ~ ^/(?:elgg-config|vendor|mod)/.*\.(?:php|json|lock|md|rst|xml|txt)$$ { deny all; }
    location ~ ^/(?:elgg-config|vendor/bin)/ { deny all; }
    location ~ ^/(?:composer\.(?:json|lock)|phpunit\.xml\.dist|README\.md)$$ { deny all; }
    location ~ ^/(?:index|upgrade)\.php$$ {
        include snippets/fastcgi-php.conf;
        fastcgi_pass unix:$socket;
        fastcgi_read_timeout 300s;
    }
    location ~ \.php(?:/|$$) { deny all; }
"""


def _php(valor):
    """Literal de PHP entre comillas simples."""
    return "'" + str(valor).replace("\\", "\\\\").replace("'", "\\'") + "'"


def _elgg_cli(meta, *args, entrada=None):
    return receta.php(meta, "vendor/bin/elgg-cli", *args, "--no-interaction", entrada=entrada)


def instalar(meta, bd, bd_usuario, bd_clave, titulo, correo, admin_usuario, admin_clave):
    fuente = receta.github("elgg/elgg", r"elgg-[0-9.]+\.zip")
    receta.preparar(meta, fuente, "Elgg")
    if not os.path.isfile(os.path.join(meta["publico"], "vendor/bin/elgg-cli")):
        raise ErrorSitio("el paquete de Elgg no tiene la estructura esperada")
    datos = receta.privada(meta, "elgg-datos")
    parametros = {
        "displayname": "Administrador", "username": admin_usuario, "password": admin_clave, "email": correo,
        "dbhost": "localhost", "dbport": "3306", "dbuser": bd_usuario, "dbpassword": bd_clave, "dbname": bd,
        "dbprefix": "elgg_", "sitename": titulo, "siteemail": correo, "wwwroot": receta.url(meta) + "/",
        "dataroot": datos + "/",
    }
    # Archivo de parámetros (lleva claves) solo legible por el usuario del sitio y borrado al terminar.
    ruta = os.path.join(meta["tmp"], ".elgg-instalacion.php")
    with open(os.open(ruta, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600), "w") as f:
        f.write("<?php\nreturn [\n" + "".join(f"    {_php(k)} => {_php(v)},\n" for k, v in parametros.items()) + "];\n")
    os.chown(ruta, *_ids(meta))
    try:
        try:
            salida = _elgg_cli(meta, "install", f"--config={ruta}")
        finally:
            os.remove(ruta)
        if "install successful" not in salida:
            raise ErrorSitio("la instalación de Elgg quedó incompleta")
        os.chmod(os.path.join(meta["publico"], "elgg-config/settings.php"), 0o640)
        # El instalador deja el sitio en inglés: idioma del sitio y del administrador en español.
        _api(meta, f"elgg_save_config('language', 'es'); $u = elgg_get_user_by_username({_php(admin_usuario)});\n"
                   "if (!$u) return false; $u->language = 'es'; return $u->save();")
    except Exception:
        # El panel vacía la carpeta pública y la base; los datos privados también, para poder reintentar.
        shutil.rmtree(datos, ignore_errors=True)
        raise
    return receta.url(meta) + "/login"


def _ids(meta):
    p = pwd.getpwnam(meta["usuario"])
    return p.pw_uid, p.pw_gid


def _api(meta, cuerpo):
    """Ejecuta código con la propia API de Elgg (sin restricciones de acceso). Las claves van por la
    entrada estándar, no en la línea de órdenes."""
    codigo = ("<?php require 'vendor/autoload.php'; \\Elgg\\Application::start();\n"
              "$ok = elgg_call(ELGG_IGNORE_ACCESS, function () {\n" + cuerpo + "\n});\nexit($ok ? 0 : 1);\n")
    receta.php(meta, entrada=codigo)


def clave_admin(meta, usuario, nueva):
    _api(meta, f"$u = elgg_get_user_by_username({_php(usuario)}); if (!$u) return false;\n"
               f"$u->setPassword({_php(nueva)}); return $u->save();")


def cron(meta):
    _elgg_cli(meta, "cron", "--quiet")
