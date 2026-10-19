"""Moodle — aula virtual (GPLv3). https://moodle.org

Paquete oficial de packaging.moodle.org (última rama estable que publica su suma SHA-256), instalación
por su propia línea de órdenes (admin/cli/install.php). Desde Moodle 5.1 la web se sirve desde
«public/»: config.php y el resto del código quedan fuera del alcance de la web. Los datos de Moodle
(moodledata) van en la carpeta privada del sitio.
"""

import os
import re
import tempfile

from comun import ErrorSitio, ejecutar

from . import descargas

NOMBRE = "Moodle"
DESCRIPCION = "Aula virtual: cursos, tareas, evaluaciones y certificados."
LICENCIA = "GPLv3"
RAIZ_WEB = "public"
BASE = "https://download.moodle.org/download.php/direct"

REGLAS_NGINX = r"""
    location = /login/index.php {
        limit_req zone=sitios_login burst=10 nodelay;
        limit_req zone=sitios_general burst=80 nodelay;
        include snippets/fastcgi-php.conf;
        fastcgi_pass unix:$socket;
    }
    # Archivos internos de Moodle que no deben servirse (lista de su documentación de nginx).
    location ~ (/vendor/|/node_modules/|composer\.json|/readme|/README|readme\.txt|/upgrade\.txt|/UPGRADING\.md|db/install\.xml|/fixtures/|/behat/|phpunit\.xml|\.lock|environment\.xml) {
        deny all;
    }
"""


def _ultima_rama():
    """(rama, sha256) de la última rama estable con paquete y suma publicados."""
    for rama in range(520, 499, -1):
        try:
            texto = descargas.texto(f"{BASE}/stable{rama}/moodle-latest-{rama}.tgz.sha256", tope=512)
        except Exception:
            continue
        m = re.search(r"SHA256\(moodle-latest-%d\.tgz\)=\s*([0-9a-f]{64})" % rama, texto)
        if m:
            return rama, m.group(1)
    raise ErrorSitio("no se encontró una versión estable de Moodle con su suma publicada")


def _datos(meta):
    return os.path.join(meta["tmp"], "moodledata")


def instalar(meta, bd, bd_usuario, bd_clave, titulo, correo, admin_usuario, admin_clave):
    rama, sha = _ultima_rama()
    with tempfile.TemporaryDirectory() as tmp:
        paquete = os.path.join(tmp, "moodle.tgz")
        descargas.descargar(f"{BASE}/stable{rama}/moodle-latest-{rama}.tgz", paquete)
        descargas.comprobar(paquete, sha, "sha256", "Moodle")
        descargas.extraer(paquete, meta["publico"])
    if not os.path.exists(os.path.join(meta["publico"], "admin/cli/install.php")):
        raise ErrorSitio("el paquete de Moodle no tiene la estructura esperada")
    ejecutar(["chown", "-R", f"{meta['usuario']}:www-data", meta["publico"]])
    ejecutar(["chmod", "-R", "u+rwX,g+rX,g-w,o-rwx", meta["publico"]])
    datos = _datos(meta)
    os.makedirs(datos, exist_ok=True)
    ejecutar(["chown", "-R", f"{meta['usuario']}:{meta['usuario']}", datos])
    os.chmod(datos, 0o700)
    url = ("https://" if meta.get("ssl") else "http://") + meta["dominio"]
    corto = re.sub(r"[^A-Za-z0-9]", "", titulo)[:20] or "Aula"
    ejecutar([
        "php", "-d", "max_input_vars=5000", "admin/cli/install.php", "--non-interactive", "--agree-license", "--lang=es",
        f"--wwwroot={url}", f"--dataroot={datos}", "--dbtype=mariadb", "--dbhost=localhost",
        f"--dbname={bd}", f"--dbuser={bd_usuario}", f"--dbpass={bd_clave}", "--prefix=mdl_",
        f"--fullname={titulo}", f"--shortname={corto}", f"--adminuser={admin_usuario}",
        f"--adminpass={admin_clave}", f"--adminemail={correo}", f"--supportemail={correo}",
    ], como=meta["usuario"], cwd=meta["publico"], tiempo=1200)
    ejecutar(["chmod", "640", os.path.join(meta["publico"], "config.php")])
    meta["app_version"] = f"rama {rama}"
    return url + "/login/index.php"


def clave_admin(meta, usuario, nueva):
    ejecutar(["php", "-d", "max_input_vars=5000", "admin/cli/reset_password.php", f"--username={usuario}", f"--password={nueva}",
              "--ignore-password-policy"], como=meta["usuario"], cwd=meta["publico"])


def cron(meta):
    ejecutar(["php", "-d", "max_input_vars=5000", "admin/cli/cron.php", "--keep-alive=0"], como=meta["usuario"], cwd=meta["publico"], tiempo=280)
