"""MyBB — foro de debate (LGPLv3). https://mybb.com

Paquete oficial adjunto a la versión de GitHub de mybb/mybb (SHA-256 calculada por GitHub); lo que se
publica es su carpeta «Upload/». MyBB no trae instalador por línea de órdenes: se recorre su asistente web
(install/index.php), que no guarda estado entre pasos, desde el propio servidor. Al terminar se borra
install/ y config.php queda de solo lectura.
"""

import hashlib
import os
import re
import secrets

from comun import ErrorSitio

from . import receta

NOMBRE = "MyBB"
DESCRIPCION = "Foro de debate: temas, respuestas, mensajes privados, moderación y grupos de usuarios."
LICENCIA = "LGPLv3"
CATEGORIA = "Foros y comunidad"
VERIFICACION = "GitHub"
RAIZ_WEB = ""
BD = "mariadb"

# Carpetas internas que no se sirven (configuración, librerías, copias del panel) y límite de intentos de
# acceso (solo cuentan los POST) en el foro y en el panel de administración. install/ no se niega aquí porque
# el asistente se recorre por la web; al terminar se borra entero.
REGLAS_NGINX = r"""
    location ^~ /inc/ { deny all; }
    location ^~ /admin/backups/ { deny all; }
    location ^~ /admin/inc/ { deny all; }
    location ^~ /admin/modules/ { deny all; }
    location ~* ^/(?:htaccess(?:-nginx)?\.txt|error\.log)$$ { deny all; }
    location ~ ^/(?:member|admin/index)\.php$$ {
        limit_req zone=sitios_login burst=10 nodelay;
        limit_req zone=sitios_general burst=80 nodelay;
        include snippets/fastcgi-php.conf;
        fastcgi_pass unix:$socket;
    }
"""


def instalar(meta, bd, bd_usuario, bd_clave, titulo, correo, admin_usuario, admin_clave):
    fuente = receta.github("mybb/mybb", r"mybb_\d+\.zip")
    m = re.fullmatch(r"mybb_(\d)(\d)(\d+)", fuente.version)  # etiqueta «mybb_1841» → 1.8.41
    if m:
        fuente.version = ".".join(m.groups())
    receta.preparar(meta, fuente, "MyBB", subcarpeta="Upload")
    if not os.path.isfile(os.path.join(meta["publico"], "install", "index.php")):
        raise ErrorSitio("el paquete de MyBB no tiene la estructura esperada")
    sitio_url = receta.url(meta)
    web = receta.Web(meta)
    try:
        pasos = [
            # Comprueba requisitos y crea inc/config.php a partir de config.default.php.
            ({"action": "requirements_check"}, "database_info"),
            ({"action": "create_tables", "dbengine": "mysqli", "config[mysqli][dbhost]": "localhost",
             "config[mysqli][dbuser]": bd_usuario, "config[mysqli][dbpass]": bd_clave,
             "config[mysqli][dbname]": bd, "config[mysqli][tableprefix]": "mybb_",
             "config[mysqli][encoding]": "utf8mb4"}, "populate_tables"),
            ({"action": "populate_tables"}, "templates"),
            ({"action": "templates"}, "configuration"),
            ({"action": "adminuser", "bbname": titulo, "bburl": sitio_url, "websitename": titulo,
             "websiteurl": sitio_url, "cookiedomain": "", "cookiepath": "/", "contactemail": correo, "pin": ""}, "final"),
            ({"action": "final", "adminuser": admin_usuario, "adminpass": admin_clave, "adminpass2": admin_clave,
             "adminemail": correo}, None),
        ]
        # Cada paso correcto ofrece el siguiente; si hay un error, el asistente repite el mismo paso.
        for datos, siguiente in pasos:
            codigo, html, _ = web.pedir("/install/index.php", datos)
            if codigo != "200" or (siguiente and f'name="action" value="{siguiente}"' not in html):
                raise ErrorSitio(f"el asistente de MyBB se detuvo en «{datos['action']}» (HTTP {codigo})")
    finally:
        web.cerrar()
    if not os.path.exists(os.path.join(meta["publico"], "install", "lock")):
        raise ErrorSitio("la instalación de MyBB no se completó")
    # Zona horaria de Ecuador (UTC-5): en la base y en la copia de la configuración que MyBB lee (settings.php).
    receta.sql(meta, "UPDATE mybb_settings SET value = '-5' WHERE name = 'timezoneoffset';")
    ajustes = os.path.join(meta["publico"], "inc", "settings.php")
    with open(ajustes) as f:
        texto = f.read()
    with open(ajustes, "w") as f:
        f.write(re.sub(r"""\$settings\['timezoneoffset'\] = "[^"]*";""", """$settings['timezoneoffset'] = "-5";""", texto))
    receta.quitar(meta, "install", "htaccess.txt", "htaccess-nginx.txt")
    os.chmod(os.path.join(meta["publico"], "inc", "config.php"), 0o440)
    return sitio_url + "/admin/index.php"


def clave_admin(meta, usuario, nueva):
    """MyBB guarda md5(md5(sal) . md5(clave)); con una loginkey nueva se cierran las sesiones abiertas."""
    sal = secrets.token_hex(4)
    hash_ = hashlib.md5((hashlib.md5(sal.encode()).hexdigest() + hashlib.md5(nueva.encode()).hexdigest())
                        .encode()).hexdigest()
    clave_sesion = secrets.token_hex(25)
    receta.sql(meta, f"UPDATE mybb_users SET password = '{hash_}', salt = '{sal}', loginkey = '{clave_sesion}' "
                     f"WHERE username = {receta.literal(usuario)};")


def cron(meta):
    """Tareas programadas de MyBB (limpieza, copias de la base, avisos) sin depender de las visitas."""
    receta.php(meta, "task.php", tiempo=280)
