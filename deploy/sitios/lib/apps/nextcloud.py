"""Nextcloud — archivos, calendario, contactos y colaboración en la nube propia (AGPLv3). https://nextcloud.com

Paquete oficial de download.nextcloud.com (última versión estable del listado de versiones) verificado con
la SHA-256 que el proyecto publica junto al paquete. Instalación por su propia línea de órdenes
(occ maintenance:install). Los archivos de las personas van en la carpeta privada del sitio, fuera de la
web. Las reglas de nginx son las de la configuración oficial (documentación de administración).
"""

import re
import shutil

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
# Cortafuegos: Nextcloud usa WebDAV y REST (PROPFIND, PUT, DELETE…), que el perfil común no admite; y en
# WebDAV (remote.php, public.php) los archivos suben como cuerpo crudo de hasta 10 MB por trozo, así que
# ahí no se analiza el cuerpo (sí la ruta, las cabeceras y los parámetros).
REGLAS_NGINX = r"""
    client_body_timeout 300s;
    index index.php index.html /index.php$$request_uri;
    modsecurity_rules 'SecRuleRemoveById 911100';
    location = /robots.txt { allow all; log_not_found off; access_log off; }
    location ^~ /.well-known {
        location = /.well-known/carddav { return 301 /remote.php/dav/; }
        location = /.well-known/caldav { return 301 /remote.php/dav/; }
        location /.well-known/pki-validation { try_files $$uri $$uri/ =404; }
        return 301 /index.php$$request_uri;
    }
    location ~ ^/(?:build|tests|config|lib|3rdparty|templates|data)(?:$$|/) { return 404; }
    location ~ ^/(?:\.(?!well-known)|autotest|occ|issue|indie|db_|console) { return 404; }
    location ~ ^/(?:remote|public)\.php(?:$$|/) {
        modsecurity_rules 'SecRequestBodyAccess Off';
        modsecurity_rules 'SecRuleRemoveById 920420';
        include snippets/fastcgi-php.conf;
        fastcgi_param modHeadersAvailable true;
        fastcgi_param front_controller_active true;
        fastcgi_pass unix:$socket;
        fastcgi_read_timeout 300s;
        fastcgi_request_buffering off;
        fastcgi_max_temp_file_size 0;
    }
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
    # Recursos estáticos: los que no existen como archivo (vistas previas, temas) los genera index.php.
    location ~* \.mjs$$ { types { } default_type text/javascript; expires 7d; try_files $$uri /index.php$$request_uri; }
    location ~* \.(?:css|js|svg|gif|ico|jpg|jpeg|png|webp|wasm|tflite|map|ogg|flac|woff2?)$$ {
        expires 7d;
        access_log off;
        try_files $$uri /index.php$$request_uri;
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
    try:
        _occ(meta, "maintenance:install", "--database=mysql", "--database-host=localhost", f"--database-name={bd}",
             f"--database-user={bd_usuario}", f"--database-pass={bd_clave}", f"--admin-user={admin_usuario}",
             f"--admin-pass={admin_clave}", f"--admin-email={correo}", f"--data-dir={datos}", tiempo=1200)
        dominios = [meta["dominio"]] + ([f"www.{meta['dominio']}"] if meta.get("www") else [])
        ajustes = [(f"trusted_domains {i}", d) for i, d in enumerate(dominios)] + [
            ("overwrite.cli.url", receta.url(meta)), ("default_language", "es"), ("default_locale", "es_EC"),
            ("default_phone_region", "EC"), ("logtimezone", "America/Guayaquil"),
            ("memcache.local", "\\OC\\Memcache\\APCu"), ("maintenance_window_start", "6"),
            ("mail_smtpmode", "smtp"), ("mail_smtphost", "localhost"), ("mail_smtpport", "25"),
            ("mail_domain", meta["dominio"])]
        for clave, valor in ajustes:
            _occ(meta, "config:system:set", *clave.split(), f"--value={valor}")
        # Correo por el servidor de correo local: su certificado es del nombre del servidor, no de «localhost».
        for opcion in ("verify_peer", "verify_peer_name"):
            _occ(meta, "config:system:set", "mail_smtpstreamoptions", "ssl", opcion, "--type=boolean", "--value=false")
        _occ(meta, "background:cron")
        _occ(meta, "maintenance:repair", "--include-expensive")  # migraciones de tipos MIME (rápidas con la base vacía)
        if "installed' => true" not in open(f"{meta['publico']}/config/config.php").read():
            raise ErrorSitio("la instalación de Nextcloud quedó incompleta")
        ejecutar(["chmod", "640", f"{meta['publico']}/config/config.php"])
    except Exception:
        # El panel vacía la carpeta pública y la base; los datos privados también, para poder reintentar.
        shutil.rmtree(datos, ignore_errors=True)
        raise
    return receta.url(meta) + "/login"


def clave_admin(meta, usuario, nueva):
    _occ(meta, "user:resetpassword", "--password-from-env", usuario, env={"OC_PASS": nueva})


def cron(meta):
    ejecutar(["php", "-d", "apc.enable_cli=1", "-f", "cron.php"], como=meta["usuario"], cwd=meta["publico"], tiempo=280)
