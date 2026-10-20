"""Dolibarr — ERP y CRM para organizaciones pequeñas (GPLv3). https://www.dolibarr.org

Distribución oficial en SourceForge (enlazada desde dolibarr.org): paquete .zip de la última versión
publicada en GitHub, verificado con la suma que SourceForge publica para ese archivo. Instalación por la
línea de órdenes de sus propios pasos (install/step1, step2 y step5, como su imagen oficial de
contenedor). La web se sirve desde «htdocs»; los documentos van en la carpeta privada del sitio y el
instalador queda bloqueado (install.lock) y cerrado en nginx.
"""

import json
import os
import re
import tempfile
import urllib.parse

from comun import ErrorSitio, ejecutar

from . import descargas

NOMBRE = "Dolibarr"
DESCRIPCION = "ERP y CRM: contactos, facturas, inventario, proyectos y más."
LICENCIA = "GPLv3"
RAIZ_WEB = "htdocs"
SF = "https://sourceforge.net/projects/dolibarr"

REGLAS_NGINX = r"""
    location ^~ /install/ { deny all; }
    location ^~ /conf/ { deny all; }
    location ~* ^/(?:custom/.*/)?(?:.*\.(?:sql|lock|log)|filelist-.*\.xml)$$ { deny all; }
"""


def _ultima():
    """(versión, md5) del .zip de la última versión estable."""
    datos = json.loads(descargas.texto("https://api.github.com/repos/Dolibarr/dolibarr/releases/latest"))
    version = datos.get("tag_name", "")
    if datos.get("prerelease") or not re.fullmatch(r"\d+\.\d+\.\d+", version):
        raise ErrorSitio("la última versión publicada de Dolibarr no es estable")
    ruta = urllib.parse.quote(f"/Dolibarr ERP-CRM/{version}")
    rss = descargas.texto(f"{SF}/rss?path={ruta}")
    m = re.search(r"dolibarr-%s\.zip\]\]></title>.*?<media:hash algo=\"md5\">([0-9a-f]{32})</media:hash>"
                  % re.escape(version), rss, re.S)
    if not m:
        raise ErrorSitio("SourceForge no publica la suma del paquete de Dolibarr")
    return version, m.group(1)


def _datos(meta):
    return os.path.join(meta["tmp"], "documentos")


def instalar(meta, bd, bd_usuario, bd_clave, titulo, correo, admin_usuario, admin_clave):
    version, md5 = _ultima()
    url = f"{SF}/files/{urllib.parse.quote(f'Dolibarr ERP-CRM/{version}/dolibarr-{version}.zip')}/download"
    with tempfile.TemporaryDirectory() as tmp:
        paquete = os.path.join(tmp, "dolibarr.zip")
        descargas.descargar(url, paquete)
        descargas.comprobar(paquete, md5, "md5", "Dolibarr")
        descargas.extraer(paquete, meta["publico"])
    htdocs = os.path.join(meta["publico"], "htdocs")
    if not os.path.exists(os.path.join(htdocs, "install", "step1.php")):
        raise ErrorSitio("el paquete de Dolibarr no tiene la estructura esperada")
    conf = os.path.join(htdocs, "conf", "conf.php")
    open(conf, "a").close()
    datos = _datos(meta)
    os.makedirs(datos, exist_ok=True)
    ejecutar(["chown", "-R", f"{meta['usuario']}:www-data", meta["publico"]])
    ejecutar(["chmod", "-R", "u+rwX,g+rX,g-w,o-rwx", meta["publico"]])
    ejecutar(["chown", "-R", f"{meta['usuario']}:{meta['usuario']}", datos])
    os.chmod(datos, 0o700)
    sitio_url = ("https://" if meta.get("ssl") else "http://") + meta["dominio"]
    instalacion = os.path.join(htdocs, "install")

    def paso(*args):
        ejecutar([receta.cli_php(meta), *args], como=meta["usuario"], cwd=instalacion, tiempo=900)

    # step1: conf.php y base de datos (ya creada por el panel: no crear base ni usuario).
    paso("step1.php", "set", "es_ES", htdocs, datos, sitio_url, "", "", "mysqli", "localhost", bd, bd_usuario,
         bd_clave, "3306", "llx_", "", "")
    paso("step2.php", "set", "es_ES")
    # step5: administrador y bloqueo del instalador (install.lock en documentos).
    paso("step5.php", "0", "0", "es_ES", "set", admin_usuario, admin_clave, admin_clave, "1")
    ejecutar(["chmod", "440", conf])
    if not os.path.exists(os.path.join(datos, "install.lock")):
        raise ErrorSitio("la instalación de Dolibarr no se completó (falta install.lock)")
    from aplicaciones import _mariadb

    # Nombre y correo de la organización en la configuración inicial.
    for clave, valor in (("MAIN_INFO_SOCIETE_NOM", titulo), ("MAIN_INFO_SOCIETE_MAIL", correo)):
        v = valor.replace("\\", "").replace("'", "''")
        _mariadb(f"INSERT INTO `{bd}`.llx_const (name, entity, value, type, visible) VALUES ('{clave}', 1, '{v}', 'chaine', 0) "
                 f"ON DUPLICATE KEY UPDATE value = '{v}';")
    meta["app_version"] = version
    return sitio_url + "/"


def cambiar_url(meta):
    """Dolibarr guarda su dirección en conf/conf.php ($dolibarr_main_url_root). Sus enlaces son relativos:
    responde también por los alias sin redirigir."""
    from . import receta

    nueva = receta.url(meta)
    receta.reemplazar(meta, "htdocs/conf/conf.php", r"^(\$dolibarr_main_url_root\s*=\s*)'[^']*';",
                      lambda m: f"{m.group(1)}'{nueva}';")


def clave_admin(meta, usuario, nueva):
    """Dolibarr guarda password_hash() en llx_user.pass_crypted."""
    import subprocess

    r = subprocess.run(["php", "-r", "echo password_hash(stream_get_contents(STDIN), PASSWORD_DEFAULT);"],
                       input=nueva, capture_output=True, text=True, timeout=30)
    if r.returncode != 0 or not r.stdout.startswith("$2y$"):
        raise ErrorSitio("no se pudo calcular la contraseña")
    from aplicaciones import _mariadb

    _mariadb(f"UPDATE `{meta['bd']}`.llx_user SET pass_crypted = '{r.stdout}', pass = NULL WHERE login = '{usuario}';")
