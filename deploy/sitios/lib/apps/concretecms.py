"""Concrete CMS — gestor de contenidos con edición directa sobre la página (MIT). https://www.concretecms.org

Paquete oficial adjunto a la versión de GitHub (SHA-256 calculada por GitHub). Instalación por su línea
de órdenes (c5:install) con un archivo de opciones en la carpeta privada, para que las claves no
aparezcan en la lista de procesos. Concrete siempre crea el administrador como «admin»: se le pone el
nombre que da el panel con su propia API (c5:exec), que también sirve para cambiarle la clave.
"""

import json
import os
import tempfile

from comun import ErrorSitio, ejecutar

from . import receta

NOMBRE = "Concrete CMS"
DESCRIPCION = "Sitios institucionales que se editan directamente sobre la página, arrastrando bloques."
LICENCIA = "MIT"
CATEGORIA = "Sitios y blogs"
VERIFICACION = "GitHub"
RAIZ_WEB = ""

# Todo pasa por index.php; configuración, código y archivos internos no se sirven.
REGLAS_NGINX = r"""
    location ~ ^/(?!index\.php(?:/|$$)).*\.php(?:/|$$) { deny all; }
    location ~ ^/application/(?:config|bootstrap|src|controllers|languages|files/(?:incoming|trash|backups|cache/[^/]+\.(?:log|txt)))/ { deny all; }
    location ~ ^/(?:updates|concrete/(?:vendor|config|bootstrap|src|controllers|bin))/ { deny all; }
    location ~* \.(?:twig|xml|lock|md|TXT)$$ { deny all; }
    location ~ ^/composer\.json$$ { deny all; }
    location ~ ^/(?:index\.php/)?login/authenticate/ {
        limit_req zone=sitios_login burst=10 nodelay;
        limit_req zone=sitios_general burst=80 nodelay;
        try_files $$uri /index.php?$$args;
    }
"""

# Se ejecuta con c5:exec (Concrete ya arrancado): nombre y clave del administrador.
_ADMIN = r"""<?php
$d = json_decode(getenv('RECETA_DATOS'), TRUE);
$repo = app(\Concrete\Core\User\UserInfoRepository::class);
$ui = isset($d['renombrar']) ? $repo->getByID(1) : $repo->getByName($d['usuario']);
if (!$ui) { fwrite(STDERR, "no existe el usuario\n"); exit(1); }
if (isset($d['renombrar'])) { $ui->update(['uName' => $d['usuario']]); }
$ui->changePassword($d['clave']);
echo "LISTO\n";
return 0;  // c5:exec usa lo que devuelve el script como código de salida
"""


def _concrete(meta, *args, datos=None):
    return ejecutar(["php", "-d", "memory_limit=512M", "concrete/bin/concrete", *args], como=meta["usuario"],
                    cwd=meta["publico"], tiempo=1200, env_extra={"RECETA_DATOS": json.dumps(datos or {})})


def _archivo_privado(meta, contenido):
    """Archivo temporal 0600 del usuario del sitio en su carpeta privada (se borra al terminar)."""
    fd, ruta = tempfile.mkstemp(dir=meta["tmp"], prefix=".receta-", suffix=".php")
    with os.fdopen(fd, "w") as f:
        f.write(contenido)
    ejecutar(["chown", meta["usuario"], ruta])
    return ruta


def _admin(meta, datos):
    ruta = _archivo_privado(meta, _ADMIN)
    try:
        return _concrete(meta, "c5:exec", ruta, datos=datos)
    finally:
        os.remove(ruta)


def instalar(meta, bd, bd_usuario, bd_clave, titulo, correo, admin_usuario, admin_clave):
    receta.preparar(meta, receta.github("concretecms/concretecms", r"concrete-cms-[0-9.]+\.zip"), "Concrete CMS")
    if not os.path.isfile(os.path.join(meta["publico"], "concrete/bin/concrete")):
        raise ErrorSitio("el paquete de Concrete CMS no tiene la estructura esperada")
    # Traducción al español (se descarga de su servidor oficial de traducciones).
    _concrete(meta, "c5:language-install", "--add=es_ES", "--core")
    opciones = {"db-server": "localhost", "db-username": bd_usuario, "db-password": bd_clave, "db-database": bd,
                "timezone": "America/Guayaquil", "site": titulo, "starting-point": "atomik_full",
                "admin-email": correo, "admin-password": admin_clave, "language": "es_ES", "site-locale": "es_EC",
                "disable-marketplace-connect": True}
    ruta = _archivo_privado(meta, "<?php\nreturn " + _php_literal(opciones) + ";\n")
    try:
        _concrete(meta, "c5:install", f"--config={ruta}", "-n")
    finally:
        os.remove(ruta)
    if "LISTO" not in _admin(meta, {"renombrar": True, "usuario": admin_usuario, "clave": admin_clave}):
        raise ErrorSitio("no se pudo preparar el administrador de Concrete CMS")
    # Direcciones sin «index.php» (nginx ya envía todo a index.php).
    _concrete(meta, "c5:config", "set", "-g", "concrete.seo.url_rewriting", "true")
    for nombre in ("database.php", "site_install.php", "site_install_user.php"):
        archivo = os.path.join(meta["publico"], "application/config", nombre)
        if os.path.exists(archivo):
            os.chmod(archivo, 0o640)
    return receta.url(meta) + "/login"


def _php_literal(valor):
    """Arreglo PHP a partir de un dict (json_decode evita problemas de comillas)."""
    return "json_decode(" + "'" + json.dumps(valor).replace("\\", "\\\\").replace("'", "\\'") + "', TRUE)"


def clave_admin(meta, usuario, nueva):
    if "LISTO" not in _admin(meta, {"usuario": usuario, "clave": nueva}):
        raise ErrorSitio("no se pudo cambiar la clave en Concrete CMS")
