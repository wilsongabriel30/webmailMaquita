"""Nextcloud — archivos, calendario, contactos y colaboración en la nube propia (AGPLv3). https://nextcloud.com

Paquete oficial de download.nextcloud.com (última versión estable del listado de versiones) verificado con
la SHA-256 que el proyecto publica junto al paquete. Instalación por su propia línea de órdenes
(occ maintenance:install). Los archivos de las personas van en la carpeta privada del sitio, fuera de la
web. Las reglas de nginx son las de la configuración oficial (documentación de administración).
"""

import re

from comun import ErrorSitio, ejecutar

from . import descargas, receta

NOMBRE = "Nextcloud"
DESCRIPCION = "Nube propia: archivos, calendario, contactos y trabajo en equipo, sin depender de terceros."
LICENCIA = "AGPLv3"
CATEGORIA = "Archivos y galerías"
VERIFICACION = "suma oficial"
RAIZ_WEB = ""
BD = "mariadb"
VERSIONES = "https://download.nextcloud.com/server/releases/"

# Configuración oficial de nginx de Nextcloud, adaptada a la plantilla común (que ya trae «location /» y
# las reglas de archivos ocultos). Solo se ejecutan los PHP de entrada; el resto pasa por index.php.
REGLAS_NGINX = r"""
    client_body_timeout 300s;
    location = /robots.txt { allow all; log_not_found off; access_log off; }
    location ^~ /.well-known {
        location = /.well-known/carddav { return 301 /remote.php/dav/; }
        location = /.well-known/caldav { return 301 /remote.php/dav/; }
        location /.well-known/pki-validation { try_files $$uri $$uri/ =404; }
        return 301 /index.php$$request_uri;
    }
    location ~ ^/(?:build|tests|config|lib|3rdparty|templates|data)(?:$$|/) { return 404; }
    location ~ ^/(?:\.|autotest|occ|issue|indie|db_|console) { return 404; }
    location ~ \.php(?:$$|/) {
        rewrite ^/(?!index|remote|public|cron|core\/ajax\/update|status|ocs\/v[12]|updater\/.+|ocs-provider\/.+) /index.php$$request_uri;
        include snippets/fastcgi-php.conf;
        fastcgi_param modHeadersAvailable true;
        fastcgi_param front_controller_active true;
        fastcgi_pass unix:$socket;
        fastcgi_read_timeout 300s;
        fastcgi_request_buffering off;
        fastcgi_max_temp_file_size 0;
    }
    location /remote { return 301 /remote.php$$request_uri; }
"""


def _fuente():
    """Última versión estable del listado oficial, con su suma publicada."""
    versiones = re.findall(r'href="nextcloud-(\d+\.\d+\.\d+)\.zip"', descargas.texto(VERSIONES))
    if not versiones:
        raise ErrorSitio("no se encontró una versión estable de Nextcloud")
    version = max(versiones, key=lambda v: tuple(map(int, v.split("."))))
    enlace = f"{VERSIONES}nextcloud-{version}.zip"
    suma = receta.suma_publicada(enlace + ".sha256", f"nextcloud-{version}.zip")
    return receta.Fuente(version, enlace, suma, "sha256", "suma oficial")


def _occ(meta, *args, env=None, tiempo=900):
    # APCu es la caché local: la línea de órdenes también tiene que poder usarla.
    return ejecutar(["php", "-d", "memory_limit=512M", "-d", "apc.enable_cli=1", "occ", "--no-interaction", *args],
                    como=meta["usuario"], cwd=meta["publico"], tiempo=tiempo, env_extra=env)


def instalar(meta, bd, bd_usuario, bd_clave, titulo, correo, admin_usuario, admin_clave):
    receta.preparar(meta, _fuente(), "Nextcloud")
    datos = receta.privada(meta, "nextcloud-datos")
    _occ(meta, "maintenance:install", "--database=mysql", "--database-host=localhost", f"--database-name={bd}",
         f"--database-user={bd_usuario}", f"--database-pass={bd_clave}", f"--admin-user={admin_usuario}",
         f"--admin-pass={admin_clave}", f"--admin-email={correo}", f"--data-dir={datos}", tiempo=1200)
    dominios = [meta["dominio"]] + ([f"www.{meta['dominio']}"] if meta.get("www") else [])
    ajustes = [(f"trusted_domains {i}", d) for i, d in enumerate(dominios)] + [
        ("overwrite.cli.url", receta.url(meta)), ("default_language", "es"), ("default_locale", "es_EC"),
        ("default_phone_region", "EC"), ("logtimezone", "America/Guayaquil"),
        ("memcache.local", "\\OC\\Memcache\\APCu"), ("maintenance_window_start", "6")]
    for clave, valor in ajustes:
        _occ(meta, "config:system:set", *clave.split(), f"--value={valor}")
    _occ(meta, "background:cron")
    if "installed' => true" not in open(f"{meta['publico']}/config/config.php").read():
        raise ErrorSitio("la instalación de Nextcloud quedó incompleta")
    ejecutar(["chmod", "640", f"{meta['publico']}/config/config.php"])
    return receta.url(meta) + "/login"


def clave_admin(meta, usuario, nueva):
    _occ(meta, "user:resetpassword", "--password-from-env", usuario, env={"OC_PASS": nueva})


def cron(meta):
    ejecutar(["php", "-d", "apc.enable_cli=1", "-f", "cron.php"], como=meta["usuario"], cwd=meta["publico"], tiempo=280)
