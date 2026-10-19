"""Chamilo — aula virtual (GPLv3). https://chamilo.org

Paquete oficial adjunto a la versión de GitHub (chamilo/chamilo-lms, SHA-256 calculada por GitHub), que ya
trae vendor/ y los recursos compilados. Chamilo no trae instalador por línea de órdenes y su asistente web
no cabe en los límites de PHP-FPM del sitio (necesita más de 256 MB): se ejecuta el último paso del propio
asistente (main/install/index.php, que recibe todos los datos de una vez) con PHP de línea de órdenes.
Al terminar, Chamilo bloquea el asistente (responde 409). La web se sirve desde «public»; .env, config/,
var/ y src/ quedan fuera de la web. Reglas de nginx de su guía de instalación.
"""

import base64
import json
import os

from comun import ErrorSitio, ejecutar

from . import receta

NOMBRE = "Chamilo"
DESCRIPCION = "Aula virtual sencilla: cursos, lecciones, evaluaciones, foros y certificados."
LICENCIA = "GPLv3"
CATEGORIA = "Educación"
VERIFICACION = "GitHub"
RAIZ_WEB = "public"
BD = "mariadb"
INSTALADOR = "/main/install/index.php"

REGLAS_NGINX = r"""
    location = /check.php { deny all; }
    location = /legacy.php { deny all; }
    location ~* ^/(?:build|bundles|documentation|fonts|img|libs|sound)/.*\.php$$ { deny all; }
    # Árboles PHP antiguos: main/ y plugin/ ejecutan sus .php directamente.
    location ~ ^/(?:main|plugin)/.+\.php(?:/|$$) {
        include snippets/fastcgi-php.conf;
        fastcgi_pass unix:$socket;
        fastcgi_read_timeout 300s;
        fastcgi_buffer_size 32k;
        fastcgi_buffers 8 32k;
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


def _asistente(meta, datos):
    """Ejecuta el último paso del asistente oficial con PHP de línea de órdenes: por la web, PHP-FPM del
    sitio (256 MB, 120 s) no alcanza para crear el esquema y cargar los datos iniciales."""
    publico = os.path.join(meta["publico"], "public")
    servidor = {
        "HTTP_HOST": meta["dominio"], "SERVER_NAME": meta["dominio"], "SERVER_PORT": "443" if meta.get("ssl") else "80",
        "REQUEST_SCHEME": "https" if meta.get("ssl") else "http", "REQUEST_METHOD": "POST",
        "SCRIPT_NAME": INSTALADOR, "PHP_SELF": INSTALADOR, "DOCUMENT_ROOT": publico,
        "SCRIPT_FILENAME": publico + INSTALADOR, "REQUEST_URI": INSTALADOR + "?running=1&installType=new",
    }
    if meta.get("ssl"):
        servidor["HTTPS"] = "on"
    carga = base64.b64encode(json.dumps({"servidor": servidor, "post": datos}).encode()).decode()
    codigo = ("<?php $d = json_decode(base64_decode('" + carga + "'), true);\n"
              "$_SERVER = array_merge($_SERVER, $d['servidor']); $_POST = $d['post'];\n"
              "$_GET = ['running' => '1', 'installType' => 'new', 'updateFromConfigFile' => ''];\n"
              "$_REQUEST = array_merge($_GET, $_POST); chdir(dirname($_SERVER['SCRIPT_FILENAME']));\n"
              "require $_SERVER['SCRIPT_FILENAME'];\n")
    receta.php(meta, "-d", "memory_limit=2G", "-d", f"session.save_path={meta['tmp']}", "-d", "display_errors=0",
               entrada=codigo, cwd=os.path.dirname(publico + INSTALADOR), tiempo=1800)


def instalar(meta, bd, bd_usuario, bd_clave, titulo, correo, admin_usuario, admin_clave):
    fuente = receta.github("chamilo/chamilo-lms", r"chamilo-[0-9.]+\.zip")
    receta.preparar(meta, fuente, "Chamilo")
    if not os.path.isfile(os.path.join(meta["publico"], "public" + INSTALADOR)):
        raise ErrorSitio("el paquete de Chamilo no tiene la estructura esperada")
    _asistente(meta, {
        "step6": "1", "dbHostForm": "localhost", "dbPortForm": "3306", "dbUsernameForm": bd_usuario,
        "dbPassForm": bd_clave, "dbNameForm": bd, "encryptPassForm": "bcrypt",
        "loginForm": admin_usuario, "passForm": admin_clave, "adminFirstName": "Administrador",
        "adminLastName": titulo[:60], "emailForm": correo, "adminPhoneForm": "",
        "languageForm": "es", "campusForm": titulo, "institutionForm": titulo,
        "institutionUrlForm": receta.url(meta), "allowSelfReg": "false", "allowSelfRegProf": "0",
        "installationProfile": "", "mailerDsn": "smtp://localhost:25?verify_peer=0",
        "mailerFromEmail": f"no-responder@{meta['dominio']}", "mailerFromName": titulo,
    })
    hay = ejecutar(["mariadb", "--protocol=socket", "-u", "root", "-N", bd, "-e",
                    f"SELECT COUNT(*) FROM `user` WHERE username = {receta.literal(admin_usuario)};"]).strip()
    if hay != "1":
        raise ErrorSitio("la instalación de Chamilo quedó incompleta")
    # Zona horaria de la plataforma y del administrador (el asistente no la pregunta).
    receta.sql(meta, "UPDATE settings SET selected_value = 'America/Guayaquil' WHERE variable = 'timezone'; "
                     f"UPDATE `user` SET timezone = 'America/Guayaquil' WHERE username = {receta.literal(admin_usuario)};")
    # Caché de Symfony preparada desde la línea de órdenes (la primera visita no tiene que generarla).
    receta.php(meta, "-d", "memory_limit=1G", "bin/console", "cache:warmup", "--env=prod", "--no-interaction")
    os.chmod(os.path.join(meta["publico"], ".env"), 0o600)
    web = receta.Web(meta)
    try:
        # El asistente queda bloqueado por Chamilo (409) y la portada responde.
        bloqueado, _, _ = web.pedir(INSTALADOR)
        portada, _, _ = web.pedir("/login")
    finally:
        web.cerrar()
    if bloqueado != "409" or portada != "200":
        raise ErrorSitio(f"Chamilo no responde tras instalarse (HTTP {bloqueado}/{portada})")
    return receta.url(meta) + "/login"


def clave_admin(meta, usuario, nueva):
    """Chamilo guarda password_hash() (bcrypt) en user.password; la sal ya no se usa con bcrypt."""
    receta.sql(meta, f"UPDATE `user` SET password = {receta.literal(receta.hash_clave(nueva))} "
                     f"WHERE username = {receta.literal(usuario)};")
