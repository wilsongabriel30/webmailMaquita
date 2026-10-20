"""GLPI — inventario de equipos y mesa de ayuda (GPLv3). https://glpi-project.org

Paquete oficial adjunto a la versión de GitHub de glpi-project (SHA-256 calculada por GitHub). Instalación por su
propia consola (bin/console database:install). La web se sirve desde «public/»: config, files, marketplace y el
código quedan fuera del alcance de la web, y todas las rutas .php pasan por su enrutador (public/index.php), como
en la configuración oficial de nginx. Las cuentas que trae de fábrica (glpi, tech, normal, post-only) tienen
claves conocidas: «glpi» pasa a ser el administrador generado y las otras quedan desactivadas con clave aleatoria.
"""

import os
import secrets

from comun import ErrorSitio

from . import receta

NOMBRE = "GLPI"
DESCRIPCION = "Inventario de computadoras y equipos, con mesa de ayuda para atender pedidos de soporte."
LICENCIA = "GPLv3"
CATEGORIA = "Soporte y proyectos"
VERIFICACION = "GitHub"
RAIZ_WEB = "public"
BD = "mariadb"

# Enrutador único (como la configuración oficial de nginx de GLPI): los .php que no son index.php y los recursos
# que no existen como archivo (p. ej. los de complementos) se entregan a public/index.php.
REGLAS_NGINX = r"""
    location = /front/login.php {
        limit_req zone=sitios_login burst=10 nodelay;
        limit_req zone=sitios_general burst=80 nodelay;
        try_files /.no-existe /index.php$$is_args$$args;
    }
    location ~ ^/index\.php$$ {
        include snippets/fastcgi-php.conf;
        fastcgi_pass unix:$socket;
        fastcgi_read_timeout 300s;
    }
    location ~ \.php(?:/|$$) { try_files /.no-existe /index.php$$is_args$$args; }
    location ~* \.(?:css|js|map|jpg|jpeg|gif|png|webp|svg|ico|woff2?|ttf|eot)$$ {
        expires 7d;
        try_files $$uri /index.php$$is_args$$args;
    }
"""

# Cuentas de fábrica que no se usan: quedan desactivadas y sin su clave conocida.
_FABRICA = ("tech", "normal", "post-only")


def _consola(meta, *args, tiempo=900):
    return receta.php(meta, "bin/console", "--no-interaction", *args, tiempo=tiempo)


def instalar(meta, bd, bd_usuario, bd_clave, titulo, correo, admin_usuario, admin_clave):
    fuente = receta.github("glpi-project/glpi", r"glpi-[0-9.]+\.tgz")
    receta.preparar(meta, fuente, "GLPI")
    if not os.path.isfile(os.path.join(meta["publico"], "public", "index.php")):
        raise ErrorSitio("el paquete de GLPI no tiene la estructura esperada")
    _consola(meta, "database:install", "--db-host=localhost", f"--db-name={bd}", f"--db-user={bd_usuario}",
             f"--db-password={bd_clave}", "--default-language=es_ES", "--no-telemetry", tiempo=1200)
    if not os.path.isfile(os.path.join(meta["publico"], "config", "config_db.php")):
        raise ErrorSitio("la instalación de GLPI no se completó (falta config_db.php)")
    sitio = receta.url(meta)
    _consola(meta, "config:set", "url_base", sitio)
    _consola(meta, "config:set", "admin_email", correo)
    # Administrador: la cuenta «glpi» (superadministrador de fábrica) con el nombre y la clave generados.
    receta.sql(meta, f"UPDATE glpi_users SET name = {receta.literal(admin_usuario)} WHERE name = 'glpi';")
    receta.sql(meta, "INSERT INTO glpi_useremails (users_id, is_default, is_dynamic, email) "
                     f"SELECT id, 1, 0, {receta.literal(correo)} FROM glpi_users WHERE name = {receta.literal(admin_usuario)};")
    clave_admin(meta, admin_usuario, admin_clave)
    otra = receta.hash_clave(secrets.token_urlsafe(32))
    nombres = ", ".join(receta.literal(n) for n in _FABRICA)
    receta.sql(meta, f"UPDATE glpi_users SET is_active = 0, password = {receta.literal(otra)} WHERE name IN ({nombres});")
    # Tareas programadas por la línea de órdenes (cron() de la receta), no al azar de las visitas.
    receta.sql(meta, "UPDATE glpi_crontasks SET mode = 2;")
    # El instalador web no debe quedar disponible; config solo para el usuario del sitio.
    receta.quitar(meta, "install/install.php")
    for n in os.listdir(os.path.join(meta["publico"], "config")):
        os.chmod(os.path.join(meta["publico"], "config", n), 0o600)
    return sitio + "/"


def cambiar_url(meta):
    """GLPI guarda su dirección en glpi_configs (url_base): la usan los correos y los enlaces externos."""
    _consola(meta, "config:set", "url_base", receta.url(meta))
    _consola(meta, "cache:clear")


def clave_admin(meta, usuario, nueva):
    _consola(meta, "user:reset_password", usuario, f"--password={nueva}")


def cron(meta):
    receta.php(meta, "front/cron.php", tiempo=280)
