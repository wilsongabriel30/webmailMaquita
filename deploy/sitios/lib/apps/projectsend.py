"""ProjectSend — enviar archivos a clientes de forma privada (GPLv2). https://www.projectsend.org

Paquete oficial adjunto a la versión de GitHub (projectsend/projectsend, SHA-256 calculada por GitHub), que
ya trae vendor/. Desde la versión 2 es una aplicación Laravel con instalación por su propia línea de
órdenes (artisan migrate y projectsend:admin), según su INSTALL.md. La web se sirve desde «public»; la
configuración (.env) y los archivos subidos (storage/) quedan fuera de la web y las descargas, tras la
comprobación de permisos en PHP, las envía nginx (X-Accel-Redirect a una ruta interna).
ProjectSend entra con el CORREO del administrador, no con el nombre de usuario.
"""

import json
import os
import re
import time

from comun import ErrorSitio, ejecutar

from . import receta

NOMBRE = "ProjectSend"
DESCRIPCION = "Enviar archivos a clientes de forma privada: cada cliente ve y descarga solo lo suyo."
LICENCIA = "GPLv2"
CATEGORIA = "Archivos y galerías"
VERIFICACION = "GitHub"
ENTRA_CON_CORREO = True  # el panel muestra el correo como usuario de acceso
RAIZ_WEB = "public"
BD = "mariadb"

# Reglas de su INSTALL.md (paso 6): descargas por ruta interna y búfer de cabeceras más amplio.
REGLAS_NGINX = r"""
    location = /login {
        limit_req zone=sitios_login burst=10 nodelay;
        limit_req zone=sitios_general burst=80 nodelay;
        try_files $$uri /index.php?$$query_string;
    }
    # public/protected-files es un enlace a storage/app/files: solo se llega por la ruta interna.
    location ^~ /protected-files/ {
        internal;
        add_header X-Content-Type-Options "nosniff" always;
        add_header X-Frame-Options "SAMEORIGIN" always;
        add_header Referrer-Policy "strict-origin-when-cross-origin" always;
        add_header Content-Security-Policy "sandbox; default-src 'none'" always;
    }
    location = /index.php {
        include snippets/fastcgi-php.conf;
        fastcgi_pass unix:$socket;
        fastcgi_read_timeout 300s;
        fastcgi_buffer_size 32k;
        fastcgi_buffers 8 32k;
    }
    location ~ \.php(?:/|$$) { deny all; }
"""


def _artisan(meta, *args, tiempo=900):
    return receta.php(meta, "artisan", *args, "--no-interaction", tiempo=tiempo)


def _valor(texto):
    """Valor de .env entre comillas simples (literal: sin variables ni comentarios)."""
    if "'" in str(texto) or "\n" in str(texto):
        raise ErrorSitio("valor no admitido en la configuración de ProjectSend")
    return f"'{texto}'"


