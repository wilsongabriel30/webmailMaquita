"""Omeka S — colecciones digitales de archivos, bibliotecas y museos (GPLv3). https://omeka.org/s/

Paquete oficial adjunto a la versión de GitHub (omeka/omeka-s, SHA-256 calculada por GitHub). Omeka S no
trae instalador por línea de órdenes: se escribe config/database.ini y se recorre su instalador web
(/install, un único formulario) desde el servidor. Las miniaturas se hacen con la extensión Imagick y las
tareas en segundo plano se ejecutan en la misma petición, porque PHP-FPM del sitio no puede lanzar
procesos (sin exec). Omeka entra con el CORREO del administrador, no con el nombre de usuario.
"""

import re
import time

from comun import ErrorSitio

from . import receta

NOMBRE = "Omeka S"
DESCRIPCION = "Colecciones digitales: archivo, biblioteca o museo en línea con fichas, imágenes y exposiciones."
LICENCIA = "GPLv3"
CATEGORIA = "Archivos y galerías"
VERIFICACION = "GitHub"
ENTRA_CON_CORREO = True  # el panel muestra el correo como usuario de acceso
RAIZ_WEB = ""
BD = "mariadb"

# config/ (database.ini), logs/ y el código PHP interno no se sirven; de application/, modules/ y themes/
# solo los recursos estáticos (CSS, JS, imágenes). files/ ya no ejecuta PHP por la plantilla general.
REGLAS_NGINX = r"""
    location = /login {
        limit_req zone=sitios_login burst=10 nodelay;
        limit_req zone=sitios_general burst=80 nodelay;
        try_files $$uri /index.php?$$args;
    }
    location ~ ^/(?:config|logs|vendor)/ { deny all; }
    location ~ ^/(?:application|modules|themes)/.*\.(?:php|phtml|po|mo|json|lock|xml|md|txt)$$ { deny all; }
    location ~ ^/(?:composer\.(?:json|lock)|README\.md|LICENSE)$$ { deny all; }
    # Solo index.php es punto de entrada (Omeka no usa otros).
    location = /index.php {
        include snippets/fastcgi-php.conf;
        fastcgi_pass unix:$socket;
        fastcgi_read_timeout 300s;
    }
    location ~ \.php(?:/|$$) { deny all; }
"""


def _configurar(meta, bd, bd_usuario, bd_clave):
    receta.escribir(meta, "config/database.ini",
                    f'user     = "{bd_usuario}"\npassword = "{bd_clave}"\ndbname   = "{bd}"\nhost     = "localhost"\n',
                    0o440)
    ruta = "config/local.config.php"
    with open(f"{meta['publico']}/{ruta}") as f:
        texto = f.read()
    cambios = (("'Omeka\\File\\Thumbnailer\\ImageMagick'", "'Omeka\\File\\Thumbnailer\\Imagick'"),
               ("'locale' => 'en_US'", "'locale' => 'es'"),
               ("'Omeka\\File\\Store' => 'Omeka\\File\\Store\\Local',",
                "'Omeka\\File\\Store' => 'Omeka\\File\\Store\\Local',\n"
                "            'Omeka\\Job\\DispatchStrategy' => 'Omeka\\Job\\DispatchStrategy\\Synchronous',"))
    for viejo, nuevo in cambios:
        if viejo not in texto:
            raise ErrorSitio("la configuración de Omeka S no tiene el formato esperado")
        texto = texto.replace(viejo, nuevo)
    receta.escribir(meta, ruta, texto, 0o440)


def instalar(meta, bd, bd_usuario, bd_clave, titulo, correo, admin_usuario, admin_clave):
    fuente = receta.github("omeka/omeka-s", r"omeka-s-[0-9.]+\.zip")
    receta.preparar(meta, fuente, "Omeka S")
    _configurar(meta, bd, bd_usuario, bd_clave)
    web = receta.Web(meta)
    try:
        for _ in range(10):
            # PHP-FPM se recarga al crear o cambiar sitios: se espera a que el grupo del sitio responda.
            codigo, html, _ = web.pedir("/install")
            if codigo not in ("502", "503", "504"):
                break
            time.sleep(3)
        if codigo != "200" or "installation_title" not in html:
            raise ErrorSitio(f"el instalador de Omeka S no respondió (HTTP {codigo})")
        codigo, html, destino = web.pedir("/install", {
            "user[email]": correo, "user[email-confirm]": correo, "user[name]": admin_usuario,
            "user[password-confirm][password]": admin_clave,
            "user[password-confirm][password-confirm]": admin_clave,
            "settings[installation_title]": titulo, "settings[time_zone]": "America/Guayaquil",
            "settings[locale]": "es", "submit": "Enviar"})
        if codigo != "302" or not destino.endswith("/login"):
            avisos = "; ".join(re.findall(r'<li class="error">\s*([^<]+?)\s*</li>', html))[:300]
            raise ErrorSitio(f"el instalador de Omeka S no terminó (HTTP {codigo}) {avisos}".strip())
    finally:
        web.cerrar()
    # Comprobación con una sesión nueva: el administrador entra (Omeka identifica por correo).
    web = receta.Web(meta)
    try:
        _, html, _ = web.pedir("/login")
        codigo, _, destino = web.pedir("/login", {"email": correo, "password": admin_clave, "submit": "Entrar",
                                                  "loginform_csrf": web.campo(html, "loginform_csrf")})
        if codigo != "302" or not destino.endswith("/admin"):
            raise ErrorSitio("la instalación de Omeka S quedó incompleta: el administrador no puede entrar")
    finally:
        web.cerrar()
    return receta.url(meta) + "/login"


def clave_admin(meta, usuario, nueva):
    """Omeka guarda password_hash() en user.password_hash; el administrador se creó con ese nombre."""
    receta.sql(meta, f"UPDATE `user` SET password_hash = {receta.literal(receta.hash_clave(nueva, 'PASSWORD_DEFAULT'))} "
                     f"WHERE name = {receta.literal(usuario)} AND role = 'global_admin';")
