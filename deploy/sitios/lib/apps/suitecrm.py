"""SuiteCRM 8 — CRM: cuentas, contactos, oportunidades, casos, campañas y agenda (AGPLv3).
https://suitecrm.com

Paquete oficial adjunto a la versión de GitHub de SuiteCRM-Core (el de instalación, no el «-dev» ni el
de migración; SHA-256 calculada por GitHub). Se instala con su línea de órdenes
(bin/console suitecrm:app:install). La web se sirve desde «public/»; dentro, «legacy/» es el SuiteCRM 7
que usa la versión 8: se niega lo mismo que niega su .htaccess oficial (subidas, código interno, registros).
"""

import hashlib
import os
import re

from comun import ErrorSitio

from . import receta

NOMBRE = "SuiteCRM"
DESCRIPCION = "CRM: clientes, contactos, oportunidades de venta, casos de soporte, campañas y agenda."
LICENCIA = "AGPLv3"
CATEGORIA = "Gestión y CRM"
VERIFICACION = "GitHub"
RAIZ_WEB = "public"

# Reglas del .htaccess que SuiteCRM genera para Apache (install_utils.php), más sus instaladores web.
REGLAS_NGINX = r"""
    location = /install.php { deny all; }
    location ~* ^/legacy/(?:install|upload|tests)(?:/|$$) { deny all; }
    location ~* ^/legacy/(?:install\.php|emailmandelivery\.php|RoboFile\.php|files\.md5|composer\.(?:json|lock)|config(?:_override|_si)?\.php)$$ { deny all; }
    location ~* ^/legacy/(?:custom/blowfish|cache/diagnostic)(?:/|$$) { deny all; }
    location ~* ^/legacy/.*/not_imported_[^/]*\.txt$$ { deny all; }
    location ~* ^/legacy/(?:.*/)?(?:soap|cache|xtemplate|data|examples|include|log4php|metadata|modules|vendor)/.*\.(?:php|tpl|phar)$$ { deny all; }
    # La interfaz pide todo por GraphQL: el texto de la consulta («{ id _id … }») parece una orden de shell
    # para el cortafuegos (regla 932100). Solo para ese campo se omiten las reglas de ejecución de órdenes;
    # las variables (los datos) se siguen revisando con todas las reglas.
    location = /api/graphql {
        modsecurity_rules 'SecAction "id:9201001,phase:1,pass,nolog,t:none,ctl:ruleRemoveTargetByTag=attack-rce;ARGS:json.query"';
        include fastcgi_params;
        fastcgi_param SCRIPT_FILENAME $$document_root/index.php;
        fastcgi_param SCRIPT_NAME /index.php;
        fastcgi_pass unix:$socket;
        fastcgi_read_timeout 120s;
    }
"""


def _consola(meta, *args, tiempo=900):
    return receta.php(meta, "bin/console", *args, "--no-interaction", "--env=prod", tiempo=tiempo)


def instalar(meta, bd, bd_usuario, bd_clave, titulo, correo, admin_usuario, admin_clave):
    fuente = receta.github("SuiteCRM/SuiteCRM-Core", r"SuiteCRM-\d+\.\d+\.\d+\.zip")
    receta.preparar(meta, fuente, "SuiteCRM")
    if not os.path.isfile(os.path.join(meta["publico"], "bin", "console")):
        raise ErrorSitio("el paquete de SuiteCRM no tiene la estructura esperada")
    sitio_url = receta.url(meta)
    salida = _consola(meta, "suitecrm:app:install", "-u", admin_usuario, "-p", admin_clave, "-U", bd_usuario,
                      "-P", bd_clave, "-H", "localhost", "-Z", "3306", "-N", bd, "-S", sitio_url + "/",
                      "-d", "no", "-W", "true", tiempo=1800)
    configuracion = os.path.join(meta["publico"], "public", "legacy", "config.php")
    if not os.path.isfile(configuracion) or "Installation Completed" not in salida:
        lineas = [l for l in salida.splitlines() if l.strip() and not l.startswith("===")]
        raise ErrorSitio("SuiteCRM: " + (lineas or ["la instalación no terminó"])[-1][:300])
    # La configuración del instalador silencioso lleva las claves en claro: ya no hace falta.
    receta.quitar(meta, "public/legacy/config_si.php")
    # SuiteCRM crea su caché (JS y CSS que sirve nginx) con permisos 2770 y el grupo del usuario del sitio
    # (al no ser miembro de www-data pierde el setgid): nginx no podría leerla. Con 0755/0644 la lee por los
    # permisos de «otros»; «publico» (2750, sin acceso para otros) sigue cerrando el paso a los demás usuarios.
    with open(configuracion) as f:
        texto = f.read()
    texto, n = re.subn(r"'dir_mode' => \d+,\s*'file_mode' => \d+,", "'dir_mode' => 493,\n    'file_mode' => 420,", texto)
    if n != 1:
        raise ErrorSitio("SuiteCRM: no se encontraron los permisos por omisión en config.php")
    receta.escribir(meta, "public/legacy/config.php", texto)
    receta.permisos(meta)
    # Correo del administrador (avisos y recuperación de contraseña).
    receta.sql(meta, f"INSERT INTO email_addresses (id, email_address, email_address_caps, date_created, date_modified) "
                     f"VALUES (UUID(), {receta.literal(correo)}, {receta.literal(correo.upper())}, NOW(), NOW());")
    receta.sql(meta, "INSERT INTO email_addr_bean_rel (id, email_address_id, bean_id, bean_module, primary_address, "
                     "date_created, date_modified) SELECT UUID(), e.id, u.id, 'Users', 1, NOW(), NOW() FROM "
                     f"email_addresses e, users u WHERE e.email_address = {receta.literal(correo)} "
                     f"AND u.user_name = {receta.literal(admin_usuario)};")
    return sitio_url + "/"


def clave_admin(meta, usuario, nueva):
    """SuiteCRM guarda password_hash(md5(clave)) en users.user_hash."""
    if not re.fullmatch(r"[A-Za-z0-9_]+", usuario):
        raise ErrorSitio("usuario no válido")
    hash_ = receta.hash_clave(hashlib.md5(nueva.encode()).hexdigest(), "PASSWORD_DEFAULT")
    receta.sql(meta, f"UPDATE users SET user_hash = {receta.literal(hash_)}, pwd_last_changed = NOW() "
                     f"WHERE user_name = {receta.literal(usuario)};")


def cron(meta):
    """Planificador de SuiteCRM (campañas, recordatorios, correo entrante, limpieza)."""
    receta.php(meta, "-f", "cron.php", cwd=os.path.join(meta["publico"], "public", "legacy"), tiempo=280)
