"""LimeSurvey — encuestas en línea con muchos tipos de pregunta y resultados exportables (GPLv2+).
https://www.limesurvey.org

Paquete oficial de download.limesurvey.org (la última versión estable que anuncia su página de descargas),
verificado con la SHA-256 que el proyecto publica junto al archivo. La rama 6 dejó de tener soporte el
31/08/2026, por eso se instala la 7. Instalación por su propia línea de órdenes
(application/commands/console.php install) con application/config/config.php escrito por el panel.
"""

import os
import re

from comun import ErrorSitio

from . import descargas, receta

NOMBRE = "LimeSurvey"
DESCRIPCION = "Encuestas en línea: muchos tipos de pregunta, invitaciones por correo y resultados en Excel o SPSS."
LICENCIA = "GPLv2+"
CATEGORIA = "Encuestas y marketing"
VERIFICACION = "suma oficial"
RAIZ_WEB = ""
DESCARGAS = "https://community.limesurvey.org/downloads/"

# Lo mismo que niega su .htaccess oficial (Apache), más el instalador y los PHP de las subidas.
REGLAS_NGINX = r"""
    location ^~ /application/ { deny all; }
    location ^~ /locale/ { deny all; }
    location ^~ /vendor/ { deny all; }
    location ^~ /docs/ { deny all; }
    location ^~ /installer/ { deny all; }
    location ^~ /tmp/runtime/ { deny all; }
    location ~ ^/upload/.*(?:\.php|/fu_[a-z0-9_]*)$$ { deny all; }
    location ~ ^/(?:setdebug\.php|open-api-gen\.php|composer\.(?:json|lock)|package\.json|publiccode\.yml|README\.md|SECURITY\.md)$$ { deny all; }
"""


def _fuente():
    pagina = descargas.texto(DESCARGAS)
    base = r"https://download\.limesurvey\.org/latest-master/limesurvey(\d+\.\d+\.\d+)\+(\d+)"
    m = re.search(base + r"\.zip", pagina)
    if not m:
        raise ErrorSitio("la página de descargas de LimeSurvey no muestra la versión estable")
    version, compilacion = m.groups()
    archivo = f"https://download.limesurvey.org/latest-master/limesurvey{version}%2B{compilacion}"
    sha = receta.suma_publicada(archivo + "-sha256-checksum.txt")
    return receta.Fuente(version, archivo + ".zip", sha, "sha256", "suma oficial")


def _cadena(texto):
    return "'" + str(texto).replace("\\", "\\\\").replace("'", "\\'") + "'"


def _consola(meta, *args):
    return receta.php(meta, "application/commands/console.php", *args)


def instalar(meta, bd, bd_usuario, bd_clave, titulo, correo, admin_usuario, admin_clave):
    receta.preparar(meta, _fuente(), "LimeSurvey")
    if not os.path.isfile(os.path.join(meta["publico"], "application", "commands", "console.php")):
        raise ErrorSitio("el paquete de LimeSurvey no tiene la estructura esperada")
    config = f"""<?php if (!defined('BASEPATH')) exit('No direct script access allowed');
// Generado por el panel de hospedaje.
return array(
    'components' => array(
        'db' => array(
            'connectionString' => 'mysql:host=localhost;port=3306;dbname={bd};',
            'emulatePrepare' => true,
            'username' => {_cadena(bd_usuario)},
            'password' => {_cadena(bd_clave)},
            'charset' => 'utf8mb4',
            'tablePrefix' => 'lime_',
        ),
        'urlManager' => array('urlFormat' => 'path', 'rules' => array(), 'showScriptName' => false),
    ),
    'config' => array(
        'debug' => 0,
        'debugsql' => 0,
        'mysqlEngine' => 'INNODB',
        'defaultlang' => 'es',
        'displayTimezone' => 'America/Guayaquil',
        'sitename' => {_cadena(titulo)},
        'siteadminname' => {_cadena(titulo)},
        'siteadminemail' => {_cadena(correo)},
        'siteadminbounce' => {_cadena(correo)},
    ),
);
"""
    receta.escribir(meta, "application/config/config.php", config)
    salida = _consola(meta, "install", admin_usuario, admin_clave, titulo, correo, "verbose")
    if "All done" not in salida:
        raise ErrorSitio("LimeSurvey: " + (salida.strip().splitlines() or ["la instalación no terminó"])[-1][:300])
    receta.permisos(meta)
    return receta.url(meta) + "/admin"


def clave_admin(meta, usuario, nueva):
    salida = _consola(meta, "resetpassword", usuario, nueva)
    if "was set" not in salida:
        raise ErrorSitio("LimeSurvey no cambió la contraseña")
