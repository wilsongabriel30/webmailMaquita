"""Alta, listado y baja de sitios: usuario de sistema, carpetas, pool de PHP-FPM y vhost de nginx.

Estructura de cada sitio (la carpeta del sitio es de root para que el acceso FTP/SFTP pueda
encerrarse en ella; el usuario del sitio solo escribe en «publico» y «tmp»):

    /srv/sitios/<dominio>/            root:root 755   (raíz del FTP/SFTP)
    /srv/sitios/<dominio>/publico/    <usuario>:www-data 2750   (lo que sirve nginx)
    /srv/sitios/<dominio>/tmp/        <usuario>:<usuario> 700   (sesiones, subidas, errores PHP)
    /srv/sitios/<dominio>/registros/  root:root 750   (accesos y errores de nginx)
"""

import glob
import os
import pwd
import shutil
import time

import pagina_inicio
import plantillas
from comun import (
    ACME_WEBROOT,
    GRUPO_SITIOS,
    NGINX_ACT,
    NGINX_DISP,
    PAPELERA,
    PREFIJO_CONF,
    RAIZ_SITIOS,
    ErrorSitio,
    ejecutar,
    guardar_meta,
    leer_meta,
    ruta_meta,
    slug,
    todos_los_meta,
    version_php,
)

def _socket(meta):
    return f"/run/php/sitio-{meta['usuario']}.sock"


def _ruta_vhost(dominio):
    return os.path.join(NGINX_DISP, f"{PREFIJO_CONF}{dominio}.conf")


def _ruta_pool(meta):
    return f"/etc/php/{meta['php']}/fpm/pool.d/sitio-{meta['usuario']}.conf"


def _escribir(ruta, texto, modo=0o644):
    tmp = ruta + ".tmp"
    with open(tmp, "w") as f:
        f.write(texto)
    os.chmod(tmp, modo)
    os.replace(tmp, ruta)


def _nombres_en_uso():
    """server_name de los vhosts que NO son sitios (webmail, panel, autodiscover...)."""
    usados = set()
    for ruta in glob.glob(os.path.join(NGINX_ACT, "*")):
        if os.path.basename(ruta).startswith(PREFIJO_CONF):
            continue
        try:
            with open(ruta) as f:
                for linea in f:
                    linea = linea.strip()
                    if linea.startswith("server_name"):
                        usados.update(linea.rstrip(";").split()[1:])
        except OSError:
            continue
    return usados


def recargar_nginx():
    # Otra operación puede estar escribiendo su vhost en ese instante: se reintenta antes de dar error.
    import time

    for intento in range(3):
        try:
            ejecutar(["nginx", "-t"])
            break
        except ErrorSitio:
            if intento == 2:
                raise
            time.sleep(2)
    antes = _trabajadores_nginx()
    ejecutar(["systemctl", "reload", "nginx"])
    # La recarga es gradual (con ModSecurity, los procesos nuevos tardan unos segundos en cargar las reglas):
    # se espera a que estén todos los trabajadores nuevos, para que lo siguiente ya vea la configuración nueva.
    for _ in range(60):
        time.sleep(0.25)
        ahora = _trabajadores_nginx()
        if antes and len(ahora - antes) >= len(antes):
            break
    time.sleep(0.5)


def _trabajadores_nginx():
    try:
        with open("/run/nginx.pid") as f:
            maestro = f.read().strip()
        with open(f"/proc/{maestro}/task/{maestro}/children") as f:
            hijos = f.read().split()
    except OSError:
        return set()
    trabajadores = set()
    for pid in hijos:
        try:
            with open(f"/proc/{pid}/cmdline", "rb") as f:
                titulo = f.read()
            if b"worker process" in titulo and b"shutting down" not in titulo:  # no los viejos que se van
                trabajadores.add(pid)
        except OSError:
            pass
    return trabajadores


def recargar_php(meta):
    ejecutar(["systemctl", "reload", f"php{meta['php']}-fpm"])


def escribir_pool(meta):
    """Pool de PHP-FPM del sitio (con los ajustes de «Avanzado», si los hay)."""
    _escribir(_ruta_pool(meta), plantillas.pool(meta, _socket(meta)))


