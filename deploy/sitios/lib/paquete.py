"""Subir su propio paquete (.zip o .tar.gz) a un sitio vacío desde el panel.

Para aplicaciones que no están en el catálogo: el panel deja el archivo en SUBIDAS y este módulo lo extrae en la
carpeta pública con las mismas protecciones que los paquetes del catálogo (sin rutas fuera del destino, sin
enlaces peligrosos ni archivos que se inflan al descomprimir), detecta la carpeta que debe servir la web
(public/, htdocs/, web/…) y, si se pide, prepara una base de datos MariaDB. La persona termina la instalación
en el asistente propio de la aplicación con los datos de la base que muestra el panel.
"""

import os
import re
import shutil
import tarfile
import tempfile
import zipfile

from comun import ErrorSitio, guardar_meta, leer_meta

SUBIDAS = "/var/lib/maquita-sitios/subidas"
RE_ARCHIVO = re.compile(r"^[0-9a-f]{32}\.(zip|tar\.gz|tgz)$")
TOPE_EXTRAIDO = 3 * 1024**3  # 3 GB descomprimido
TOPE_ARCHIVOS = 150_000
CARPETAS_WEB = ("public", "public_html", "htdocs", "web", "www", "html")
ENTRADAS = ("index.php", "index.html", "index.htm")


def _medir(ruta):
    """Tamaño y número de archivos una vez descomprimido (sin descomprimir)."""
    if zipfile.is_zipfile(ruta):
        with zipfile.ZipFile(ruta) as z:
            info = z.infolist()
            return sum(i.file_size for i in info), len(info)
    try:
        with tarfile.open(ruta) as t:
            miembros = t.getmembers()
            return sum(m.size for m in miembros), len(miembros)
    except tarfile.TarError:
        raise ErrorSitio("el archivo no es un .zip ni un .tar.gz válido")


def _raiz_web(publico):
    """Carpeta que sirve la web: la raíz si tiene index; si no, la típica de su marco (public/, htdocs/…)."""
    if any(os.path.isfile(os.path.join(publico, e)) for e in ENTRADAS):
        return ""
    for carpeta in CARPETAS_WEB:
        if any(os.path.isfile(os.path.join(publico, carpeta, e)) for e in ENTRADAS):
            return carpeta
    return ""


def instalar(dominio, archivo, con_bd):
    from aplicaciones import _publico_vacio, crear_bd
    from apps import descargas
    from apps.receta import permisos

    import sitio

    if not RE_ARCHIVO.match(archivo or ""):
        raise ErrorSitio("archivo subido no válido")
    ruta = os.path.join(SUBIDAS, archivo)
    try:
        meta = leer_meta(dominio)
        if meta.get("app"):
            raise ErrorSitio("el sitio ya tiene una aplicación: suba el paquete a un sitio vacío")
        if not os.path.isfile(ruta) or os.path.islink(ruta):
            raise ErrorSitio("no se encontró el archivo subido")
        tamano, cantidad = _medir(ruta)
        if tamano > TOPE_EXTRAIDO or cantidad > TOPE_ARCHIVOS:
            raise ErrorSitio("el paquete descomprimido es demasiado grande (máximo 3 GB y 150 000 archivos)")
        _publico_vacio(meta)
        with tempfile.TemporaryDirectory(dir=meta["tmp"]) as tmp:
            descargas.extraer(ruta, tmp)
            for n in os.listdir(tmp):
                shutil.move(os.path.join(tmp, n), os.path.join(meta["publico"], n))
        permisos(meta)
        meta["app"] = "paquete"
        meta["paquete"] = {"raiz": _raiz_web(meta["publico"]), "suma": descargas.suma(ruta, "sha256")}
        respuesta = {"dominio": dominio, "app": "paquete", "raiz_web": meta["paquete"]["raiz"] or "publico",
                     "url": ("https://" if meta.get("ssl") else "http://") + dominio + "/"}
        if con_bd:
            bd, usuario, clave = crear_bd(meta)
            meta["bd"] = bd
            respuesta.update({"base_datos": bd, "bd_usuario": usuario, "bd_clave": clave, "bd_servidor": "localhost"})
        meta["app_admin"] = respuesta["url"]
        guardar_meta(meta)
        sitio.escribir_vhost(meta)
        sitio.recargar_nginx()
        return respuesta
    finally:
        if os.path.lexists(ruta):
            os.remove(ruta)
