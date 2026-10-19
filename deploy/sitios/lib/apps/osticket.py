"""osTicket — mesa de ayuda con tiques por web y correo (GPLv2). https://osticket.com

Paquete oficial adjunto a la versión de GitHub de osTicket (SHA-256 calculada por GitHub); lo que se
publica en la web es su carpeta «upload/». osTicket no trae instalador por línea de órdenes: se envía
desde el servidor el formulario único de su asistente (setup/install.php), como lo haría una persona.
Después se borra setup/ y la configuración (include/ost-config.php) queda de solo lectura.
"""

import os

from comun import ErrorSitio

from . import receta

NOMBRE = "osTicket"
DESCRIPCION = "Mesa de ayuda: recibe pedidos de soporte por la web o por correo y los organiza en tiques."
LICENCIA = "GPLv2"
CATEGORIA = "Soporte y proyectos"
VERIFICACION = "GitHub"
RAIZ_WEB = ""
CONFIG = "include/ost-config.php"

# Según la guía de nginx de osTicket: la API (api/tickets.json, api/tasks/cron) pasa por api/http.php;
# include/ (configuración y código interno) no se sirve; manage.php y api/cron.php ya se niegan a correr
# fuera de la línea de órdenes. setup/ no se niega aquí porque el asistente se recorre por la web: se borra
# al terminar.
REGLAS_NGINX = r"""
    location = /scp/login.php {
        limit_req zone=sitios_login burst=10 nodelay;
        limit_req zone=sitios_general burst=80 nodelay;
        include snippets/fastcgi-php.conf;
        fastcgi_pass unix:$socket;
    }
    location ~ ^/api/(?:tickets|tasks)(?:[./].*)?$$ { rewrite ^/api/(.*)$$ /api/http.php/$$1 last; }
    location ^~ /include/ { deny all; }
    location ~* ^/(?:manage\.php|api/(?:cron|pipe)\.php|web\.config)$$ { deny all; }
"""


def instalar(meta, bd, bd_usuario, bd_clave, titulo, correo, admin_usuario, admin_clave):
    fuente = receta.github("osTicket/osTicket", r"osTicket-v[0-9.]+\.zip")
    receta.preparar(meta, fuente, NOMBRE, subcarpeta="upload")
    if not os.path.isfile(os.path.join(meta["publico"], "setup", "install.php")):
        raise ErrorSitio("el paquete de osTicket no tiene la estructura esperada")
    # El asistente escribe la configuración sobre una copia de la de ejemplo (con permiso de escritura).
    with open(os.path.join(meta["publico"], "include", "ost-sampleconfig.php")) as f:
        receta.escribir(meta, CONFIG, f.read(), 0o640)
    # osTicket no admite que el correo del sistema sea el mismo del administrador.
    sistema = f"soporte@{meta['dominio']}"
    if sistema.lower() == correo.lower():
        sistema = f"mesa-de-ayuda@{meta['dominio']}"
    web = receta.Web(meta)
    try:
        codigo, html, _ = web.pedir("/setup/install.php", {
            "s": "install", "name": titulo, "email": sistema, "lang_id": "en_US",
            "fname": "Administrador", "lname": "Mesa de ayuda", "admin_email": correo,
            "username": admin_usuario, "passwd": admin_clave, "passwd2": admin_clave,
            "prefix": "ost_", "dbhost": "localhost", "dbname": bd, "dbuser": bd_usuario, "dbpass": bd_clave,
            "timezone": "America/Guayaquil",
        })
    finally:
        web.cerrar()
    with open(os.path.join(meta["publico"], CONFIG)) as f:
        if "define('OSTINSTALLED',TRUE);" not in f.read():
            raise ErrorSitio(f"el asistente de osTicket no terminó la instalación (HTTP {codigo})")
    receta.quitar(meta, "setup")
    os.chmod(os.path.join(meta["publico"], CONFIG), 0o440)
    return receta.url(meta) + "/scp/"


def clave_admin(meta, usuario, nueva):
    """osTicket comprueba la clave con crypt(): acepta el bcrypt de password_hash()."""
    hash_ = receta.hash_clave(nueva)
    receta.sql(meta, f"UPDATE ost_staff SET passwd = {receta.literal(hash_)}, change_passwd = 0 "
                     f"WHERE username = {receta.literal(usuario)};")


def cron(meta):
    """Tareas periódicas: lectura de buzones, vencimientos de tiques, limpieza."""
    receta.php(meta, "api/cron.php", tiempo=280)
