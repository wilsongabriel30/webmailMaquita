"""Backdrop CMS — gestor de contenidos sencillo y liviano, heredero de Drupal 7 (GPLv2+). https://backdropcms.org

Paquete oficial adjunto a la versión de GitHub (SHA-256 calculada por GitHub). Se instala sin asistente
con install_backdrop(), lo mismo que hace su core/scripts/install.sh, pero recibiendo los datos por el
entorno y no por la línea de órdenes (así las claves no se ven en la lista de procesos). La
configuración (archivos JSON) y los archivos privados van en la carpeta privada del sitio.
"""

import json
import os
import re

from comun import ErrorSitio, ejecutar

from . import receta

NOMBRE = "Backdrop CMS"
DESCRIPCION = "Sitios institucionales y blogs fáciles de administrar, livianos y con muchos complementos libres."
LICENCIA = "GPLv2+"
CATEGORIA = "Sitios y blogs"
VERIFICACION = "GitHub"
RAIZ_WEB = ""

# Como la configuración de nginx de Drupal 7: código interno sin servir y solo los PHP de entrada; las
# imágenes por estilo se generan en la primera visita.
REGLAS_NGINX = r"""
    location ~* \.(?:engine|inc|info|install|make|module|profile|test|po|theme|tpl|xtmpl|json)$$ { deny all; }
    location ~ ^/(?:core/scripts|files/config_[^/]*)/ { deny all; }
    location ~ ^/(?:README\.md|LICENSE\.txt|core/(?:README\.md|CHANGELOG\.txt|COPYRIGHT\.txt|LICENSE\.txt))$$ { deny all; }
    location ~ ^/files/styles/ {
        expires 30d;
        try_files $$uri /index.php?$$args;
    }
    location ~ ^/(?!index\.php(?:/|$$)|core/(?:update|authorize)\.php(?:/|$$)).*\.php(?:/|$$) { deny all; }
    location = /user/login {
        limit_req zone=sitios_login burst=10 nodelay;
        limit_req zone=sitios_general burst=80 nodelay;
        try_files $$uri /index.php?$$args;
    }
"""

_COMIENZO = r"""<?php
$d = json_decode(getenv('RECETA_DATOS'), TRUE);
$_SERVER += ['HTTP_HOST' => 'default', 'REMOTE_ADDR' => '127.0.0.1', 'SERVER_SOFTWARE' => NULL,
  'REQUEST_METHOD' => 'GET', 'QUERY_STRING' => '', 'REQUEST_URI' => '/', 'HTTP_USER_AGENT' => 'console'];
$_SERVER['PHP_SELF'] = '/index.php';
define('BACKDROP_ROOT', getcwd());
"""

_INSTALADOR = _COMIENZO + r"""
define('MAINTENANCE_MODE', 'install');
require_once './core/includes/install.core.inc';
install_backdrop([
  'parameters' => ['profile' => 'standard', 'langcode' => 'es'],
  'forms' => [
    'install_settings_form' => ['driver' => 'mysql', 'mysql' => ['driver' => 'mysql', 'database' => $d['bd'],
      'username' => $d['bd_usuario'], 'password' => $d['bd_clave'], 'host' => 'localhost', 'port' => ''],
      'op' => 'Save and continue'],
    'install_configure_form' => ['site_name' => $d['titulo'], 'site_mail' => $d['correo'],
      'account' => ['name' => $d['usuario'], 'mail' => $d['correo'], 'pass' => $d['clave']],
      'date_default_timezone' => 'America/Guayaquil', 'clean_url' => 1,
      'update_status_module' => [1 => TRUE, 2 => TRUE], 'op' => 'Save and continue'],
  ],
]);
config_set('system.core', 'site_mail', $d['correo']);
config_set('system.core', 'site_default_country', 'EC');
config_set('system.core', 'file_private_path', $d['privado']);
echo "INSTALADO\n";
"""

# Cambio de clave con la API de usuarios (user_save calcula el hash y limpia la caché).
_CLAVE = _COMIENZO + r"""
require_once './core/includes/bootstrap.inc';
backdrop_bootstrap(BACKDROP_BOOTSTRAP_FULL);
$cuenta = user_load_by_name($d['usuario']);
if (!$cuenta) { fwrite(STDERR, "no existe el usuario\n"); exit(1); }
$cuenta->pass = $d['clave'];
user_save($cuenta);
echo "LISTO\n";
"""


def _php(meta, script, datos):
    return ejecutar(["php", "-d", "memory_limit=512M", "-d", "max_execution_time=0"], entrada=script,
                    como=meta["usuario"], cwd=meta["publico"], tiempo=1200,
                    env_extra={"RECETA_DATOS": json.dumps(datos)})


def instalar(meta, bd, bd_usuario, bd_clave, titulo, correo, admin_usuario, admin_clave):
    receta.preparar(meta, receta.github("backdrop/backdrop", r"backdrop\.zip"), "Backdrop CMS")
    ajustes_ruta = os.path.join(meta["publico"], "settings.php")
    if not os.path.isfile(os.path.join(meta["publico"], "core/includes/install.core.inc")) or not os.path.isfile(ajustes_ruta):
        raise ErrorSitio("el paquete de Backdrop no tiene la estructura esperada")
    with open(ajustes_ruta) as f:
        ajustes = f.read()
    # La configuración activa y de preparación, fuera de la web (por defecto queda en files/config_*).
    for tipo in ("active", "staging"):
        carpeta = receta.privada(meta, f"backdrop-config-{tipo}")
        ajustes, n = re.subn(r"^\$config_directories\['%s'\] = .*$" % tipo,
                             lambda _: f"$config_directories['{tipo}'] = {receta.literal(carpeta)};", ajustes, flags=re.M)
        if n != 1:
            raise ErrorSitio("el settings.php de Backdrop no tiene la estructura esperada")
    # nginx solo entrega a este sitio los nombres que tiene configurados: el control de Host ya está hecho.
    ajustes += "\n$settings['trusted_host_patterns'] = array('.*');\n"
    receta.escribir(meta, "settings.php", ajustes, 0o640)
    salida = _php(meta, _INSTALADOR, {"bd": bd, "bd_usuario": bd_usuario, "bd_clave": bd_clave, "titulo": titulo,
                                      "correo": correo, "usuario": admin_usuario, "clave": admin_clave,
                                      "privado": receta.privada(meta, "backdrop-privado")})
    if "INSTALADO" not in salida:
        raise ErrorSitio("la instalación de Backdrop no se completó")
    os.chmod(ajustes_ruta, 0o440)
    return receta.url(meta) + "/user/login"


def clave_admin(meta, usuario, nueva):
    if "LISTO" not in _php(meta, _CLAVE, {"usuario": usuario, "clave": nueva}):
        raise ErrorSitio("no se pudo cambiar la clave en Backdrop")
