"""Matomo — estadísticas de visitas sin entregar los datos a terceros (GPLv3). https://matomo.org

Paquete oficial adjunto a la versión de GitHub de matomo-org (SHA-256 calculada por GitHub). Matomo
no trae instalador por línea de órdenes: se recorre su propio asistente web (Installation) desde el
servidor, con las mismas peticiones que haría una persona. IP de las visitas anonimizada por defecto.
"""

import os
import shutil
import subprocess
import tempfile

from comun import ErrorSitio, ejecutar

from . import descargas

NOMBRE = "Matomo"
DESCRIPCION = "Estadísticas de visitas de sus sitios, sin entregar los datos a terceros."
LICENCIA = "GPLv3"
RAIZ_WEB = ""

# Reglas de la configuración oficial de nginx de Matomo (matomo-org/matomo-nginx): solo se ejecutan
# los PHP de entrada; config, tmp, core, lang, librerías y complementos no se sirven (salvo sus
# recursos estáticos).
REGLAS_NGINX = r"""
    location ~ ^/(index|matomo|piwik|js/index)\.php$$ {
        include snippets/fastcgi-php.conf;
        fastcgi_pass unix:$socket;
        fastcgi_read_timeout 300s;
    }
    location ~* \.php$$ { deny all; }
    location ~* \.(?:gif|ico|jpg|jpeg|png|svg|webp|js|css|map|woff2?|ttf|eot)$$ { expires 7d; try_files $$uri =404; }
    location ~ ^/(?:config|tmp|core|lang|libs|vendor|plugins|misc|node_modules)/ { deny all; }
    location ~ /(?:[^/]*\.md|LEGALNOTICE|LICENSE)$$ { default_type text/plain; }
"""


def _peticion(meta, ruta, datos=None, cookies=None):
    """Petición al asistente como la haría el navegador (curl --resolve contra este servidor)."""
    url = f"http://{meta['dominio']}/index.php?{ruta}"
    orden = ["curl", "-s", "-o", "/dev/null", "-w", "%{http_code} %{redirect_url}", "--max-time", "300",
             "--resolve", f"{meta['dominio']}:80:127.0.0.1", "-b", cookies, "-c", cookies]
    for clave, valor in (datos or {}).items():
        orden += ["--data-urlencode", f"{clave}={valor}"]
    r = subprocess.run(orden + [url], capture_output=True, text=True, timeout=330)
    codigo, _, destino = r.stdout.partition(" ")
    return codigo, destino


def instalar(meta, bd, bd_usuario, bd_clave, titulo, correo, admin_usuario, admin_clave):
    import sitio

    version, url, sha = descargas.github_ultima("matomo-org/matomo", r"matomo-[0-9.]+\.zip")
    with tempfile.TemporaryDirectory() as tmp:
        paquete = os.path.join(tmp, "matomo.zip")
        descargas.descargar(url, paquete)
        descargas.comprobar(paquete, sha, "sha256", "Matomo")
        # El zip trae «matomo/» y además «How to install Matomo.html» suelto: se extrae aparte y se
        # sube solo el contenido de «matomo/».
        extraido = os.path.join(tmp, "extraido")
        descargas.extraer(paquete, extraido, quitar_prefijo=False)
        origen = os.path.join(extraido, "matomo")
        if not os.path.isfile(os.path.join(origen, "index.php")):
            raise ErrorSitio("el paquete de Matomo no tiene la estructura esperada")
        for nombre in os.listdir(origen):
            shutil.move(os.path.join(origen, nombre), meta["publico"])
    ejecutar(["chown", "-R", f"{meta['usuario']}:www-data", meta["publico"]])
    ejecutar(["chmod", "-R", "u+rwX,g+rX,g-w,o-rwx", meta["publico"]])
    # El asistente se recorre por HTTP: el vhost tiene que servir ya Matomo con sus reglas.
    sitio.escribir_vhost(meta)
    sitio.recargar_nginx()
    sitio_url = ("https://" if meta.get("ssl") else "http://") + meta["dominio"]
    with tempfile.NamedTemporaryFile(dir=meta["tmp"], prefix=".instalacion-") as cookies:
        pasos = [
            ("action=systemCheck", None, ""),
            ("action=databaseSetup", {"host": "localhost", "username": bd_usuario, "password": bd_clave, "dbname": bd,
                                      "tables_prefix": "matomo_", "adapter": "PDO\\MYSQL", "schema": "Mariadb",
                                      "submit": "Siguiente"}, "tablesCreation"),
            ("action=tablesCreation&module=Installation", None, ""),
            ("action=setupSuperUser&module=Installation", {"login": admin_usuario, "password": admin_clave,
                                                          "password_bis": admin_clave, "email": correo,
                                                          "subscribe_newsletter_piwikorg": "0",
                                                          "subscribe_newsletter_professionalservices": "0",
                                                          "submit": "Siguiente"}, "firstWebsiteSetup"),
            ("action=firstWebsiteSetup&module=Installation", {"siteName": titulo, "url": sitio_url,
                                                             "timezone": "America/Guayaquil", "ecommerce": "0",
                                                             "submit": "Siguiente"}, "trackingCode"),
            ("action=trackingCode&module=Installation&site_idSite=1", None, ""),
            ("action=finished&module=Installation&site_idSite=1", {"anonymise_ip": "1", "setup_geoip2": "0",
                                                                    "submit": "Continuar"}, "index.php"),
        ]
        for ruta, datos, esperado in pasos:
            codigo, destino = _peticion(meta, ruta, datos, cookies.name)
            if codigo not in ("200", "302") or (esperado and esperado not in destino):
                raise ErrorSitio(f"el asistente de Matomo se detuvo en «{ruta.split('&')[0]}» (HTTP {codigo})")
    config = os.path.join(meta["publico"], "config", "config.ini.php")
    with open(config) as f:
        if "installation_in_progress" in f.read():
            raise ErrorSitio("la instalación de Matomo quedó incompleta")
    os.chmod(config, 0o640)
    meta["app_version"] = version
    return sitio_url + "/"


def clave_admin(meta, usuario, nueva):
    """Matomo guarda password_hash(md5(clave)); se actualiza en su tabla de usuarios."""
    r = subprocess.run(["php", "-r", "echo password_hash(md5(stream_get_contents(STDIN)), PASSWORD_BCRYPT);"],
                       input=nueva, capture_output=True, text=True, timeout=30)
    if r.returncode != 0 or not r.stdout.startswith("$2y$"):
        raise ErrorSitio("no se pudo calcular la contraseña")
    from aplicaciones import _mariadb

    hash_ = r.stdout.replace("'", "")
    _mariadb(f"UPDATE `{meta['bd']}`.`matomo_user` SET password = '{hash_}' WHERE login = '{usuario}';")


def cron(meta):
    """Archivado de informes (Matomo lo omite solo si se hizo hace poco)."""
    url = ("https://" if meta.get("ssl") else "http://") + meta["dominio"]
    ejecutar(["php", "console", "core:archive", f"--url={url}/"], como=meta["usuario"], cwd=meta["publico"], tiempo=280)
