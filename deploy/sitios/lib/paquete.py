"""Subir su propio paquete (.zip, .tar.gz, .rar o .7z) a un sitio vacío desde el panel.

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
RE_ARCHIVO = re.compile(r"^[0-9a-f]{32}\.(zip|tar\.gz|tgz|rar|7z)$")
TOPE_EXTRAIDO = 3 * 1024**3  # 3 GB descomprimido
TOPE_ARCHIVOS = 150_000
CARPETAS_WEB = ("public", "public_html", "htdocs", "web", "www", "html")
ENTRADAS = ("index.php", "index.html", "index.htm")


def _medir(ruta):
    """Tamaño y número de archivos una vez descomprimido (sin descomprimir)."""
    if ruta.lower().endswith((".rar", ".7z")):
        import archivos_7z
        return archivos_7z.medir(ruta)
    if zipfile.is_zipfile(ruta):
        with zipfile.ZipFile(ruta) as z:
            info = z.infolist()
            return sum(i.file_size for i in info), len(info)
    try:
        with tarfile.open(ruta) as t:
            miembros = t.getmembers()
            return sum(m.size for m in miembros), len(miembros)
    except tarfile.TarError:
        raise ErrorSitio("el archivo no es un .zip, .tar.gz, .rar ni .7z válido")


def _raiz_web(publico):
    """Carpeta que sirve la web: la raíz si tiene index; si no, la típica de su marco (public/, htdocs/…)."""
    if any(os.path.isfile(os.path.join(publico, e)) for e in ENTRADAS):
        return ""
    for carpeta in CARPETAS_WEB:
        if any(os.path.isfile(os.path.join(publico, carpeta, e)) for e in ENTRADAS):
            return carpeta
    return ""


def instalar(dominio, archivo, con_bd, base=None):
    """`base`: respaldo .sql o .sql.gz de la base (migración desde otro hosting); implica preparar la base."""
    from aplicaciones import _publico_vacio

    import migracion
    import sitio

    if not RE_ARCHIVO.match(archivo or ""):
        raise ErrorSitio("archivo subido no válido")
    ruta = os.path.join(SUBIDAS, archivo)
    if base is not None and not migracion.RE_BASE.match(base):
        raise ErrorSitio("respaldo de base no válido")
    ruta_base = os.path.join(SUBIDAS, base) if base else None
    try:
        if ruta_base and (not os.path.isfile(ruta_base) or os.path.islink(ruta_base)):
            raise ErrorSitio("no se encontró el respaldo de la base subido")
        meta = leer_meta(dominio)
        if meta.get("app"):
            raise ErrorSitio("el sitio ya tiene una aplicación: suba el paquete a un sitio vacío")
        if not os.path.isfile(ruta) or os.path.islink(ruta):
            raise ErrorSitio("no se encontró el archivo subido")
        tamano, cantidad = _medir(ruta)
        if tamano > TOPE_EXTRAIDO or cantidad > TOPE_ARCHIVOS:
            raise ErrorSitio("el paquete descomprimido es demasiado grande (máximo 3 GB y 150 000 archivos)")
        _publico_vacio(meta)
        try:
            return _extraer_y_conectar(meta, dominio, ruta, ruta_base, con_bd)
        except BaseException:
            # El sitio vuelve a quedar vacío y sin base: se puede volver a intentar.
            from aplicaciones import _deshacer_instalacion

            meta["app"] = None
            meta.pop("paquete", None)
            _deshacer_instalacion(meta)
            sitio.escribir_vhost(meta)
            sitio.recargar_nginx()
            raise
    finally:
        for r in (ruta, ruta_base):
            if r and os.path.lexists(r):
                os.remove(r)


def _extraer_y_conectar(meta, dominio, ruta, ruta_base, con_bd):
    from aplicaciones import crear_bd
    from apps import descargas
    from apps.receta import permisos

    import migracion
    import sitio

    with tempfile.TemporaryDirectory(dir=meta["tmp"]) as tmp:
        descargas.extraer(ruta, tmp)
        for n in os.listdir(tmp):
            shutil.move(os.path.join(tmp, n), os.path.join(meta["publico"], n))
    permisos(meta)
    meta["app"] = "paquete"
    meta["paquete"] = {"raiz": _raiz_web(meta["publico"]), "suma": descargas.suma(ruta, "sha256")}
    respuesta = {"dominio": dominio, "app": "paquete", "raiz_web": meta["paquete"]["raiz"] or "publico",
                 "url": ("https://" if meta.get("ssl") else "http://") + dominio + "/"}
    meta["app_admin"] = respuesta["url"]
    if con_bd or ruta_base:
        bd, usuario, clave = crear_bd(meta)
        meta["bd"] = bd
        guardar_meta(meta)
        respuesta.update({"base_datos": bd, "bd_usuario": usuario, "bd_clave": clave, "bd_servidor": "localhost"})
        if ruta_base:
            respuesta["tablas"] = migracion.importar(meta, ruta_base, bd, usuario, clave)
            migrado = migracion.conectar(meta, meta["paquete"]["raiz"], bd, usuario, clave)
            respuesta["migracion"] = migrado
            # WordPress o Joomla en la raíz: el sitio pasa a ser de esa aplicación (reglas, «Entrar», seguridad).
            if migrado.get("aplicacion") in ("wordpress", "joomla") and not meta["paquete"]["raiz"]:
                meta["app"] = migrado["aplicacion"]
                meta["app_usuario"] = migrado.get("admin_usuario")
                meta["app_admin"] = respuesta["url"] + ("wp-admin/" if meta["app"] == "wordpress" else "administrator/")
                respuesta["app"] = meta["app"]
    guardar_meta(meta)
    sitio.escribir_vhost(meta)
    sitio.recargar_nginx()
    return respuesta
