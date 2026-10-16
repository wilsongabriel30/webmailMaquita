"""Instalación de aplicaciones libres en un sitio: WordPress y Joomla (ambas GPLv2 o posterior).

No se redistribuye nada: cada instalación descarga la versión oficial vigente de su origen y
comprueba su integridad antes de usarla.

- WordPress: paquete .zip oficial verificado con la SHA-1 que publica downloads.wordpress.org;
  después WP-CLI (MIT) lo configura y `wp core verify-checksums` comprueba cada archivo contra
  api.wordpress.org.
- Joomla: paquete completo oficial de la última versión estable (GitHub de joomla-cms), verificado
  con SHA-256 contra dos fuentes que deben coincidir (notas de la versión y GitHub), e instalación
  por su propia línea de órdenes (`installation/joomla.php install`).

La base de datos es MariaDB (GPLv2): una base y un usuario propios por sitio, solo desde localhost.
"""

import hashlib
import json
import os
import re
import secrets
import shutil
import tempfile
import urllib.request
import zipfile

from comun import WP_CLI, ErrorSitio, clave, ejecutar, guardar_meta, leer_meta, slug

API_WORDPRESS = "https://api.wordpress.org/core/version-check/1.7/"
LANZAMIENTOS_JOOMLA = "https://api.github.com/repos/joomla/joomla-cms/releases/latest"
AGENTE = "instalador-sitios/1.0"


def _mariadb(sql):
    ejecutar(["mariadb", "--protocol=socket", "-u", "root", "-e", sql])


def crear_bd(meta):
    """Base y usuario propios. Los identificadores salen de slug() (solo [a-z0-9])."""
    nombre = f"w_{slug(meta['dominio'])}"
    usuario = nombre
    contrasena = clave(24).replace("'", "")
    _mariadb(
        f"CREATE DATABASE `{nombre}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"
        f"CREATE USER '{usuario}'@'localhost' IDENTIFIED BY '{contrasena}';"
        f"GRANT ALL PRIVILEGES ON `{nombre}`.* TO '{usuario}'@'localhost';"
        "FLUSH PRIVILEGES;"
    )
    return nombre, usuario, contrasena


def volcar_y_borrar_bd(meta, destino):
    """Antes de borrar un sitio, guarda su base de datos junto a los archivos (papelera)."""
    nombre = meta["bd"]
    salida = ejecutar(["mariadb-dump", "--protocol=socket", "-u", "root", "--single-transaction", nombre])
    with open(os.open(destino, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600), "w") as f:
        f.write(salida)
    _mariadb(f"DROP DATABASE IF EXISTS `{nombre}`; DROP USER IF EXISTS '{nombre}'@'localhost';")


def _publico_vacio(meta):
    """La carpeta pública solo puede tener el index.html de bienvenida."""
    restos = [n for n in os.listdir(meta["publico"]) if n != "index.html"]
    if restos:
        raise ErrorSitio("la carpeta del sitio ya tiene archivos: instala la aplicación en un sitio vacío")
    ruta = os.path.join(meta["publico"], "index.html")
    if os.path.exists(ruta):
        os.remove(ruta)


def _deshacer_instalacion(meta):
    """Si la instalación falla, el sitio vuelve a quedar vacío y sin base de datos."""
    try:
        _mariadb(f"DROP DATABASE IF EXISTS `{meta['bd']}`; DROP USER IF EXISTS '{meta['bd']}'@'localhost';")
    except ErrorSitio:
        pass
    for nombre in os.listdir(meta["publico"]):
        ruta = os.path.join(meta["publico"], nombre)
        if os.path.isdir(ruta) and not os.path.islink(ruta):
            shutil.rmtree(ruta, ignore_errors=True)
        else:
            os.remove(ruta)
    meta["bd"] = None
    guardar_meta(meta)


def _url(meta):
    return ("https://" if meta.get("ssl") else "http://") + meta["dominio"]


def instalar(dominio, app, titulo, correo):
    meta = leer_meta(dominio)
    if meta.get("app"):
        raise ErrorSitio(f"el sitio ya tiene {meta['app']} instalado")
    _publico_vacio(meta)
    bd, bd_usuario, bd_clave = crear_bd(meta)
    meta["bd"] = bd
    guardar_meta(meta)
    admin_usuario = "admin" + secrets.token_hex(3)
    admin_clave = clave(18)
    try:
        if app == "wordpress":
            _wordpress(meta, bd, bd_usuario, bd_clave, titulo, correo, admin_usuario, admin_clave)
            acceso_admin = _url(meta) + "/wp-admin/"
        else:
            _joomla(meta, bd, bd_usuario, bd_clave, titulo, correo, admin_usuario, admin_clave)
            acceso_admin = _url(meta) + "/administrator/"
    except Exception:
        _deshacer_instalacion(meta)
        raise
    meta["app"] = app
    meta["app_admin"] = acceso_admin
    meta["app_usuario"] = admin_usuario
    guardar_meta(meta)
    if app == "wordpress":
        import seguridad

        seguridad.endurecer_wordpress(meta)
    # El vhost lleva reglas propias de cada aplicación (accesos de fuerza bruta, archivos sensibles).
    import sitio

    sitio.escribir_vhost(meta)
    sitio.recargar_nginx()
    # Las credenciales se devuelven UNA vez para mostrarlas en el panel; no se guardan.
    return {
        "dominio": dominio,
        "app": app,
        "url_admin": acceso_admin,
        "admin_usuario": admin_usuario,
        "admin_clave": admin_clave,
        "base_datos": bd,
    }


