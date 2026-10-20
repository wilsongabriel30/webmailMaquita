"""OpenCart — tienda en línea: catálogo, carrito, pagos y pedidos (GPLv3). https://www.opencart.com

Paquete oficial adjunto a la versión de GitHub (SHA-256 calculada por GitHub); se publica su carpeta
«upload/». Se instala con su línea de órdenes (install/cli_install.php) y luego se hace lo que pide su
propio aviso de seguridad: se borra install/, la carpeta storage/ (registros, sesiones, librerías) pasa
a la carpeta privada del sitio y la administración deja de estar en «/admin/».
"""

import html
import json
import os
import re
import secrets
import shutil

from comun import ErrorSitio, ejecutar

from . import receta

NOMBRE = "OpenCart"
DESCRIPCION = "Tienda en línea: catálogo de productos, carrito, pagos, envíos y pedidos."
LICENCIA = "GPLv3"
CATEGORIA = "Tienda en línea"
VERIFICACION = "GitHub"
UN_SOLO_DOMINIO = True  # enlaces y sesión van al dominio de HTTP_SERVER: www y alias redirigen al principal
RAIZ_WEB = ""

# system/ solo tiene código PHP; las plantillas twig y la tarea programada no se sirven.
REGLAS_NGINX = r"""
    location ^~ /system/ { deny all; }
    location ^~ /install/ { deny all; }
    location = /cron.php { deny all; }
    location ~* \.twig$$ { deny all; }
"""


def _cambiar(meta, archivo, cambios):
    ruta = os.path.join(meta["publico"], archivo)
    with open(ruta) as f:
        texto = f.read()
    for viejo, nuevo in cambios:
        if viejo not in texto:
            raise ErrorSitio(f"OpenCart: no se encontró «{viejo}» en {archivo}")
        texto = texto.replace(viejo, nuevo)
    receta.escribir(meta, archivo, texto)


def instalar(meta, bd, bd_usuario, bd_clave, titulo, correo, admin_usuario, admin_clave):
    fuente = receta.github("opencart/opencart", r"opencart-[0-9.]+\.zip")
    receta.preparar(meta, fuente, "OpenCart", subcarpeta="upload")
    publico = meta["publico"]
    if not os.path.isfile(os.path.join(publico, "install", "cli_install.php")):
        raise ErrorSitio("el paquete de OpenCart no tiene la estructura esperada")
    for dist, final in (("config-dist.php", "config.php"), ("admin/config-dist.php", "admin/config.php")):
        shutil.copy(os.path.join(publico, dist), os.path.join(publico, final))
    receta.permisos(meta)
    sitio_url = receta.url(meta)
    # El instalador solo trae inglés y francés; el español se agrega después como paquete de idioma.
    salida = receta.php(meta, "install/cli_install.php", "install", "--username", admin_usuario, "--email", correo,
                        "--password", admin_clave, "--http_server", sitio_url + "/", "--language", "en-gb",
                        "--db_driver", "mysqli", "--db_hostname", "localhost", "--db_username", bd_usuario,
                        "--db_password", bd_clave, "--db_database", bd, "--db_port", "3306", "--db_prefix", "oc_")
    if "SUCCESS" not in salida:
        raise ErrorSitio("OpenCart: " + (salida.strip().splitlines() or ["la instalación no terminó"])[0][:300])
    # storage/ fuera de la web (su nombre debe empezar por «storage», como exige OpenCart).
    almacen = receta.privada(meta, "storage")
    origen = os.path.join(publico, "system", "storage")
    for n in os.listdir(origen):
        shutil.move(os.path.join(origen, n), os.path.join(almacen, n))
    os.rmdir(origen)
    ejecutar(["chown", "-R", f"{meta['usuario']}:{meta['usuario']}", almacen])
    cambio_storage = ("define('DIR_STORAGE', DIR_SYSTEM . 'storage/');", f"define('DIR_STORAGE', '{almacen}/');")
    _cambiar(meta, "config.php", [cambio_storage])
    # Administración en una carpeta propia del sitio (menos ataques automáticos a «/admin/»).
    carpeta = "admin_" + secrets.token_hex(3)
    os.rename(os.path.join(publico, "admin"), os.path.join(publico, carpeta))
    _cambiar(meta, f"{carpeta}/config.php", [
        cambio_storage,
        (f"define('HTTP_SERVER', '{sitio_url}/admin/');", f"define('HTTP_SERVER', '{sitio_url}/{carpeta}/');"),
        ("define('DIR_APPLICATION', DIR_OPENCART . 'admin/');", f"define('DIR_APPLICATION', DIR_OPENCART . '{carpeta}/');"),
    ])
    receta.quitar(meta, "install", "config-dist.php", f"{carpeta}/config-dist.php")
    # Datos de la tienda: nombre, correo, Ecuador (Pichincha) y su hora.
    nombre = html.escape(titulo)
    descripcion = json.dumps({"1": {"meta_title": nombre, "meta_description": "", "meta_keyword": ""}})
    ajustes = {"config_name": nombre, "config_owner": nombre, "config_description": descripcion, "config_email": correo,
               "config_country_id": "62", "config_zone_id": "997", "config_timezone": "America/Guayaquil"}
    for clave, valor in ajustes.items():
        receta.sql(meta, f"UPDATE oc_setting SET value = {receta.literal(valor)} "
                         f"WHERE store_id = 0 AND `key` = {receta.literal(clave)};")
    meta["opencart_admin"] = carpeta
    return f"{sitio_url}/{carpeta}/"


def cambiar_url(meta):
    """HTTP_SERVER de config.php (tienda) y HTTP_SERVER/HTTP_CATALOG de la administración; se conserva la
    ruta (/admin_xxxxxx/). La base no guarda la dirección de la tienda principal."""
    m = re.search(r"/(admin_[0-9a-f]+)/?$", meta.get("app_admin") or "")
    carpeta = m.group(1) if m else meta.get("opencart_admin")
    if not carpeta or not os.path.isfile(os.path.join(meta["publico"], carpeta, "config.php")):
        raise ErrorSitio("OpenCart: no se encontró la carpeta de administración")
    patron = r"^(define\('HTTP_(?:SERVER|CATALOG)', ')https?://[^/']+(/[^']*'\);)$"
    for archivo in ("config.php", f"{carpeta}/config.php"):
        receta.reemplazar(meta, archivo, patron, lambda c: c.group(1) + receta.url(meta) + c.group(2))


def clave_admin(meta, usuario, nueva):
    """OpenCart guarda password_hash() en oc_user."""
    if not re.fullmatch(r"[A-Za-z0-9_]+", usuario):
        raise ErrorSitio("usuario no válido")
    receta.sql(meta, f"UPDATE oc_user SET password = {receta.literal(receta.hash_clave(nueva, 'PASSWORD_DEFAULT'))} "
                     f"WHERE username = {receta.literal(usuario)};")


def cron(meta):
    """Tareas programadas de OpenCart (monedas, suscripciones, RGPD). Su cron.php no carga las librerías de
    storage/vendor (Twig): se cargan antes con auto_prepend_file."""
    cargador = os.path.join(meta["tmp"], "storage", "vendor", "autoload.php")
    receta.php(meta, "-d", f"auto_prepend_file={cargador}", "cron.php", tiempo=280)
