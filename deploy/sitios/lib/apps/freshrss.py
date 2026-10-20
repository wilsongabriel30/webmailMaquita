"""FreshRSS — lector de noticias (RSS/Atom) propio y multiusuario (AGPLv3). https://freshrss.org

FreshRSS no adjunta paquetes a sus versiones: se descarga el archivo de la última etiqueta estable desde
GitHub por HTTPS (verificación «HTTPS»). Se instala con su línea de órdenes (cli/do-install.php y
cli/create-user.php). La web se sirve desde «p/»: el código y los datos (data/, con la configuración,
las claves y la caché) quedan fuera del alcance de la web.
"""

import os

from comun import ErrorSitio

from . import receta

NOMBRE = "FreshRSS"
DESCRIPCION = "Lector de noticias: sigue sitios y blogs por RSS en un solo lugar, también desde el celular."
LICENCIA = "AGPLv3"
CATEGORIA = "Utilidades"
VERIFICACION = "HTTPS"
RAIZ_WEB = "p"

# Solo se publica «p/»: el código y data/ no son alcanzables. Sin límite de peticiones propio: la lectura
# (marcar como leído, favoritos) se hace con muchas peticiones POST a /i/.
REGLAS_NGINX = ""


def _cli(meta, orden, *args):
    return receta.php(meta, f"cli/{orden}.php", *args)


def instalar(meta, bd, bd_usuario, bd_clave, titulo, correo, admin_usuario, admin_clave):
    fuente = receta.github_etiqueta("FreshRSS/FreshRSS",
                                    "https://github.com/FreshRSS/FreshRSS/archive/refs/tags/{etiqueta}.tar.gz")
    receta.preparar(meta, fuente, "FreshRSS")
    if not os.path.isfile(os.path.join(meta["publico"], "cli", "do-install.php")):
        raise ErrorSitio("el paquete de FreshRSS no tiene la estructura esperada")
    # Valores por omisión de los usuarios nuevos: español y hora de Ecuador.
    receta.escribir(meta, "data/config-user.custom.php",
                    "<?php\nreturn ['language' => 'es', 'timezone' => 'America/Guayaquil'];\n")
    _cli(meta, "do-install", f"--default-user={admin_usuario}", "--auth-type=form", "--environment=production",
         f"--base-url={receta.url(meta)}", "--language=es", f"--title={titulo}", "--api-enabled",
         "--disable-update", "--db-type=mysql", "--db-host=localhost", f"--db-user={bd_usuario}",
         f"--db-password={bd_clave}", f"--db-base={bd}", "--db-prefix=freshrss_")
    _cli(meta, "create-user", f"--user={admin_usuario}", f"--password={admin_clave}", "--language=es",
         f"--email={correo}")
    receta.permisos(meta)
    os.chmod(os.path.join(meta["publico"], "data", "config.php"), 0o640)
    return receta.url(meta) + "/i/"


def clave_admin(meta, usuario, nueva):
    _cli(meta, "update-user", f"--user={usuario}", f"--password={nueva}")


def cron(meta):
    """Actualiza las fuentes de todos los usuarios (FreshRSS respeta el intervalo de cada fuente)."""
    receta.php(meta, "app/actualize_script.php", tiempo=280)


def cambiar_url(meta):
    """FreshRSS guarda su dirección (base_url de data/config.php): se cambia con su propia línea de órdenes."""
    _cli(meta, "reconfigure", f"--base-url={receta.url(meta)}")
    # reconfigure reescribe data/config.php con los permisos por omisión: se dejan como al instalar.
    receta.permisos(meta)
    os.chmod(os.path.join(meta["publico"], "data", "config.php"), 0o640)
