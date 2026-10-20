"""Mautic — automatización de marketing: contactos, segmentos, campañas y envíos de correo (GPLv3).
https://mautic.org

Paquete oficial adjunto a la versión de GitHub (el completo, no el de actualización; SHA-256 calculada
por GitHub). Instalación por su línea de órdenes (bin/console mautic:install). Solo se ejecuta index.php
y no se sirven la configuración (config/), var/ (caché, registros, cola) ni el código. Los segmentos,
campañas y envíos funcionan con sus tareas programadas (cron).
"""

import os
import re

from comun import ErrorSitio

from . import receta

NOMBRE = "Mautic"
DESCRIPCION = "Marketing por correo: contactos, segmentos, campañas automáticas, formularios y boletines."
LICENCIA = "GPLv3"
CATEGORIA = "Encuestas y marketing"
VERIFICACION = "GitHub"
RAIZ_WEB = ""

# Como su .htaccess oficial: solo index.php; de app/ solo los recursos estáticos (Assets) de sus módulos.
REGLAS_NGINX = r"""
    location ~ ^/index\.php(/|$$) {
        include snippets/fastcgi-php.conf;
        fastcgi_pass unix:$socket;
        fastcgi_read_timeout 300s;
    }
    location ~ \.php(/|$$) { deny all; }
    location ~ ^/app/(?!bundles/[^/]+/Assets/|assets/) { deny all; }
    location ~ ^/(?:bin|config|translations|utils|var|vendor|patches|templates|node_modules)/ { deny all; }
    location ~ ^/(?:composer\.(?:json|lock)|package(?:-lock)?\.json|[^/]+\.md|codeception\.yml|deleted_files\.txt)$$ { deny all; }
"""

# Tareas periódicas recomendadas por Mautic, en este orden (los segmentos antes que las campañas).
TAREAS = ("mautic:segments:update", "mautic:campaigns:update", "mautic:campaigns:trigger", "mautic:messages:send",
          "mautic:broadcasts:send", "mautic:import", "mautic:webhooks:process", "mautic:reports:scheduler")


def _consola(meta, *args, tiempo=900):
    return receta.php(meta, "bin/console", *args, "--no-interaction", "--env=prod", tiempo=tiempo)


def _cadena(texto):
    return "'" + str(texto).replace("\\", "\\\\").replace("'", "\\'") + "'"


def instalar(meta, bd, bd_usuario, bd_clave, titulo, correo, admin_usuario, admin_clave):
    fuente = receta.github("mautic/mautic", r"\d+\.\d+\.\d+\.zip")
    receta.preparar(meta, fuente, "Mautic")
    if not os.path.isfile(os.path.join(meta["publico"], "bin", "console")):
        raise ErrorSitio("el paquete de Mautic no tiene la estructura esperada")
    sitio_url = receta.url(meta)
    salida = _consola(meta, "mautic:install", sitio_url, "--force", "--db_driver=pdo_mysql", "--db_host=localhost",
                      "--db_port=3306", f"--db_name={bd}", f"--db_user={bd_usuario}", f"--db_password={bd_clave}",
                      "--db_backup_tables=false", "--admin_firstname=Administrador", f"--admin_lastname={titulo[:40]}",
                      f"--admin_username={admin_usuario}", f"--admin_email={correo}",
                      f"--admin_password={admin_clave}", tiempo=1200)
    local = os.path.join(meta["publico"], "config", "local.php")
    if "Install canceled" in salida or not os.path.isfile(local):
        raise ErrorSitio("Mautic: " + (salida.strip().splitlines() or ["la instalación no terminó"])[-1][:300])
    # Hora de Ecuador, remitente y correo por el servidor local (su certificado no es de «localhost»).
    ajustes = {"default_timezone": "America/Guayaquil", "mailer_from_name": titulo, "mailer_from_email": correo,
               "mailer_dsn": "smtp://localhost:25?verify_peer=0"}
    with open(local) as f:
        texto = f.read().rstrip()
    texto += "\n// Ajustes del panel de hospedaje.\n" + "".join(
        f"$parameters[{_cadena(k)}] = {_cadena(v)};\n" for k, v in ajustes.items())
    receta.escribir(meta, "config/local.php", texto)
    _consola(meta, "cache:clear")
    receta.permisos(meta)
    return sitio_url + "/s/login"


def cambiar_url(meta):
    """site_url de config/local.php (enlaces de correos, formularios y seguimiento); se aplica al limpiar
    su caché."""
    receta.reemplazar(meta, "config/local.php", r"^(\s*'site_url' => )'[^']*',$",
                      lambda c: c.group(1) + _cadena(receta.url(meta)) + ",")
    _consola(meta, "cache:clear")
    receta.permisos(meta)


def clave_admin(meta, usuario, nueva):
    """Mautic guarda bcrypt en su tabla de usuarios."""
    if not re.fullmatch(r"[A-Za-z0-9_]+", usuario):
        raise ErrorSitio("usuario no válido")
    receta.sql(meta, f"UPDATE users SET password = {receta.literal(receta.hash_clave(nueva))} "
                     f"WHERE username = {receta.literal(usuario)};")


def cron(meta):
    fallos = []
    for tarea in TAREAS:
        try:
            _consola(meta, tarea, tiempo=240)
        except ErrorSitio as e:
            fallos.append(f"{tarea}: {e}")
    if fallos:
        raise ErrorSitio("; ".join(fallos)[:500])
