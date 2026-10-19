"""Seguridad y mantenimiento de las aplicaciones de cada sitio.

- endurecer_wordpress: complementos obligatorios (acceso desde el panel y endurecimiento), constantes
  de wp-config, segundo factor (complemento oficial «Two Factor») y limpieza de lo que no se usa.
- entrar: enlace de un solo uso (60 s) para abrir el escritorio de WordPress desde el panel.
- clave_admin: contraseña nueva para el administrador de la aplicación.
- revisar / actualizar: versión, actualizaciones pendientes, integridad de archivos y actualización.
- cron: tareas programadas de cada aplicación, lanzadas por el sistema (no por las visitas).
"""

import hashlib
import json
import os
import secrets
import shutil

from comun import ErrorSitio, clave, ejecutar, guardar_meta, leer_meta, todos_los_meta

DIR_COMPLEMENTOS = "/usr/local/lib/maquita-sitios/wordpress"
COMPLEMENTOS = ("acceso-panel.php", "seguridad-sitio.php", "visibilidad-sitio.php")
# Archivos del núcleo que se borran a propósito (revelan la versión): la verificación los excluye.
INFORMATIVOS = ("readme.html", "license.txt", "wp-config-sample.php")
_EXCLUIR = "--exclude=" + ",".join(INFORMATIVOS)


def _wp(meta, *args, entrada=None, tiempo=600):
    import aplicaciones

    return aplicaciones._wp(meta, *args, entrada=entrada)


def _joomla_cli(meta, *args):
    return ejecutar(["php", "cli/joomla.php", *args, "--no-interaction"], como=meta["usuario"], cwd=meta["publico"])


def _url(meta):
    return ("https://" if meta.get("ssl") else "http://") + meta["dominio"]


# --- WordPress: endurecimiento al instalar (y al pedir HTTPS) ---


def endurecer_wordpress(meta):
    mu = os.path.join(meta["publico"], "wp-content", "mu-plugins")
    os.makedirs(mu, exist_ok=True)
    # De root y solo legibles por el sitio: ni un complemento comprometido ni el propio sitio
    # pueden desactivarlos o modificarlos.
    os.chown(mu, 0, _gid(meta))
    os.chmod(mu, 0o750)
    for nombre in COMPLEMENTOS:
        destino = os.path.join(mu, nombre)
        shutil.copyfile(os.path.join(DIR_COMPLEMENTOS, nombre), destino)
        os.chown(destino, 0, _gid(meta))
        os.chmod(destino, 0o640)
    constantes = [
        ("DISALLOW_FILE_EDIT", "true"),
        ("DISABLE_WP_CRON", "true"),
        ("WP_AUTO_UPDATE_CORE", "true"),
        ("WP_DEBUG", "false"),
        ("WP_POST_REVISIONS", "20"),
        ("FORCE_SSL_ADMIN", "true" if meta.get("ssl") else "false"),
    ]
    for nombre, valor in constantes:
        _wp(meta, "config", "set", nombre, valor, "--raw")
    # Enlaces legibles (/nombre-de-la-entrada/): mejores para las personas y para los buscadores.
    _wp(meta, "rewrite", "structure", "/%postname%/")
    # Visible para buscadores (WordPress permite ocultarlo) y aviso automático por IndexNow al publicar.
    import visibilidad

    _wp(meta, "option", "update", "blog_public", "1")
    _wp(meta, "option", "update", "indexnow_clave", visibilidad.clave_indexnow(meta))
    for sobrante in ("hello", "akismet"):
        try:
            _wp(meta, "plugin", "delete", sobrante)
        except ErrorSitio:
            pass
    # Segundo factor: complemento oficial de los colaboradores de WordPress (GPLv2+). Cada usuario lo
    # activa en su perfil; el acceso desde el panel ya va protegido por el segundo factor del panel.
    try:
        _wp(meta, "plugin", "install", "two-factor", "--activate")
    except ErrorSitio:
        pass
    _quitar_informativos(meta)


def _quitar_informativos(meta):
    for archivo in INFORMATIVOS:
        ruta = os.path.join(meta["publico"], archivo)
        if os.path.exists(ruta):
            os.remove(ruta)


def _gid(meta):
    import grp
    import pwd

    try:
        return grp.getgrnam(meta["usuario"]).gr_gid
    except KeyError:
        return pwd.getpwnam(meta["usuario"]).pw_gid


# --- Acceso desde el panel ---


def entrar(dominio):
    meta = leer_meta(dominio)
    if meta.get("app") != "wordpress":
        raise ErrorSitio("el acceso directo está disponible para WordPress; en Joomla use «Nueva contraseña»")
    usuario = meta.get("app_usuario")
    if not usuario:
        raise ErrorSitio("el sitio no tiene registrado su usuario administrador")
    usuario_id = _wp(meta, "user", "get", usuario, "--field=ID").strip()
    if not usuario_id.isdigit():
        raise ErrorSitio("no se encontró el usuario administrador del sitio")
    vale = secrets.token_urlsafe(32)
    huella = hashlib.sha256(vale.encode()).hexdigest()
    _wp(meta, "transient", "set", f"acceso_panel_{huella}", usuario_id, "60")
    return {"dominio": dominio, "url": f"{_url(meta)}/?acceso_panel={vale}", "valido_segundos": 60}


