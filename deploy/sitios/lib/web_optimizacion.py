"""Optimización por sitio, pensada para quien entra por ADSL rural o satélite (poco ancho de banda y mucha latencia):

- Compresión gzip de texto, CSS, JavaScript, JSON, SVG y fuentes (y brotli si nginx tiene el módulo). De serie, sí.
- Caché del navegador para los archivos estáticos (CSS, JS, imágenes, fuentes): el visitante no los vuelve a
  descargar en cada página. De serie, 30 días (lo de siempre).
- Caché de página (fastcgi_cache) para sitios PHP, activable: la portada y las entradas se sirven sin pasar por
  PHP durante unos minutos y, si PHP cae o tarda, se sirve la última copia. De serie, no.

La caché de página nunca guarda ni sirve lo que es de una persona: se salta con sesión iniciada (cookies de
WordPress, WooCommerce, Joomla o de sesión PHP), en /wp-admin, el inicio de sesión, el carrito, las búsquedas, los
POST y con autenticación básica. nginx tampoco guarda respuestas que crean una cookie.
"""

import glob
import os
import shutil

import web_comun as w
from comun import ErrorSitio

CACHE_RAIZ = "/var/cache/nginx/sitios"
MODULOS_NGINX = "/etc/nginx/modules-enabled"
USUARIO_NGINX = "www-data"
CADUCIDADES = ("off", "1h", "1d", "7d", "30d", "180d", "365d")
DEFECTO = {"compresion": True, "estaticos": "30d", "cache_pagina": False, "cache_minutos": 10}
TIPOS = ("text/plain text/css text/xml text/javascript application/javascript application/json application/xml "
         "application/rss+xml application/atom+xml application/manifest+json image/svg+xml image/x-icon "
         "font/ttf font/otf application/vnd.ms-fontobject")
# Lo que nunca sale de la caché de página (y nunca entra en ella).
SIN_CACHE_RUTAS = (r"/wp-admin/|/wp-login\.php|/xmlrpc\.php|/wp-[a-z-]+\.php|/feed/|sitemap[a-z0-9_-]*\.xml|"
                   r"/administrator/|/carrito|/cart|/checkout|/finalizar-compra|/my-account|/mi-cuenta|/user/|/admin")
SIN_CACHE_COOKIES = (r"wordpress_logged_in|wordpress_sec|wp-postpass|wordpress_no_cache|comment_author|"
                     r"woocommerce_items_in_cart|woocommerce_cart_hash|wp_woocommerce_session|PHPSESSID|"
                     r"joomla_user_state|SESS[0-9a-f]+|[0-9a-f]{32}=")


def hay_brotli():
    """El módulo que comprime al vuelo (brotli-filter); el «static» solo sirve archivos .br ya hechos."""
    return any("brotli" in n and "filter" in n for n in map(os.path.basename, glob.glob(os.path.join(MODULOS_NGINX, "*"))))


def _directivas_propias(meta):
    """Directivas de las reglas propias del sitio («Avanzado»): si ya ponen gzip, no se repite (nginx rechaza una
    directiva duplicada y el sitio dejaría de cargar al regenerar)."""
    import avanzado

    try:
        with open(avanzado.ruta_extra(meta["dominio"])) as f:
            return {d for d, _ in avanzado._sentencias(f.read())}
    except OSError:
        return set()


def zona(meta):
    return f"sitio_{meta['usuario']}"


def carpeta_cache(dominio):
    return os.path.join(CACHE_RAIZ, dominio)


def validar(meta, datos):
    if not isinstance(datos, dict):
        raise ErrorSitio("ajustes de optimización no válidos")
    import nginx_web

    limpio = dict(DEFECTO)
    limpio["compresion"] = w.booleano(datos.get("compresion", DEFECTO["compresion"]))
    estaticos = str(datos.get("estaticos", DEFECTO["estaticos"]))
    if estaticos not in CADUCIDADES:
        raise ErrorSitio(f"caché del navegador no válida (una de: {', '.join(CADUCIDADES)})")
    limpio["estaticos"] = estaticos
    limpio["cache_pagina"] = w.booleano(datos.get("cache_pagina", False))
    if limpio["cache_pagina"] and not nginx_web.con_php(meta):
        raise ErrorSitio("la caché de página es para sitios PHP")
    try:
        minutos = int(datos.get("cache_minutos", DEFECTO["cache_minutos"]))
    except (TypeError, ValueError):
        raise ErrorSitio("minutos de caché no válidos")
    if not 1 <= minutos <= 1440:
        raise ErrorSitio("la caché de página dura entre 1 y 1440 minutos")
    limpio["cache_minutos"] = minutos
    return limpio