def _wp(meta, *args, entrada=None):
    # cwd en la carpeta del sitio: algunas órdenes lanzan subprocesos desde la carpeta actual, y la
    # del que llama (root) no es accesible para el usuario del sitio (posix_spawn: Permission denied).
    return ejecutar([WP_CLI, f"--path={meta['publico']}", *args], como=meta["usuario"], entrada=entrada,
                    cwd=meta["publico"], env_extra={"WP_CLI_CACHE_DIR": os.path.join(meta["tmp"], ".wp-cli")})


def _wordpress(meta, bd, bd_usuario, bd_clave, titulo, correo, admin_usuario, admin_clave):
    if not os.path.exists(WP_CLI):
        raise ErrorSitio("WP-CLI no está instalado: ejecuta «instalar-app.sh sitios»")
    # Núcleo oficial (inglés). La versión traducida suele publicarse días después de cada versión
    # nueva: el español se añade al final como paquete de idioma, que no depende de eso.
    _descargar_wordpress(meta)
    # La clave de la base va por la entrada estándar (--prompt) para que no aparezca en la lista de procesos.
    _wp(meta, "config", "create", f"--dbname={bd}", f"--dbuser={bd_usuario}", "--dbhost=localhost",
        "--prompt=dbpass", entrada=bd_clave + "\n")
    _wp(meta, "config", "set", "DISALLOW_FILE_EDIT", "true", "--raw")
    _wp(meta, "config", "set", "FS_METHOD", "direct")
    _wp(meta, "core", "install", f"--url={_url(meta)}", f"--title={titulo}", f"--admin_user={admin_usuario}",
        f"--admin_email={correo}", "--skip-email", "--prompt=admin_password", entrada=admin_clave + "\n")
    _wp(meta, "core", "verify-checksums")
    for idioma in ("es_ES", "es_EC"):
        try:
            _wp(meta, "language", "core", "install", idioma, "--activate")
            break
        except ErrorSitio:
            continue
    ejecutar(["chmod", "640", os.path.join(meta["publico"], "wp-config.php")])


def _descargar_wordpress(meta):
    """Paquete .zip oficial, verificado con la SHA-1 que publica downloads.wordpress.org.

    No se usa «wp core download»: baja el .tar.gz y la extracción de PHP (PharData) pierde los
    archivos con rutas de más de 100 caracteres, que WordPress 7 ya tiene. Después,
    «wp core verify-checksums» compara cada archivo con api.wordpress.org (segunda fuente).
    """
    pet = urllib.request.Request(API_WORDPRESS, headers={"User-Agent": AGENTE})
    with urllib.request.urlopen(pet, timeout=60) as r:
        oferta = json.load(r)["offers"][0]
    version = oferta.get("current", "")
    url = oferta.get("packages", {}).get("full") or oferta.get("download")
    if not re.match(r"^\d+\.\d+(\.\d+)?$", version) or not (url or "").startswith("https://downloads.wordpress.org/release/"):
        raise ErrorSitio("respuesta inesperada de api.wordpress.org")
    with tempfile.TemporaryDirectory() as tmp:
        paquete = os.path.join(tmp, "wordpress.zip")
        _descargar(url, paquete)
        suma = os.path.join(tmp, "wordpress.zip.sha1")
        _descargar(url + ".sha1", suma, tope=1024)
        with open(suma) as f:
            partes = f.read().split()
        esperado = partes[0].strip().lower() if partes else ""
        h = hashlib.sha1()
        with open(paquete, "rb") as f:
            for bloque in iter(lambda: f.read(1 << 20), b""):
                h.update(bloque)
        if not re.match(r"^[0-9a-f]{40}$", esperado) or h.hexdigest() != esperado:
            raise ErrorSitio("el paquete de WordPress no coincide con su suma oficial: instalación cancelada")
        _extraer_zip(paquete, tmp, "wordpress/")
        origen = os.path.join(tmp, "wordpress")
        for nombre in os.listdir(origen):
            shutil.move(os.path.join(origen, nombre), meta["publico"])
    ejecutar(["chown", "-R", f"{meta['usuario']}:www-data", meta["publico"]])
    ejecutar(["chmod", "-R", "u+rwX,g+rX,g-w,o-rwx", meta["publico"]])
    meta["app_version"] = version