def escribir_vhost(meta):
    import nginx_web

    nginx_web.escribir(meta)  # lo que incluye el vhost (funciones web): antes que el vhost
    import waf_sitio

    waf_sitio.escribir(meta)  # reglas del cortafuegos de aplicación del sitio (las incluye el vhost)
    texto = plantillas.vhost(meta, _socket(meta), ACME_WEBROOT, meta.get("ssl", False))
    _escribir(_ruta_vhost(meta["dominio"]), texto)
    enlace = os.path.join(NGINX_ACT, os.path.basename(_ruta_vhost(meta["dominio"])))
    if not os.path.islink(enlace):
        os.symlink(_ruta_vhost(meta["dominio"]), enlace)


def publicar_vhost(meta):
    """Escribe el vhost y recarga nginx; si nginx lo rechaza, deja el anterior para no romper los demás sitios."""
    ruta = _ruta_vhost(meta["dominio"])
    anterior = open(ruta).read() if os.path.exists(ruta) else None
    escribir_vhost(meta)
    try:
        recargar_nginx()
    except ErrorSitio:
        if anterior is None:
            for r in (os.path.join(NGINX_ACT, os.path.basename(ruta)), ruta):
                if os.path.lexists(r):
                    os.remove(r)
        else:
            _escribir(ruta, anterior)
        raise


def crear(dominio, con_www=True, nombre=None):
    php = version_php()
    if not php:
        raise ErrorSitio("PHP-FPM no está instalado: ejecuta «instalar-app.sh sitios»")
    if os.path.exists(ruta_meta(dominio)):
        raise ErrorSitio(f"el sitio {dominio} ya existe")
    import alias

    if dominio in alias._ocupados(None):
        raise ErrorSitio(f"{dominio} ya es alias del sitio {alias._ocupados(None)[dominio]}")
    usados = _nombres_en_uso()
    if dominio in usados or f"www.{dominio}" in usados:
        raise ErrorSitio(f"{dominio} ya lo usa otro servicio de este servidor (correo o panel)")

    usuario = f"web{slug(dominio)}"
    base = os.path.join(RAIZ_SITIOS, dominio)
    meta = {
        "dominio": dominio,
        "www": con_www,
        "usuario": usuario,
        "base": base,
        "publico": os.path.join(base, "publico"),
        "tmp": os.path.join(base, "tmp"),
        "registros": os.path.join(base, "registros"),
        "php": php,
        "app": None,
        "ssl": False,
        "ftp": False,
        "creado": time.strftime("%Y-%m-%d %H:%M"),
    }
    try:
        pwd.getpwnam(usuario)
        raise ErrorSitio(f"el usuario de sistema {usuario} ya existe")
    except KeyError:
        pass

    os.makedirs(RAIZ_SITIOS, mode=0o755, exist_ok=True)
    # Sin shell ni contraseña hasta que se active el FTP. El grupo «sitios» es el que encierra el
    # SFTP en la carpeta del sitio (sshd_config.d/sitios.conf).
    ejecutar([
        "useradd", "--system", "--no-create-home", "--home-dir", base,
        "--shell", "/usr/sbin/nologin", "--user-group", "--groups", GRUPO_SITIOS, usuario,
    ])
    ejecutar(["passwd", "-l", usuario])

    os.makedirs(base, mode=0o755)
    os.chown(base, 0, 0)
    pw = pwd.getpwnam(usuario)
    www = pwd.getpwnam("www-data")
    os.makedirs(meta["publico"])
    os.chown(meta["publico"], pw.pw_uid, www.pw_gid)
    os.chmod(meta["publico"], 0o2750)
    os.makedirs(meta["tmp"])
    os.chown(meta["tmp"], pw.pw_uid, pw.pw_gid)
    os.chmod(meta["tmp"], 0o700)
    os.makedirs(meta["registros"])
    os.chmod(meta["registros"], 0o750)

    # Página «en construcción» con el nombre de la institución, robots.txt, sitemap.xml y llms.txt.
    for archivo, contenido in pagina_inicio.archivos(dominio, nombre, con_www).items():
        ruta = os.path.join(meta["publico"], archivo)
        _escribir(ruta, contenido, 0o640)
        os.chown(ruta, pw.pw_uid, www.pw_gid)
    meta["nombre"] = nombre or dominio
    import visibilidad

    visibilidad.clave_indexnow(meta)  # archivo de verificación de IndexNow en la raíz

    guardar_meta(meta)
    try:
        _escribir(_ruta_pool(meta), plantillas.pool(meta, _socket(meta)))
        recargar_php(meta)
        escribir_vhost(meta)
        recargar_nginx()
    except ErrorSitio:
        _deshacer(meta)
        raise
    return publico(meta)


