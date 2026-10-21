"""Funciones web por sitio (panel → Sitios web → «Web»): el mecanismo común de nginx.

Cada función (redirecciones, carpetas con contraseña, páginas de error, hotlinking, bloqueo de IP y optimización)
valida sus datos y los guarda ya limpios en el meta del sitio (meta["web"][<función>]). Este módulo genera con
ellos los archivos que incluye el vhost del sitio:

    /etc/maquita-sitios/nginx-web/<dominio>/servidor.conf    dentro de server{}, al final de lo común
    /etc/maquita-sitios/nginx-web/<dominio>/estaticos.conf   dentro de la location de archivos estáticos
    /etc/maquita-sitios/nginx-web/<dominio>/php.conf         dentro de la location de PHP
    /etc/nginx/conf.d/sitios-cache-<dominio>.conf            contexto http: zona de la caché de página (si la hay)

Un cambio se aplica siempre igual: copia de lo que hay, se escriben los archivos nuevos y el vhost, `nginx -t`; si
nginx los rechaza se restauran las copias (el meta no llega a cambiar) y se devuelve el motivo. Como todo sale del
meta, «maquita-sitios regenerar» (y cualquier otra reescritura del vhost) los rehace con los mismos ajustes.
"""

import copy
import fcntl
import importlib
import os
import shutil
import subprocess

from comun import META_DIR, ErrorSitio, guardar_meta, leer_meta

RAIZ = "/etc/maquita-sitios/nginx-web"
HTTP_CONF = "/etc/nginx/conf.d"
NGINX_PRUEBA = ["nginx", "-t"]
CERROJO = os.path.join(META_DIR, ".nginx-web.lock")
# Función → módulo que la valida y genera su trozo de configuración. El orden es el del archivo: el bloqueo de IP
# y las redirecciones primero (la redirección de todo el dominio debe ir antes que las de una ruta).
FUNCIONES = {
    "bloqueo": "web_bloqueo",
    "redirecciones": "web_redirecciones",
    "hotlink": "web_hotlink",
    "privacidad": "web_privacidad",
    "errores": "web_errores",
    "optimizacion": "web_optimizacion",
}
PARTES = ("servidor", "estaticos", "php")


def modulo(funcion):
    return importlib.import_module(FUNCIONES[funcion])


def carpeta(dominio):
    return os.path.join(RAIZ, dominio)


def ruta_http(dominio):
    return os.path.join(HTTP_CONF, f"sitios-cache-{dominio}.conf")


def rutas(dominio):
    """Todos los archivos que genera este módulo para un sitio (los que se copian antes de cada cambio)."""
    return [os.path.join(carpeta(dominio), f"{p}.conf") for p in PARTES] + [ruta_http(dominio)]


def raiz_web(meta):
    """Carpeta que sirve nginx como «root» (la de las páginas de error), o None si el sitio no la tiene."""
    app = meta.get("app")
    if app == "propia":
        propia = meta.get("propia") or {}
        return propia.get("raiz") if propia.get("tipo") == "estatico" else None
    if app == "paquete" and (meta.get("paquete") or {}).get("raiz"):
        return f"{meta['publico']}/{meta['paquete']['raiz']}"
    if app and app not in ("wordpress", "joomla", "paquete"):
        try:
            from apps import CATALOGO

            if app in CATALOGO and CATALOGO[app].RAIZ_WEB:
                return f"{meta['publico']}/{CATALOGO[app].RAIZ_WEB}"
        except ImportError:
            pass
    return meta["publico"]


def con_php(meta):
    """Sitio servido por PHP-FPM (todo menos las aplicaciones propias)."""
    return meta.get("app") != "propia"


# --- Generación ---


def generar(meta):
    """{parte: texto} de los archivos del sitio, con los ajustes guardados (o los de serie)."""
    trozos = {p: [] for p in PARTES + ("http",)}
    for funcion in FUNCIONES:
        ajustes = (meta.get("web") or {}).get(funcion)
        for parte, texto in modulo(funcion).fragmentos(meta, ajustes).items():
            if texto:
                trozos[parte].append(texto.rstrip("\n") + "\n")
    salida = {}
    for parte, lista in trozos.items():
        cabecera = "# Generado por maquita-sitios (panel → Sitios web → Web). No editar a mano.\n"
        salida[parte] = cabecera + "\n".join(lista) if lista else ("" if parte == "http" else cabecera)
    return salida


