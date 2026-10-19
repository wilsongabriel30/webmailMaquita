"""phpBB — foros de discusión (GPLv2). https://www.phpbb.com

Paquete completo oficial de download.phpbb.com (versión vigente según version.phpbb.com) verificado con
la SHA-256 que el proyecto publica junto al paquete. Instalación por su propia línea de órdenes
(install/phpbbcli.php con un archivo de configuración que se borra al terminar); después se quita la
carpeta install/. Queda en inglés: el paquete de idioma español solo se publica en phpbb.com, que
rechaza descargas automáticas (se agrega desde «Personalizar → Idiomas» del panel de administración).
"""

import json
import os
import re
import shutil
import tempfile

from comun import ErrorSitio, ejecutar

from . import descargas, receta

NOMBRE = "phpBB"
DESCRIPCION = "Foro de discusión: temas, respuestas, mensajes privados y moderación."
LICENCIA = "GPLv2"
CATEGORIA = "Foros y comunidad"
VERIFICACION = "suma oficial"
RAIZ_WEB = ""
BASE = "https://download.phpbb.com/pub/release/3.3"

# Carpetas internas según la configuración de nginx que trae phpBB (docs/nginx.sample.conf); el
# instalador se borra tras instalar y, por si acaso, también se niega.
REGLAS_NGINX = r"""
    location = /ucp.php {
        limit_req zone=sitios_login burst=10 nodelay;
        limit_req zone=sitios_general burst=80 nodelay;
        include snippets/fastcgi-php.conf;
        fastcgi_pass unix:$socket;
    }
    location ~ ^/(?:config(?:\.php)?|web\.config|common\.php|composer\.(?:json|lock)|cache|files|images/avatars/upload|includes|phpbb|store|vendor|install|bin|docs)(?:/|$$) {
        deny all;
    }
"""


def _curl(enlace, destino):
    """download.phpbb.com está tras un filtro de Cloudflare que solo deja pasar a curl y wget (rechaza el
    agente de descargas.py): se descarga con curl, solo por HTTPS."""
    ejecutar(["curl", "-fsSL", "--proto", "=https", "--max-time", "300", "--max-filesize", str(100 * 1048576),
              "-o", destino, enlace], tiempo=330)


def _preparar(meta):
    """Como receta.preparar, pero descargando con curl. El .zip trae todo dentro de «phpBB3/»."""
    datos = json.loads(descargas.texto("https://version.phpbb.com/phpbb/versions.json"))
    version = (datos.get("stable", {}).get("3.3") or {}).get("current", "")
    if not re.fullmatch(r"3\.3\.\d+", version):
        raise ErrorSitio("no se encontró la versión estable vigente de phpBB")
    enlace = f"{BASE}/{version}/phpBB-{version}.zip"
    with tempfile.TemporaryDirectory(dir=meta["tmp"]) as tmp:
        paquete, sumas = os.path.join(tmp, "paquete.zip"), os.path.join(tmp, "paquete.sha256")
        _curl(enlace + ".sha256", sumas)
        m = re.match(r"([0-9a-f]{64})\s+phpBB-%s\.zip\s*$" % re.escape(version), open(sumas).read())
        if not m:
            raise ErrorSitio("el proyecto no publica la suma de ese paquete")
        _curl(enlace, paquete)
        descargas.comprobar(paquete, m.group(1), "sha256", "phpBB")
        extraido = os.path.join(tmp, "extraido")
        descargas.extraer(paquete, extraido)
        for n in os.listdir(extraido):
            shutil.move(os.path.join(extraido, n), os.path.join(meta["publico"], n))
    receta.permisos(meta)
    meta.update(app_version=version, app_verificacion="suma oficial", app_suma=m.group(1))


def _cli(meta, *args):
    return receta.php(meta, "bin/phpbbcli.php", "--no-interaction", *args)


def instalar(meta, bd, bd_usuario, bd_clave, titulo, correo, admin_usuario, admin_clave):
    _preparar(meta)
    if not os.path.isfile(os.path.join(meta["publico"], "install", "phpbbcli.php")):
        raise ErrorSitio("el paquete de phpBB no tiene la estructura esperada")
    ssl = bool(meta.get("ssl"))
    # Formato YAML; los valores van como cadenas JSON (YAML las acepta) para no tener problemas de comillas.
    v = json.dumps
    config = f"""installer:
    admin: {{name: {v(admin_usuario)}, password: {v(admin_clave)}, email: {v(correo)}}}
    board: {{lang: en, name: {v(titulo)}, description: {v(titulo)}}}
    database: {{dbms: mysqli, dbhost: localhost, dbport: ~, dbuser: {v(bd_usuario)}, dbpasswd: {v(bd_clave)}, dbname: {v(bd)}, table_prefix: phpbb_}}
    email: {{enabled: true, smtp_delivery: false, smtp_host: ~, smtp_port: ~, smtp_auth: ~, smtp_user: ~, smtp_pass: ~}}
    server: {{cookie_secure: {v(ssl)}, server_protocol: {v("https://" if ssl else "http://")}, force_server_vars: false, server_name: {v(meta["dominio"])}, server_port: {443 if ssl else 80}, script_path: /}}
    extensions: []
"""
    carpeta = receta.privada(meta, "phpbb-instalacion")
    ruta = os.path.join(carpeta, "config.yml")
    try:
        with open(ruta, "w") as f:
            f.write(config)
        os.chmod(ruta, 0o600)
        os.chown(ruta, *_ids(meta))
        salida = receta.php(meta, "install/phpbbcli.php", "install", ruta)
    finally:
        shutil.rmtree(carpeta, ignore_errors=True)  # el archivo lleva las claves
    if "PHPBB_INSTALLED" not in open(os.path.join(meta["publico"], "config.php")).read():
        raise ErrorSitio("la instalación de phpBB no se completó" + (f": {salida[-300:]}" if salida else ""))
    receta.quitar(meta, "install")
    for clave, valor in (("board_timezone", "America/Guayaquil"), ("board_contact", correo), ("board_email", correo)):
        _cli(meta, "config:set", clave, valor)
    _cli(meta, "cache:purge")
    os.chmod(os.path.join(meta["publico"], "config.php"), 0o440)
    return receta.url(meta) + "/adm/index.php"


def _ids(meta):
    import pwd

    p = pwd.getpwnam(meta["usuario"])
    return p.pw_uid, p.pw_gid


def clave_admin(meta, usuario, nueva):
    """phpBB acepta hashes bcrypt ($2y$) en phpbb_users.user_password."""
    receta.sql(meta, f"UPDATE phpbb_users SET user_password = {receta.literal(receta.hash_clave(nueva))}, "
                     f"user_login_attempts = 0 WHERE username_clean = {receta.literal(usuario.lower())};")


def cron(meta):
    _cli(meta, "cron:run")
