"""DokuWiki — wiki sencillo que guarda las páginas en archivos, sin base de datos (GPLv2). https://www.dokuwiki.org

Paquete oficial adjunto a la versión de GitHub (SHA-256 calculada por GitHub). DokuWiki no tiene
instalador de línea de órdenes: se escriben los mismos archivos que genera su install.php (local.php,
users.auth.php con la clave en bcrypt, acl.auth.php y plugins.local.php) y se borra el instalador. Las
páginas y archivos subidos (data/) van a la carpeta privada del sitio.
"""

import os
import re
import shutil

from comun import ErrorSitio

from . import receta

NOMBRE = "DokuWiki"
DESCRIPCION = "Wiki sencillo para manuales y documentación interna; no necesita base de datos."
LICENCIA = "GPLv2"
CATEGORIA = "Wikis y documentación"
VERIFICACION = "GitHub"
RAIZ_WEB = ""
BD = None

# Carpetas internas sin servir (guía de seguridad de DokuWiki) y solo los PHP de entrada.
REGLAS_NGINX = r"""
    location ~ ^/(?:data|conf|bin|inc|vendor)/ { deny all; }
    location ~ ^/(?:README|VERSION|COPYING|SECURITY\.md|install\.php)$$ { deny all; }
    location ~ ^/(?!(?:doku|index|feed)\.php(?:/|$$)|lib/exe/[a-z_]+\.php(?:/|$$)).*\.php(?:/|$$) { deny all; }
"""

_CABECERA = "# {nombre}\n# <?php exit()?>\n# Don't modify the lines above\n#\n# Generado por el panel de hospedaje\n\n"


def _texto_php(texto):
    return "'" + str(texto).replace("\\", "\\\\").replace("'", "\\'") + "'"


def _linea_usuario(usuario, clave, correo):
    # Formato: login:hash:Nombre:correo:grupos (los dos puntos separan campos).
    return ":".join([usuario, receta.hash_clave(clave), "Administrador", correo.replace(":", ""), "admin,user"])


def instalar(meta, bd, bd_usuario, bd_clave, titulo, correo, admin_usuario, admin_clave):
    fuente = receta.github("dokuwiki/dokuwiki", r"dokuwiki-[0-9a-z-]+\.tgz")
    fuente.version = fuente.version.removeprefix("release-")
    receta.preparar(meta, fuente, "DokuWiki")
    publico = meta["publico"]
    if not os.path.isfile(os.path.join(publico, "doku.php")) or not os.path.isdir(os.path.join(publico, "data")):
        raise ErrorSitio("el paquete de DokuWiki no tiene la estructura esperada")
    # Datos fuera de la web.
    datos = receta.privada(meta, "dokuwiki-data")
    for n in os.listdir(os.path.join(publico, "data")):
        shutil.move(os.path.join(publico, "data", n), os.path.join(datos, n))
    receta.quitar(meta, "data", "install.php")
    receta.privada(meta, "dokuwiki-data")  # dueño y permisos de todo lo movido
    receta.escribir(meta, "conf/local.php", "<?php\n# Generado por el panel de hospedaje\n"
                    f"$conf['title'] = {_texto_php(titulo)};\n"
                    "$conf['lang'] = 'es';\n"
                    "$conf['license'] = 'cc-by-sa';\n"
                    f"$conf['savedir'] = {_texto_php(datos)};\n"
                    "$conf['useacl'] = 1;\n"
                    "$conf['superuser'] = '@admin';\n"
                    "$conf['disableactions'] = 'register';\n"
                    f"$conf['mailfrom'] = {_texto_php(correo)};\n")
    receta.escribir(meta, "conf/users.auth.php", _CABECERA.format(nombre="users.auth.php")
                    + "# login:passwordhash:Real Name:email:groups,comma,separated\n\n"
                    + _linea_usuario(admin_usuario, admin_clave, correo) + "\n")
    # Lectura pública; editar y subir archivos, solo usuarios con cuenta (las da el administrador).
    receta.escribir(meta, "conf/acl.auth.php", _CABECERA.format(nombre="acl.auth.php")
                    + "*               @ALL          1\n*               @user         8\n")
    receta.escribir(meta, "conf/plugins.local.php", "<?php\n$plugins['authad'] = 0;\n$plugins['authldap'] = 0;\n"
                    "$plugins['authmysql'] = 0;\n$plugins['authpgsql'] = 0;\n")
    return receta.url(meta) + "/doku.php?do=login"


def clave_admin(meta, usuario, nueva):
    ruta = os.path.join(meta["publico"], "conf/users.auth.php")
    with open(ruta) as f:
        texto = f.read()
    patron = re.compile(r"^%s:[^:\n]*:(.*)$" % re.escape(usuario), re.M)
    m = patron.search(texto)
    if not m:
        raise ErrorSitio("no existe el usuario en DokuWiki")
    nombre, correo, grupos = (m.group(1).split(":") + ["", "", ""])[:3]
    linea = ":".join([usuario, receta.hash_clave(nueva), nombre, correo, grupos])
    receta.escribir(meta, "conf/users.auth.php", texto[:m.start()] + linea + texto[m.end():])