def _ajustes(meta, ajustes):
    try:
        return validar(meta, ajustes) if ajustes else dict(DEFECTO)
    except ErrorSitio:
        return dict(DEFECTO)  # un meta estropeado no debe impedir escribir el vhost: se vuelve a lo de serie


def fragmentos(meta, ajustes):
    import nginx_web

    a = _ajustes(meta, ajustes)
    salida = {"estaticos": f"expires {a['estaticos']};"}
    servidor = []
    propias = _directivas_propias(meta)
    if a["compresion"] and "gzip" not in propias:
        servidor += ["# Compresión (menos datos por la línea: ADSL rural y satélite)", "gzip on;", "gzip_vary on;",
                     "gzip_proxied any;", "gzip_comp_level 5;", "gzip_min_length 1024;", f"gzip_types {TIPOS};"]
        if hay_brotli() and "brotli" not in propias:
            servidor += ["brotli on;", "brotli_comp_level 5;", "brotli_min_length 1024;", f"brotli_types {TIPOS};"]
    if a["cache_pagina"] and nginx_web.con_php(meta):
        servidor += [
            "# Caché de página: nunca con sesión iniciada, en la administración, el carrito ni los POST",
            "set $sitio_sin_cache 0;",
            'if ($request_method !~ "^(?:GET|HEAD)$") { set $sitio_sin_cache 1; }',
            'if ($query_string != "") { set $sitio_sin_cache 1; }',
            'if ($http_authorization != "") { set $sitio_sin_cache 1; }',
            f'if ($request_uri ~* "{SIN_CACHE_RUTAS}") {{ set $sitio_sin_cache 1; }}',
            f'if ($http_cookie ~* "{SIN_CACHE_COOKIES}") {{ set $sitio_sin_cache 1; }}',
        ]
        salida["php"] = "\n".join([
            f"fastcgi_cache {zona(meta)};",
            'fastcgi_cache_key "$scheme$request_method$host$request_uri";',
            f"fastcgi_cache_valid 200 301 302 {a['cache_minutos']}m;",
            "fastcgi_cache_valid 404 1m;",
            "fastcgi_cache_use_stale error timeout updating http_500 http_503;",
            "fastcgi_cache_background_update on;",
            "fastcgi_cache_lock on;",
            "fastcgi_cache_bypass $sitio_sin_cache;",
            "fastcgi_no_cache $sitio_sin_cache;",
        ])
        salida["http"] = (f"fastcgi_cache_path {carpeta_cache(meta['dominio'])} levels=1:2 keys_zone={zona(meta)}:10m "
                          f"max_size=256m inactive=1d use_temp_path=off;")
    salida["servidor"] = "\n".join(servidor)
    return salida


def preparar_cache(meta):
    """Carpeta de la caché de página (de www-data, que es quien escribe en ella), si está activa."""
    a = _ajustes(meta, (meta.get("web") or {}).get("optimizacion"))
    if not a["cache_pagina"]:
        return
    ruta = carpeta_cache(meta["dominio"])
    os.makedirs(ruta, mode=0o700, exist_ok=True)
    if os.geteuid() == 0:
        import pwd

        pw = pwd.getpwnam(USUARIO_NGINX)
        os.chown(ruta, pw.pw_uid, pw.pw_gid)


def borrar_cache(dominio):
    shutil.rmtree(carpeta_cache(dominio), ignore_errors=True)


def purgar(dominio):
    """Vacía la caché de página del sitio (tras publicar algo que debe verse ya). No hace falta recargar nginx."""
    from comun import leer_meta

    meta = leer_meta(dominio)
    ruta = carpeta_cache(dominio)
    borrados = 0
    if os.path.isdir(ruta) and not os.path.islink(ruta):
        for nombre in os.listdir(ruta):
            destino = os.path.join(ruta, nombre)
            for _raiz, _dirs, archivos in os.walk(destino):
                borrados += len(archivos)
            if os.path.isdir(destino) and not os.path.islink(destino):
                shutil.rmtree(destino, ignore_errors=True)
            else:
                os.remove(destino)
    return {"dominio": meta["dominio"], "purgados": borrados}


def estado(meta, ajustes):
    import nginx_web

    return {**_ajustes(meta, ajustes), "brotli": hay_brotli(), "php": nginx_web.con_php(meta),
            "caducidades": list(CADUCIDADES)}
