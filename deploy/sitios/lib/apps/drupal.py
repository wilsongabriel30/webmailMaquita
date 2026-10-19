"""Drupal — gestor de contenidos para portales institucionales (GPLv2+). https://www.drupal.org

Paquete oficial de drupal.org (trae «vendor/»), verificado con la MD5 que publica su historia de
versiones. Drupal no trae instalador de línea de órdenes para MariaDB (el suyo solo usa SQLite) y el
paquete no incluye Drush: se llama a install_drupal() sin interfaz, igual que hacen Drush y su propio
instalador CLI, con el perfil «standard» en español. Configuración exportada y archivos privados van en
la carpeta privada del sitio; solo se ejecutan los PHP de entrada.
"""

import json
import os
import re

from comun import ErrorSitio, ejecutar

from . import descargas, receta

NOMBRE = "Drupal"
DESCRIPCION = "Portales y sitios institucionales con contenidos, usuarios y permisos muy configurables."
LICENCIA = "GPLv2+"
CATEGORIA = "Sitios y blogs"
VERIFICACION = "suma oficial"
RAIZ_WEB = ""
HISTORIA = "https://updates.drupal.org/release-history/drupal/current"
RAMA = "11"  # Drupal 11 funciona con el PHP 8.3/8.4 de los servidores; la 12 se habilitará al probarla.

# Basadas en la configuración de nginx que recomienda Drupal: código interno sin servir, solo se ejecutan
# index.php, update.php y los dos de core que lo necesitan; las imágenes por estilo y los CSS/JS
# agregados se generan en la primera visita (si no existen, los crea index.php).
REGLAS_NGINX = r"""
    location ~* \.(?:engine|inc|install|make|module|profile|po|theme|twig|tpl|xtmpl|yml|yaml)$$ { deny all; }
    location ~ ^/(?:vendor|core/(?:scripts|tests|lib)|recipes)/ { deny all; }
    location ~ ^/(?:composer\.(?:json|lock)|web\.config|INSTALL\.txt|README\.md|example\.gitignore)$$ { deny all; }
    location ~ ^/sites/[^/]+/files/(?:styles|css|js)/ {
        expires 30d;
        try_files $$uri /index.php?$$args;
    }
    location ~ ^/(?!(?:index|update)\.php(?:/|$$)|core/(?:authorize|rebuild)\.php(?:/|$$)).*\.php(?:/|$$) { deny all; }
    location = /user/login {
        limit_req zone=sitios_login burst=10 nodelay;
        limit_req zone=sitios_general burst=80 nodelay;
        try_files $$uri /index.php?$$args;
    }
"""

# install_drupal() sin interfaz (como Drush site:install). Los datos llegan en RECETA_DATOS.
_INSTALADOR = r"""<?php
$d = json_decode(getenv('RECETA_DATOS'), TRUE);
$loader = require 'autoload.php';
require_once 'core/includes/install.core.inc';
$mysql = 'Drupal\\mysql\\Driver\\Database\\mysql';
install_drupal($loader, [
  'interactive' => FALSE,
  'site_path' => 'sites/default',
  'parameters' => ['profile' => 'standard', 'langcode' => 'es'],
  'forms' => [
    'install_settings_form' => [
      'driver' => $mysql,
      $mysql => ['database' => $d['bd'], 'username' => $d['bd_usuario'], 'password' => $d['bd_clave'],
                 'host' => 'localhost', 'port' => '3306', 'prefix' => ''],
    ],
    'install_configure_form' => [
      'site_name' => $d['titulo'], 'site_mail' => $d['correo'],
      'account' => ['name' => $d['usuario'], 'mail' => $d['correo'],
                    'pass' => ['pass1' => $d['clave'], 'pass2' => $d['clave']]],
      'date_default_timezone' => 'America/Guayaquil',
      'enable_update_status_module' => TRUE,
      'enable_update_status_emails' => NULL,
    ],
  ],
]);
// Ecuador y semana que empieza el lunes (el instalador no los pregunta).
\Drupal::configFactory()->getEditable('system.date')->set('country.default', 'EC')->set('first_day', 1)->save();
echo "INSTALADO\n";
"""