def instalar(meta, bd, bd_usuario, bd_clave, titulo, correo, admin_usuario, admin_clave):
    fuente = receta.github("projectsend/projectsend", r"projectsend-[0-9.]+\.zip")
    receta.preparar(meta, fuente, "ProjectSend")
    if not os.path.isfile(os.path.join(meta["publico"], "artisan")):
        raise ErrorSitio("el paquete de ProjectSend no tiene la estructura esperada")
    env = {
        "APP_NAME": titulo, "APP_ENV": "production", "APP_KEY": "", "APP_DEBUG": "false",
        "APP_URL": receta.url(meta), "APP_TIMEZONE": "America/Guayaquil", "APP_LOCALE": "es",
        "APP_FALLBACK_LOCALE": "en", "PROJECTSEND_EDITION": "community",
        "DB_CONNECTION": "mariadb", "DB_HOST": "localhost", "DB_PORT": "3306", "DB_DATABASE": bd,
        "DB_USERNAME": bd_usuario, "DB_PASSWORD": bd_clave,
        "SESSION_DRIVER": "database", "CACHE_STORE": "database", "QUEUE_CONNECTION": "database",
        "FILESYSTEM_DISK": "local",
        # nginx (www-data) envía las descargas: tiene que poder leer los archivos (solo su grupo llega).
        "PROJECTSEND_FILE_DELIVERY": "nginx", "FILES_WEB_SERVER_READABLE": "true",
        "MAIL_MAILER": "smtp", "MAIL_HOST": "localhost", "MAIL_PORT": "25", "MAIL_ENCRYPTION": "null",
        "MAIL_FROM_ADDRESS": f"no-responder@{meta['dominio']}", "MAIL_FROM_NAME": titulo,
        "LOG_CHANNEL": "stack", "LOG_STACK": "daily", "LOG_LEVEL": "warning",
    }
    receta.escribir(meta, ".env", "".join(f"{k}={_valor(v)}\n" for k, v in env.items()), 0o600)
    receta.permisos(meta)
    _artisan(meta, "key:generate", "--force")
    _artisan(meta, "migrate", "--force", tiempo=1200)
    _artisan(meta, "storage:link")
    # Destino de X-Accel-Redirect (la configuración oficial usa «alias», que aquí no puede llevar la ruta).
    enlace = os.path.join(meta["publico"], "public", "protected-files")
    os.makedirs(os.path.join(meta["publico"], "storage", "app", "files"), exist_ok=True)
    os.symlink("../storage/app/files", enlace)
    ejecutar(["chown", "-h", f"{meta['usuario']}:www-data", enlace])
    receta.permisos(meta)
    salida = _artisan(meta, "projectsend:admin", f"--name={admin_usuario}", f"--email={correo}",
                      f"--password={admin_clave}")
    if "created" not in salida:
        raise ErrorSitio("no se pudo crear el administrador de ProjectSend")
    # Nombre del sitio y español como idioma ofrecido y predeterminado (los ajustes se guardan en JSON).
    for clave, valor in (("site_name", titulo), ("enabled_locales", ["en", "es"]), ("default_locale", "es")):
        texto = receta.literal(json.dumps(valor, ensure_ascii=False))
        receta.sql(meta, f"INSERT INTO settings (`key`, value, created_at, updated_at) VALUES ('{clave}', {texto}, NOW(), NOW()) "
                         "ON DUPLICATE KEY UPDATE value = VALUES(value), updated_at = NOW();")
    receta.sql(meta, f"UPDATE users SET locale = 'es' WHERE email = {receta.literal(correo)};")
    _artisan(meta, "optimize:clear")
    os.chmod(os.path.join(meta["publico"], ".env"), 0o600)
    return receta.url(meta) + "/login"


def clave_admin(meta, usuario, nueva):
    """Laravel guarda password_hash() (bcrypt) en users.password; el administrador se creó con ese nombre."""
    receta.sql(meta, f"UPDATE users SET password = {receta.literal(receta.hash_clave(nueva))} "
                     f"WHERE name = {receta.literal(usuario)} AND type = 'staff';")


def cron(meta):
    """Cola de trabajos (correo, zips) y tareas programadas, sin servicio permanente.

    «schedule:run» solo lanza lo que toca en el minuto exacto (en punto, a medianoche) y el panel no llama
    cada minuto ni en punto: las tareas horarias y diarias de routes/console.php se lanzan aquí cuando ha
    pasado su periodo desde la última vez."""
    _artisan(meta, "queue:work", "--queue=default,zips", "--stop-when-empty", "--tries=3", "--max-time=150",
             tiempo=200)
    with open(os.path.join(meta["publico"], "routes", "console.php")) as f:
        tareas = re.findall(r"Schedule::command\('([a-z:-]+)'\)->(hourly|daily)\(\)", f.read())
    estado = os.path.join(meta["tmp"], ".projectsend-tareas.json")
    try:
        with open(estado) as f:
            ultimas = json.load(f)
    except (OSError, ValueError):
        ultimas = {}
    ahora = time.time()
    for orden, periodo in tareas:
        if ahora - ultimas.get(orden, 0) >= (3600 if periodo == "hourly" else 86400) - 300:
            ultimas[orden] = ahora
            try:
                _artisan(meta, orden, tiempo=120)
            except ErrorSitio:
                pass  # una tarea fallida no detiene las demás; se reintenta en su próximo periodo
    with open(estado, "w") as f:
        json.dump(ultimas, f)