def _escribir(ruta, texto):
    os.makedirs(os.path.dirname(ruta), mode=0o755, exist_ok=True)
    tmp = ruta + ".tmp"
    with open(tmp, "w") as f:
        f.write(texto)
    os.chmod(tmp, 0o644)
    os.replace(tmp, ruta)


def escribir(meta):
    """Escribe los archivos del sitio. La llama sitio.escribir_vhost antes de escribir el vhost."""
    textos = generar(meta)
    for parte in PARTES:
        _escribir(os.path.join(carpeta(meta["dominio"]), f"{parte}.conf"), textos[parte])
    if textos["http"]:
        _escribir(ruta_http(meta["dominio"]), textos["http"])
    elif os.path.exists(ruta_http(meta["dominio"])):
        os.remove(ruta_http(meta["dominio"]))
    import web_optimizacion

    web_optimizacion.preparar_cache(meta)


def quitar(dominio):
    """Al dar de baja el sitio: sus archivos de nginx y su caché de página."""
    shutil.rmtree(carpeta(dominio), ignore_errors=True)
    if os.path.exists(ruta_http(dominio)):
        os.remove(ruta_http(dominio))
    import web_optimizacion

    web_optimizacion.borrar_cache(dominio)


# --- Aplicar un cambio (copia, nginx -t y marcha atrás) ---


def _copiar(lista):
    copia = {}
    for ruta in lista:
        try:
            with open(ruta, "rb") as f:
                copia[ruta] = f.read()
        except FileNotFoundError:
            copia[ruta] = None
    return copia


def _restaurar(copia):
    for ruta, contenido in copia.items():
        if contenido is None:
            if os.path.lexists(ruta):
                os.remove(ruta)
            continue
        os.makedirs(os.path.dirname(ruta), exist_ok=True)
        tmp = ruta + ".restaurando"
        with open(tmp, "wb") as f:
            f.write(contenido)
        os.chmod(tmp, 0o644 if not ruta.endswith(".htpasswd") else 0o640)
        os.replace(tmp, ruta)


def _probar():
    r = subprocess.run(NGINX_PRUEBA, capture_output=True, text=True, timeout=60)
    if r.returncode == 0:
        return None
    motivo = [l for l in (r.stderr or "").splitlines() if "emerg" in l or "error" in l]
    return motivo[0].split("] ", 1)[-1][:300] if motivo else "configuración no válida"


def _recargar():
    import sitio

    sitio.recargar_nginx()


class _Cerrojo:
    """Un cambio a la vez: dos guardados simultáneos no deben mezclar sus copias."""

    def __enter__(self):
        os.makedirs(os.path.dirname(CERROJO), mode=0o700, exist_ok=True)
        self.f = open(CERROJO, "a")
        fcntl.flock(self.f, fcntl.LOCK_EX)
        return self

    def __exit__(self, *_):
        fcntl.flock(self.f, fcntl.LOCK_UN)
        self.f.close()


def aplicar(dominio, funcion, ajustes, extra_rutas=(), preparar=None):
    """Guarda los ajustes ya validados de una función y los publica.

    `preparar` (opcional) escribe archivos propios de la función antes de probar (p. ej. las claves de una carpeta);
    sus rutas van en `extra_rutas` para que se copien y se restauren con lo demás si nginx rechaza el cambio.
    """
    import sitio

    with _Cerrojo():
        meta = leer_meta(dominio)
        nuevo = copy.deepcopy(meta)
        if ajustes is None:
            (nuevo.get("web") or {}).pop(funcion, None)
        else:
            nuevo.setdefault("web", {})[funcion] = ajustes
        copia = _copiar(rutas(dominio) + [sitio._ruta_vhost(dominio)] + list(extra_rutas))
        try:
            if preparar:
                preparar(nuevo)
            sitio.escribir_vhost(nuevo)
            motivo = _probar()
        except Exception:
            _restaurar(copia)
            raise
        if motivo:
            _restaurar(copia)
            raise ErrorSitio(f"nginx rechazó el cambio y se dejó la configuración anterior: {motivo}")
        guardar_meta(nuevo)
    _recargar()
    return nuevo


def ver(dominio):
    """Estado de todas las funciones web del sitio para el panel."""
    meta = leer_meta(dominio)
    salida = {"dominio": dominio, "php": con_php(meta), "raiz_web": raiz_web(meta) is not None}
    for funcion in FUNCIONES:
        salida[funcion] = modulo(funcion).estado(meta, (meta.get("web") or {}).get(funcion))
    return salida