def _deshacer(meta):
    """Revierte un alta a medias (se llama solo si falla la configuración de PHP o nginx)."""
    for ruta in (_ruta_pool(meta), _ruta_vhost(meta["dominio"]),
                 os.path.join(NGINX_ACT, os.path.basename(_ruta_vhost(meta["dominio"])))):
        if os.path.lexists(ruta):
            os.remove(ruta)
    shutil.rmtree(meta["base"], ignore_errors=True)
    import nginx_web

    nginx_web.quitar(meta["dominio"])
    if os.path.exists(ruta_meta(meta["dominio"])):
        os.remove(ruta_meta(meta["dominio"]))
    try:
        ejecutar(["userdel", meta["usuario"]])
    except ErrorSitio:
        pass
    for orden in (["systemctl", "reload", f"php{meta['php']}-fpm"], ["systemctl", "reload", "nginx"]):
        try:
            ejecutar(orden)
        except ErrorSitio:
            pass


def publico(meta):
    """Lo que el panel puede ver de un sitio (sin rutas internas sensibles ni claves)."""
    return {
        "dominio": meta["dominio"],
        "www": meta.get("www", True),
        "alias": meta.get("alias", []),
        "alias_sin_https": meta.get("alias_sin_https", []),
        "app": meta.get("app"),
        "app_admin": meta.get("app_admin"),
        "app_pendiente": meta.get("app_pendiente", False),
        "app_version": meta.get("app_version"),
        "aviso_url": meta.get("aviso_url"),
        "ssl": meta.get("ssl", False),
        "ftp": meta.get("ftp", False),
        "tienda": meta.get("tienda", False),
        "propia": (meta.get("propia") or {}).get("tipo"),
        "bases": len(meta.get("bases", [])),
        "usuario_ftp": meta["usuario"],
        "base_datos": meta.get("bd"),
        "php": meta.get("php"),
        "creado": meta.get("creado"),
        "ocupado_mb": _tamano_mb(meta["base"]),
    }


def _tamano_mb(ruta):
    total = 0
    for raiz, _dirs, archivos in os.walk(ruta):
        for a in archivos:
            try:
                total += os.lstat(os.path.join(raiz, a)).st_size
            except OSError:
                pass
    return round(total / 1048576, 1)


LOGO_MARCA = "/opt/maquita-webmail/uploads/branding/logo"


def rehacer_inicio(dominio, identidad):
    """Rehace la página «en construcción» con la identidad de la institución (Personalización).

    Solo en sitios sin aplicación: un WordPress o Joomla tiene su propio contenido.
    """
    meta = leer_meta(dominio)
    if meta.get("app") == "propia":
        return {"dominio": dominio, "actualizada": False, "motivo": "aplicación propia: su contenido es suyo"}
    if meta.get("app"):
        # Un WordPress o Joomla conserva su contenido: solo recibe la identidad para buscadores e IA.
        import visibilidad

        return visibilidad.identidad_en_app(meta, identidad)
    pw = pwd.getpwnam(meta["usuario"])
    www = pwd.getpwnam("www-data")
    logo = None
    origen = sorted(glob.glob(os.path.join(LOGO_MARCA, "*")))
    for viejo in glob.glob(os.path.join(meta["publico"], "logo.*")):
        os.remove(viejo)
    if origen:
        extension = os.path.splitext(origen[0])[1].lower()
        if extension in (".png", ".jpg", ".jpeg", ".webp", ".svg", ".gif"):
            logo = f"logo{extension}"
            destino = os.path.join(meta["publico"], logo)
            shutil.copyfile(origen[0], destino)
            os.chown(destino, pw.pw_uid, www.pw_gid)
            os.chmod(destino, 0o640)
    # El nombre propio del sitio (asistente «Nuevo dominio») manda; si se creó sin nombre, el de la institución.
    propio = meta.get("nombre") if meta.get("nombre") not in (None, "", dominio) else None
    nombre = propio or identidad.get("nombre") or dominio
    for archivo, contenido in pagina_inicio.archivos(dominio, nombre, meta.get("www", True), identidad, logo).items():
        ruta = os.path.join(meta["publico"], archivo)
        _escribir(ruta, contenido, 0o640)
        os.chown(ruta, pw.pw_uid, www.pw_gid)
    return {"dominio": dominio, "actualizada": True, "logo": bool(logo)}


