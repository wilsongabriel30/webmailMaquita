"""Visor de registros del sitio: últimas líneas de error.log y acceso.log de nginx y del registro de PHP.

Solo tres archivos fijos, elegidos por su tipo (el panel no manda rutas): registros/error.log y
registros/acceso.log (carpeta de root) y tmp/php-errores.log, el error_log del pool de PHP-FPM del sitio
(plantillas.py). Este último está en una carpeta que controla el usuario del sitio: podría ser un enlace a
/etc/shadow, así que se abre sin seguir enlaces, tiene que ser un archivo normal y estar en su carpeta.
Se lee desde el final (como mucho TOPE_LECTURA bytes) y el filtro es un texto simple, sin distinguir mayúsculas.
"""

import os
import re
import stat

from comun import ErrorSitio, leer_meta

TIPOS = {"error": ("registros", "error.log"), "acceso": ("registros", "acceso.log"), "php": ("tmp", "php-errores.log")}
TOPE_LINEAS = 1000
TOPE_FILTRO = 100
TOPE_LECTURA = 8 * 1024 * 1024
TOPE_LINEA = 4000


def _abrir(carpeta, nombre):
    ruta = os.path.join(carpeta, nombre)
    if os.path.realpath(os.path.dirname(ruta)) != os.path.realpath(carpeta):
        raise ErrorSitio("registro no válido")
    try:
        fd = os.open(ruta, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    except FileNotFoundError:
        return None
    except OSError:
        raise ErrorSitio("ese registro no es un archivo normal (¿un enlace simbólico?)")
    if not stat.S_ISREG(os.fstat(fd).st_mode):
        os.close(fd)
        raise ErrorSitio("ese registro no es un archivo normal")
    return os.fdopen(fd, "rb")


def ultimas(dominio, tipo, lineas, filtro=None):
    if tipo not in TIPOS:
        raise ErrorSitio("registro no válido (error, acceso o php)")
    if not isinstance(lineas, int) or not 1 <= lineas <= TOPE_LINEAS:
        raise ErrorSitio(f"número de líneas no válido (1 a {TOPE_LINEAS})")
    if filtro is not None and (len(filtro) > TOPE_FILTRO or re.search(r"[\x00-\x1f\x7f]", filtro)):
        raise ErrorSitio("filtro no válido")
    meta = leer_meta(dominio)
    clave, nombre = TIPOS[tipo]
    f = _abrir(meta[clave], nombre)
    if f is None:
        return {"dominio": dominio, "tipo": tipo, "existe": False, "lineas": [], "recortado": False}
    with f:
        f.seek(0, os.SEEK_END)
        tamano = f.tell()
        f.seek(max(0, tamano - TOPE_LECTURA))
        texto = f.read(TOPE_LECTURA).decode("utf-8", "replace")
    todas = texto.splitlines()
    if tamano > TOPE_LECTURA and todas:
        todas = todas[1:]  # la primera puede estar cortada
    if filtro:
        buscado = filtro.lower()
        todas = [x for x in todas if buscado in x.lower()]
    elegidas = [x[:TOPE_LINEA] for x in todas[-lineas:]]
    return {"dominio": dominio, "tipo": tipo, "existe": True, "bytes": tamano, "lineas": elegidas,
            "recortado": tamano > TOPE_LECTURA}
