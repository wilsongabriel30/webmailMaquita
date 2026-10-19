"""Grav — gestor de contenidos de archivos planos, sin base de datos (MIT). https://getgrav.org

Paquete oficial «grav-admin» adjunto a la versión de GitHub (SHA-256 calculada por GitHub), que ya trae
el panel de administración. El administrador se crea con la línea de órdenes de Grav
(bin/plugin login new-user) usando una clave provisional, y luego se guarda el hash de la clave real
directamente en su cuenta: así la clave no aparece en la lista de procesos ni depende de la política de
claves de Grav. Reglas de nginx tomadas de su webserver-configs/nginx.conf.
"""

import json
import os
import secrets

from comun import ErrorSitio, ejecutar

from . import receta

NOMBRE = "Grav"
DESCRIPCION = "Sitios y blogs rápidos sin base de datos: las páginas se guardan como archivos de texto."
LICENCIA = "MIT"
CATEGORIA = "Sitios y blogs"
VERIFICACION = "GitHub"
RAIZ_WEB = ""
BD = None

REGLAS_NGINX = r"""
    location ~* ^/(?:\.git|cache|bin|logs|backup|tmp|tests|webserver-configs)/ { deny all; }
    location ~* ^/user/(?:env/[^/]+/)?config/ { deny all; }
    location ~* ^/user/(?:env/[^/]+/)?accounts/[^/]+/[^/]+\.(?:jpe?g|png|gif|webp|avif|bmp|ico)$$ { try_files $$uri =404; }
    location ~* ^/user/(?:env/[^/]+/)?accounts/ { deny all; }
    location ~* ^/user/(?:env/[^/]+/)?data/.*\.(?:jpe?g|png|gif|webp|avif|bmp|ico|mp4|webm|ogg|ogv|mov|mp3|wav|m4a|flac|pdf)$$ { try_files $$uri =404; }
    location ~* ^/user/(?:env/[^/]+/)?data/ { deny all; }
    location ~* ^/(?:system|vendor)/.*\.(?:txt|xml|md|html?|shtml?|json|ya?ml|php\d?|phar|phtml|pl|py|cgi|twig|sh|bat)$$ { deny all; }
    location ~* ^/user/.*\.(?:txt|md|json|ya?ml|php\d?|phar|phtml|pl|py|cgi|twig|sh|bat)$$ { deny all; }
    location ~ ^/(?:LICENSE\.txt|composer\.(?:lock|json)|now\.json|[A-Z_]+\.md)$$ { deny all; }
    location ~ ^/(?!index\.php(?:/|$$)).*\.php(?:/|$$) { deny all; }
    location ^~ /api/v1/auth/ {
        limit_req zone=sitios_login burst=10 nodelay;
        limit_req zone=sitios_general burst=80 nodelay;
        try_files $$uri /index.php?$$args;
    }
    location ~* /_app/immutable/.*\.(?:js|css|woff2?)$$ {
        try_files $$uri =404;
        access_log off;
        add_header Cache-Control "public, max-age=31536000, immutable" always;
    }
    # Grav genera algunas imágenes y recursos desde index.php cuando aún no existen.
    location ~* \.(?:jpe?g|png|gif|webp|avif|bmp|ico|svg|mp4|webm|ogg|ogv|mov|mp3|wav|m4a|flac|css|js|woff2?|ttf|otf|eot)$$ {
        try_files $$uri $$uri/ /index.php?$$args;
        expires 30d;
        access_log off;
    }
"""

# Configuración inicial (sitio en español, zona horaria, sin mostrar errores) y hash de la clave en la
# cuenta, con el YAML de Symfony que trae el propio Grav.
_AJUSTES = r"""<?php
use Symfony\Component\Yaml\Yaml;
require 'vendor/autoload.php';
$d = json_decode(getenv('RECETA_DATOS'), TRUE);
function editar($ruta, $cambio) {
  $datos = is_file($ruta) ? (Yaml::parseFile($ruta) ?: []) : [];
  file_put_contents($ruta, Yaml::dump(array_replace_recursive($datos, $cambio), 10, 2));
}
if (isset($d['titulo'])) {
  editar('user/config/site.yaml', ['title' => $d['titulo'], 'default_lang' => 'es',
    'author' => ['name' => $d['titulo'], 'email' => $d['correo']],
    'metadata' => ['description' => $d['titulo']]]);
  editar('user/config/system.yaml', ['timezone' => 'America/Guayaquil', 'errors' => ['display' => FALSE]]);
}
$cuenta = 'user/accounts/' . $d['usuario'] . '.yaml';
if (!is_file($cuenta)) { fwrite(STDERR, "no existe el usuario\n"); exit(1); }
$datos = Yaml::parseFile($cuenta);
unset($datos['password']);
$datos['hashed_password'] = password_hash($d['clave'], PASSWORD_DEFAULT);
file_put_contents($cuenta, Yaml::dump($datos, 10, 2));
echo "LISTO\n";
"""


def _ajustes(meta, datos):
    return ejecutar(["php"], entrada=_AJUSTES, como=meta["usuario"], cwd=meta["publico"],
                    env_extra={"RECETA_DATOS": json.dumps(datos)})


def instalar(meta, bd, bd_usuario, bd_clave, titulo, correo, admin_usuario, admin_clave):
    receta.preparar(meta, receta.github("getgrav/grav", r"grav-admin-v[0-9.]+\.zip"), "Grav")
    if not os.path.isfile(os.path.join(meta["publico"], "bin/plugin")):
        raise ErrorSitio("el paquete de Grav no tiene la estructura esperada")
    # Clave provisional que cumple la política de Grav; se reemplaza enseguida por el hash de la real.
    provisional = "Pv1" + secrets.token_urlsafe(18)
    receta.php(meta, "bin/plugin", "login", "new-user", "-n", f"--user={admin_usuario}", f"--password={provisional}",
               f"--email={correo}", "--permissions=b", "--admin-type=both", f"--fullname={titulo}",
               "--title=Administrador", "--language=es", "--state=enabled")
    if "LISTO" not in _ajustes(meta, {"usuario": admin_usuario, "clave": admin_clave, "titulo": titulo,
                                      "correo": correo}):
        raise ErrorSitio("no se pudo configurar Grav")
    receta.php(meta, "bin/grav", "clearcache")
    return receta.url(meta) + "/admin"


def clave_admin(meta, usuario, nueva):
    if "LISTO" not in _ajustes(meta, {"usuario": usuario, "clave": nueva}):
        raise ErrorSitio("no se pudo cambiar la clave en Grav")