def regenerar():
    """Reescribe todos los vhosts con las plantillas vigentes (tras actualizar esta sección)."""
    hechos = []
    for meta in todos_los_meta():
        escribir_vhost(meta)
        hechos.append(meta["dominio"])
    if hechos:
        recargar_nginx()
    return {"regenerados": hechos}


def listar():
    return [publico(m) for m in todos_los_meta()]


def borrar(dominio):
    """Da de baja el sitio. Los archivos y la copia de la base de datos van a la papelera."""
    import aplicaciones

    meta = leer_meta(dominio)
    sello = time.strftime("%Y%m%d-%H%M%S")
    destino = os.path.join(PAPELERA, f"{dominio}-{sello}")
    os.makedirs(PAPELERA, mode=0o700, exist_ok=True)

    if meta.get("bd"):
        import bases_usuarios

        bases_usuarios.borrar_de_base(meta, meta["bd"])  # usuarios adicionales de la base de la aplicación
        aplicaciones.volcar_y_borrar_bd(meta, os.path.join(meta["base"], f"base-de-datos-{sello}.sql"))
    import propias
    import tareas

    propias.limpiar_para_baja(meta)
    import git_despliegue

    git_despliegue.limpiar_para_baja(meta)  # secreto del gancho (la carpeta de despliegues va con el sitio)
    tareas.quitar_todos(meta)
    if meta.get("bases"):
        import bases

        bases.borrar_todas(meta, meta["base"])  # copias .sql junto a los archivos, en la papelera
        meta = leer_meta(dominio)

    import avanzado

    avanzado.quitar(dominio)  # reglas propias de nginx y versiones guardadas de «Avanzado»
    import ftp_cuentas
    import nginx_web

    ftp_cuentas.quitar_todas(meta)  # cuentas FTP adicionales (desmonta sus carpetas antes de mover el sitio)
    nginx_web.quitar(dominio)  # archivos de las funciones web y caché de página
    import claves_ssh
    import waf_sitio

    claves_ssh.quitar_todas(meta)  # claves SSH de la cuenta principal y de las adicionales
    waf_sitio.quitar(dominio)  # reglas y registro del cortafuegos de aplicación del sitio
    for ruta in (os.path.join(NGINX_ACT, os.path.basename(_ruta_vhost(dominio))), _ruta_vhost(dominio), _ruta_pool(meta)):
        if os.path.lexists(ruta):
            os.remove(ruta)
    recargar_nginx()
    recargar_php(meta)

    import acceso

    acceso.quitar_de_lista_ftp(meta["usuario"])
    try:
        ejecutar(["pkill", "-u", meta["usuario"]])
    except ErrorSitio:
        pass
    ejecutar(["userdel", meta["usuario"]])
    shutil.move(meta["base"], destino)
    ejecutar(["chown", "-R", "root:root", destino])
    import ordenes_datos

    ordenes_datos.limpiar_sitio(meta, destino)  # estadísticas, disponibilidad y copias del cliente (a la papelera)
    os.remove(ruta_meta(dominio))
    return {"dominio": dominio, "papelera": destino}