def _extraer_zip(paquete, destino, prefijo=""):
    with zipfile.ZipFile(paquete) as z:
        for n in z.namelist():
            if n.startswith("/") or ".." in n.split("/") or (prefijo and not n.startswith(prefijo)):
                raise ErrorSitio("paquete con rutas no válidas")
        z.extractall(destino)


def _descargar(url, destino, tope=200 * 1048576):
    if not url.startswith("https://"):
        raise ErrorSitio("descarga rechazada: solo HTTPS")
    pet = urllib.request.Request(url, headers={"User-Agent": AGENTE})
    with urllib.request.urlopen(pet, timeout=120) as r, open(destino, "wb") as f:
        leidos = 0
        while True:
            bloque = r.read(1 << 20)
            if not bloque:
                break
            leidos += len(bloque)
            if leidos > tope:
                raise ErrorSitio("descarga demasiado grande")
            f.write(bloque)


def _ultima_joomla():
    """(versión, url del paquete completo .zip, sha256) de la última versión estable publicada.

    La suma se exige a dos fuentes que deben coincidir: la tabla de sumas que Joomla publica en las
    notas de la versión y el resumen SHA-256 que GitHub calcula del archivo adjunto.
    """
    pet = urllib.request.Request(LANZAMIENTOS_JOOMLA, headers={"User-Agent": AGENTE, "Accept": "application/vnd.github+json"})
    with urllib.request.urlopen(pet, timeout=60) as r:
        datos = json.load(r)
    version = datos.get("tag_name", "")
    if datos.get("prerelease") or datos.get("draft") or not re.match(r"^\d+\.\d+\.\d+$", version):
        raise ErrorSitio("la última versión publicada de Joomla no es estable")
    nombre = f"Joomla_{version}-Stable-Full_Package.zip"
    activo = next((a for a in datos.get("assets", []) if a.get("name") == nombre), None)
    if not activo:
        raise ErrorSitio("no se encontró el paquete completo de Joomla en la versión publicada")
    url = activo["browser_download_url"]
    m = re.search(re.escape(nombre) + r"\)\s*\|\s*`([0-9a-f]{64})`", datos.get("body", ""))
    sha_notas = m.group(1) if m else None
    sha_github = (activo.get("digest") or "").removeprefix("sha256:")
    if not sha_notas or sha_notas != sha_github:
        raise ErrorSitio("no se pudo confirmar la suma oficial del paquete de Joomla: instalación cancelada")
    return version, url, sha_notas


def _joomla(meta, bd, bd_usuario, bd_clave, titulo, correo, admin_usuario, admin_clave):
    version, url, sha256 = _ultima_joomla()
    if not url.startswith("https://github.com/joomla/joomla-cms/releases/download/"):
        raise ErrorSitio("origen del paquete de Joomla no esperado")
    with tempfile.TemporaryDirectory() as tmp:
        paquete = os.path.join(tmp, "joomla.zip")
        _descargar(url, paquete)
        h = hashlib.sha256()
        with open(paquete, "rb") as f:
            for bloque in iter(lambda: f.read(1 << 20), b""):
                h.update(bloque)
        if h.hexdigest() != sha256:
            raise ErrorSitio("el paquete de Joomla no coincide con su suma oficial: instalación cancelada")
        _extraer_zip(paquete, meta["publico"])
    ejecutar(["chown", "-R", f"{meta['usuario']}:www-data", meta["publico"]])
    ejecutar(["chmod", "-R", "u+rwX,g+rX,g-w,o-rwx", meta["publico"]])
    prefijo = f"j{secrets.token_hex(2)}_"
    ejecutar([
        "php", "installation/joomla.php", "install",
        f"--site-name={titulo}", "--admin-user=Administrador", f"--admin-username={admin_usuario}",
        f"--admin-password={admin_clave}", f"--admin-email={correo}", "--db-type=mysqli",
        "--db-host=localhost", f"--db-user={bd_usuario}", f"--db-pass={bd_clave}", f"--db-name={bd}",
        f"--db-prefix={prefijo}", "--db-encryption=0", "--no-interaction",
    ], como=meta["usuario"], cwd=meta["publico"])
    # Sin estadísticas hacia joomla.org (el sitio no informa a terceros de su configuración).
    _mariadb(f"UPDATE `{bd}`.`{prefijo}extensions` SET enabled = 0 "
             "WHERE type = 'plugin' AND folder = 'system' AND element = 'stats';")
    instalacion = os.path.join(meta["publico"], "installation")
    if os.path.isdir(instalacion):
        shutil.rmtree(instalacion)
    meta["app_version"] = version
    guardar_meta(meta)