def clave_admin(dominio):
    meta = leer_meta(dominio)
    _no_propia(meta)
    usuario = meta.get("app_usuario")
    if not meta.get("app") or not usuario:
        raise ErrorSitio("el sitio no tiene una aplicación con administrador registrado")
    nueva = clave(18)
    if meta["app"] == "wordpress":
        _wp(meta, "user", "update", usuario, "--skip-email", "--prompt=user_pass", entrada=nueva + "\n")
    elif meta["app"] == "joomla":
        _joomla_cli(meta, "user:reset-password", f"--username={usuario}", f"--password={nueva}")
    else:
        from apps import CATALOGO

        CATALOGO[meta["app"]].clave_admin(meta, usuario, nueva)
    return {"dominio": dominio, "usuario": usuario, "clave": nueva, "url_admin": meta.get("app_admin")}


# --- Revisión y actualización ---


def _no_propia(meta):
    if meta.get("app") == "propia":
        raise ErrorSitio("es una aplicación propia: se administra desde «Gestionar»")


def revisar(dominio):
    meta = leer_meta(dominio)
    _no_propia(meta)
    app = meta.get("app")
    if app == "wordpress":
        version = _wp(meta, "core", "version").strip()
        nucleo = json.loads(_wp(meta, "core", "check-update", "--format=json").strip() or "[]")
        complementos = json.loads(_wp(meta, "plugin", "list", "--update=available", "--format=json") or "[]")
        temas = json.loads(_wp(meta, "theme", "list", "--update=available", "--format=json") or "[]")
        try:
            _wp(meta, "core", "verify-checksums", _EXCLUIR)
            integridad = "correcta"
        except ErrorSitio as e:
            integridad = f"ALTERADA: {e}"
        return {
            "dominio": dominio,
            "app": app,
            "version": version,
            "actualizaciones": {
                "nucleo": [n.get("version") for n in nucleo],
                "complementos": [c.get("name") for c in complementos],
                "temas": [t.get("name") for t in temas],
            },
            "integridad_nucleo": integridad,
        }
    if app == "joomla":
        salida = _joomla_cli(meta, "core:check-updates")
        return {"dominio": dominio, "app": app, "version": meta.get("app_version"), "detalle": salida.strip()[-500:]}
    if app:
        from apps import CATALOGO

        modulo = CATALOGO[app]
        return {"dominio": dominio, "app": app, "version": meta.get("app_version"),
                "detalle": f"{modulo.NOMBRE} se actualiza desde su propia administración (avisa cuando hay versión nueva)."}
    raise ErrorSitio("el sitio no tiene una aplicación instalada")


def actualizar(dominio):
    meta = leer_meta(dominio)
    _no_propia(meta)
    if meta.get("app") == "wordpress":
        _wp(meta, "core", "update")
        _wp(meta, "core", "update-db")
        _wp(meta, "plugin", "update", "--all")
        _wp(meta, "theme", "update", "--all")
        _wp(meta, "language", "core", "update")
        _quitar_informativos(meta)
    elif meta.get("app") == "joomla":
        _joomla_cli(meta, "core:update")
    elif meta.get("app"):
        return revisar(dominio)
    else:
        raise ErrorSitio("el sitio no tiene una aplicación instalada")
    return revisar(dominio)


def cron():
    """Tareas programadas de todas las aplicaciones (systemd, cada 5 minutos)."""
    hechos = []
    for meta in todos_los_meta():
        try:
            if meta.get("app") == "wordpress":
                _wp(meta, "cron", "event", "run", "--due-now", tiempo=280)
            elif meta.get("app") == "joomla":
                _joomla_cli(meta, "scheduler:run", "--all")
            elif meta.get("app"):
                from apps import CATALOGO

                modulo = CATALOGO.get(meta["app"])
                if not modulo or not hasattr(modulo, "cron"):
                    continue
                modulo.cron(meta)
            else:
                continue
            hechos.append(meta["dominio"])
        except ErrorSitio:
            continue
    return {"ejecutado": hechos}


def guardar_usuario_admin(meta, usuario):
    meta["app_usuario"] = usuario
    guardar_meta(meta)


def tienda(dominio):
    """WooCommerce (GPLv3) en un sitio con WordPress: tienda en línea libre, desde wordpress.org,
    con cada archivo comprobado contra las sumas de wordpress.org y en español."""
    meta = leer_meta(dominio)
    if meta.get("app") != "wordpress":
        raise ErrorSitio("la tienda (WooCommerce) se instala sobre un sitio con WordPress")
    _wp(meta, "plugin", "install", "woocommerce", "--activate")
    _wp(meta, "plugin", "verify-checksums", "woocommerce")
    try:
        _wp(meta, "language", "plugin", "install", "woocommerce", "es_ES")
    except ErrorSitio:
        pass
    meta["tienda"] = True
    guardar_meta(meta)
    return {"dominio": dominio, "tienda": True, "url_admin": f"{_url(meta)}/wp-admin/admin.php?page=wc-admin"}