# Cambio de clave con la propia API de usuarios de Drupal (hash y cachés correctos).
_CLAVE = r"""<?php
use Drupal\Core\DrupalKernel;
use Symfony\Component\HttpFoundation\Request;
$d = json_decode(getenv('RECETA_DATOS'), TRUE);
$loader = require 'autoload.php';
$peticion = Request::create('/', 'GET', [], [], [], ['SCRIPT_NAME' => '/index.php', 'SCRIPT_FILENAME' => getcwd() . '/index.php']);
$kernel = DrupalKernel::createFromRequest($peticion, $loader, 'prod');
$kernel->boot();
$kernel->preHandle($peticion);
$cuenta = user_load_by_name($d['usuario']);
if (!$cuenta) { fwrite(STDERR, "no existe el usuario\n"); exit(1); }
$cuenta->setPassword($d['clave']);
$cuenta->save();
echo "LISTO\n";
"""


def _ultima():
    """Última versión estable y cubierta por los avisos de seguridad de la rama elegida."""
    xml = descargas.texto(HISTORIA, tope=4 * 1048576)
    for bloque in re.findall(r"<release>(.*?)</release>", xml, re.S):
        version = re.search(r"<version>([^<]+)</version>", bloque).group(1)
        if not re.fullmatch(re.escape(RAMA) + r"\.\d+\.\d+", version) or 'covered="1"' not in bloque:
            continue
        m = re.search(r"<url>(https://ftp\.drupal\.org/files/projects/drupal-%s\.tar\.gz)</url>.*?<md5>([0-9a-f]{32})</md5>"
                      % re.escape(version), bloque, re.S)
        if m:
            return receta.Fuente(version, m.group(1), m.group(2), "md5", "suma oficial")
    raise ErrorSitio("no se encontró una versión estable de Drupal con su suma publicada")


def _php(meta, script, datos):
    return ejecutar(["php", "-d", "memory_limit=512M", "-d", "max_execution_time=0"], entrada=script,
                    como=meta["usuario"], cwd=meta["publico"], tiempo=1200,
                    env_extra={"RECETA_DATOS": json.dumps(datos)})


def instalar(meta, bd, bd_usuario, bd_clave, titulo, correo, admin_usuario, admin_clave):
    receta.preparar(meta, _ultima(), "Drupal")
    if not os.path.isfile(os.path.join(meta["publico"], "core/includes/install.core.inc")):
        raise ErrorSitio("el paquete de Drupal no tiene la estructura esperada")
    config = receta.privada(meta, "drupal-config")
    privado = receta.privada(meta, "drupal-privado")
    with open(os.path.join(meta["publico"], "sites/default/default.settings.php")) as f:
        ajustes = f.read()
    # nginx solo entrega a este sitio los nombres que tiene configurados: el control de Host ya está hecho.
    ajustes += (f"\n$settings['config_sync_directory'] = {receta.literal(config)};\n"
                f"$settings['file_private_path'] = {receta.literal(privado)};\n"
                "$settings['trusted_host_patterns'] = ['.*'];\n")
    receta.escribir(meta, "sites/default/settings.php", ajustes, 0o640)
    salida = _php(meta, _INSTALADOR, {"bd": bd, "bd_usuario": bd_usuario, "bd_clave": bd_clave, "titulo": titulo,
                                      "correo": correo, "usuario": admin_usuario, "clave": admin_clave})
    if "INSTALADO" not in salida:
        raise ErrorSitio("la instalación de Drupal no se completó")
    os.chmod(os.path.join(meta["publico"], "sites/default/settings.php"), 0o440)
    os.chmod(os.path.join(meta["publico"], "sites/default"), 0o550)
    return receta.url(meta) + "/user/login"


def clave_admin(meta, usuario, nueva):
    if "LISTO" not in _php(meta, _CLAVE, {"usuario": usuario, "clave": nueva}):
        raise ErrorSitio("no se pudo cambiar la clave en Drupal")
