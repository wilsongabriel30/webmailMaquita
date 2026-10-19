"""Kanboard — tableros de proyectos al estilo kanban (MIT). https://kanboard.org

El proyecto no adjunta paquete a sus versiones de GitHub: se descarga el archivo oficial de la última
etiqueta estable por HTTPS (ya trae «vendor/», no hace falta Composer). Kanboard no tiene instalador: basta
config.php con la base MariaDB y su orden «db:migrate». La migración crea el usuario admin/admin, que se
renombra y recibe la clave generada por el panel. Los datos (adjuntos, caché) van en la carpeta privada.
"""

import os

from comun import ErrorSitio, ejecutar

from . import receta

NOMBRE = "Kanboard"
DESCRIPCION = "Tableros de proyectos con tarjetas: tareas, responsables, plazos y avance del equipo."
LICENCIA = "MIT"
CATEGORIA = "Soporte y proyectos"
VERIFICACION = "HTTPS"
RAIZ_WEB = ""
BD = "mariadb"

# Código, librerías, datos y configuración no se sirven (guía de nginx de Kanboard); de los complementos solo
# se sirven sus recursos estáticos.
REGLAS_NGINX = r"""
    location ~ ^/(?:app|libs|vendor|data|cli)(?:/|$$) { deny all; }
    location ~ ^/(?:config(?:\.default)?\.php|docker-compose[^/]*|ChangeLog|web\.config|CONTRIBUTING\.md)$$ { deny all; }
    location ~* ^/plugins/.*\.(?:php|json|md)$$ { deny all; }
"""

_CONFIG = """<?php
// Configuración generada por el panel de hospedaje (opciones completas en config.default.php).
define('DATA_DIR', {datos});
define('PLUGIN_INSTALLER', false);
define('MAIL_FROM', {remitente});
define('DB_DRIVER', 'mysql');
define('DB_HOSTNAME', 'localhost');
define('DB_NAME', {bd});
define('DB_USERNAME', {bd_usuario});
define('DB_PASSWORD', {bd_clave});
define('DB_RUN_MIGRATIONS', false);
"""


def _php_texto(valor):
    return "'" + str(valor).replace("\\", "\\\\").replace("'", "\\'") + "'"


def instalar(meta, bd, bd_usuario, bd_clave, titulo, correo, admin_usuario, admin_clave):
    fuente = receta.github_etiqueta(
        "kanboard/kanboard", "https://github.com/kanboard/kanboard/archive/refs/tags/{etiqueta}.tar.gz")
    receta.preparar(meta, fuente, "Kanboard")
    if not os.path.isfile(os.path.join(meta["publico"], "vendor", "autoload.php")):
        raise ErrorSitio("el paquete de Kanboard no tiene la estructura esperada")
    datos = receta.privada(meta, "kanboard-datos")
    receta.escribir(meta, "config.php", _CONFIG.format(
        datos=_php_texto(datos), remitente=_php_texto("no-responder@" + meta["dominio"]), bd=_php_texto(bd),
        bd_usuario=_php_texto(bd_usuario), bd_clave=_php_texto(bd_clave)))
    receta.quitar(meta, "data")  # los datos van en la carpeta privada
    receta.php(meta, "cli", "db:migrate")
    # El administrador inicial (admin/admin) pasa a ser el del panel, en español y con la zona de Ecuador.
    clave = receta.literal(receta.hash_clave(admin_clave))
    receta.sql(meta, f"UPDATE users SET username = {receta.literal(admin_usuario)}, password = {clave}, "
                     f"name = 'Administrador', email = {receta.literal(correo)}, language = 'es_ES', "
                     f"timezone = 'America/Guayaquil' WHERE username = 'admin' AND role = 'app-admin';")
    for opcion, valor in (("application_language", "es_ES"), ("application_timezone", "America/Guayaquil"),
                          ("application_url", receta.url(meta) + "/"), ("application_date_format", "d/m/Y")):
        receta.sql(meta, f"INSERT INTO settings (`option`, `value`) VALUES ({receta.literal(opcion)}, "
                         f"{receta.literal(valor)}) ON DUPLICATE KEY UPDATE `value` = VALUES(`value`);")
    # Sin el administrador renombrado, nadie podría entrar con los datos que muestra el panel.
    hay = ejecutar(["mariadb", "--protocol=socket", "-u", "root", "-N", "-B", bd, "-e",
                    f"SELECT COUNT(*) FROM users WHERE username = {receta.literal(admin_usuario)};"]).strip()
    if hay != "1":
        raise ErrorSitio("Kanboard no creó su administrador inicial")
    receta.permisos(meta)
    return receta.url(meta) + "/?controller=AuthController&action=login"


def clave_admin(meta, usuario, nueva):
    """Kanboard guarda password_hash() con bcrypt en la tabla users."""
    receta.sql(meta, f"UPDATE users SET password = {receta.literal(receta.hash_clave(nueva))} "
                     f"WHERE username = {receta.literal(usuario)};")


def cron(meta):
    """Tareas diarias de Kanboard (avisos de vencimiento, estadísticas)."""
    receta.php(meta, "cli", "cronjob", tiempo=280)
