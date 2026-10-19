"""EspoCRM — CRM: contactos, cuentas, oportunidades, correo y calendario (AGPLv3). https://www.espocrm.com

Paquete oficial adjunto a la versión de GitHub (SHA-256 calculada por GitHub). Se instala con el instalador
por línea de órdenes que trae el propio paquete (install/cli.php, el mismo que usa su imagen oficial de
contenedor), paso a paso. La web se sirve desde «public/»: datos, configuración y código quedan fuera; el
cliente (client/) se publica con un enlace dentro de public/, como pide su documentación de nginx.
"""

import os
import shutil
import urllib.parse

from comun import ErrorSitio, ejecutar

from . import receta

NOMBRE = "EspoCRM"
DESCRIPCION = "Gestión de clientes (CRM): contactos, empresas, oportunidades de venta, correo y calendario."
LICENCIA = "AGPLv3"
CATEGORIA = "Gestión y CRM"
VERIFICACION = "GitHub"
RAIZ_WEB = "public"
BD = "mariadb"

# Reglas de su documentación de nginx: la API y el portal pasan por su index.php; el instalador web no se sirve.
REGLAS_NGINX = r"""
    location ^~ /install/ { deny all; }
    location ^~ /client/ { expires 7d; access_log off; try_files $$uri =404; }
    location /api/v1/portal-access/ { try_files $$uri /api/v1/portal-access/index.php$$is_args$$args; }
    location /api/v1/ { try_files $$uri /api/v1/index.php$$is_args$$args; }
    location /portal/ { try_files $$uri /portal/index.php$$is_args$$args; }
    location = /web.config { deny all; }
"""


def _cli(meta, accion, **datos):
    """Un paso del instalador. Responde siempre con código 0: el error viene en el texto («Error: …»)."""
    sesiones = receta.privada(meta, "sesiones-instalacion")
    args = ["-d", f"session.save_path={sesiones}", "install/cli.php", "-a", accion]
    if datos:
        args += ["-d", urllib.parse.urlencode(datos)]
    salida = receta.php(meta, *args)
    if "Error:" in salida:
        raise ErrorSitio(f"el instalador de EspoCRM se detuvo en «{accion}»: {salida.strip()[:300]}")


def instalar(meta, bd, bd_usuario, bd_clave, titulo, correo, admin_usuario, admin_clave):
    fuente = receta.github("espocrm/espocrm", r"EspoCRM-[0-9.]+\.zip")
    receta.preparar(meta, fuente, "EspoCRM")
    if not os.path.isfile(os.path.join(meta["publico"], "install", "cli.php")):
        raise ErrorSitio("el paquete de EspoCRM no tiene la estructura esperada")
    # El cliente (JS, CSS, plantillas) vive fuera de public/: se publica con un enlace del mismo dueño.
    enlace = os.path.join(meta["publico"], RAIZ_WEB, "client")
    os.symlink("../client", enlace)
    os.lchown(enlace, *_ids(meta["usuario"]))
    sitio_url = receta.url(meta)
    _cli(meta, "step1", **{"user-lang": "es_ES"})
    _cli(meta, "setupConfirmation", **{"host-name": "localhost", "db-name": bd, "db-user-name": bd_usuario,
                                       "db-user-password": bd_clave, "db-platform": "Mysql"})
    _cli(meta, "checkPermission")
    _cli(meta, "saveSettings", **{"site-url": sitio_url})
    _cli(meta, "buildDatabase")
    _cli(meta, "createUser", **{"user-name": admin_usuario, "user-pass": admin_clave})
    _cli(meta, "savePreferences", dateFormat="DD/MM/YYYY", timeFormat="HH:mm", timeZone="America/Guayaquil",
         weekStart="1", defaultCurrency="USD", thousandSeparator=".", decimalMark=",", language="es_ES")
    _cli(meta, "finish")
    if "'isInstalled' => true" not in open(os.path.join(meta["publico"], "data", "config-internal.php")).read():
        raise ErrorSitio("la instalación de EspoCRM quedó incompleta")
    for nombre, valor in (("applicationName", titulo), ("outboundEmailFromAddress", correo),
                          ("outboundEmailFromName", titulo)):
        receta.php(meta, "command.php", "config:set", nombre, valor)
    # Correo del administrador (EspoCRM lo guarda en sus propias tablas: se pasa por su modelo).
    receta.php(meta, "-r", _PHP_CORREO, admin_usuario, correo)
    receta.quitar(meta, os.path.join(RAIZ_WEB, "install"))
    shutil.rmtree(os.path.join(meta["tmp"], "sesiones-instalacion"), ignore_errors=True)
    for archivo in ("config.php", "config-internal.php"):
        os.chmod(os.path.join(meta["publico"], "data", archivo), 0o600)
    return sitio_url + "/"


_PHP_CORREO = r"""
require 'bootstrap.php';
$app = new \Espo\Core\Application();
$app->setupSystemUser();
$em = $app->getContainer()->getByClass(\Espo\ORM\EntityManager::class);
$u = $em->getRDBRepository('User')->where(['userName' => $argv[1]])->findOne();
if (!$u) { fwrite(STDERR, "usuario no encontrado\n"); exit(1); }
$u->set('emailAddress', $argv[2]);
$em->saveEntity($u);
"""


def _ids(usuario):
    import pwd

    p = pwd.getpwnam(usuario)
    return p.pw_uid, p.pw_gid


def clave_admin(meta, usuario, nueva):
    salida = receta.php(meta, "command.php", "set-password", usuario, entrada=nueva + "\n")
    if "has been changed" not in salida:
        raise ErrorSitio("EspoCRM no cambió la contraseña")


def cron(meta):
    receta.php(meta, "cron.php", tiempo=280)
