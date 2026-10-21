"""Rutas del administrador de archivos: siempre dentro de la carpeta del sitio.

El panel manda rutas relativas a la carpeta pública («.» es la raíz). Se rechazan las absolutas, «..», los
caracteres de control y los nombres demasiado largos; la carpeta que contiene el destino se resuelve con
realpath y tiene que seguir dentro. El último elemento no se resuelve: borrar o renombrar un enlace simbólico
actúa sobre el enlace; leer o listar a través de él solo se admite si apunta dentro de la carpeta.
"""

import os
import re

from comun import ErrorSitio

TOPE_RUTA = 1000
RE_CONTROL = re.compile(r"[\x00-\x1f\x7f]")


def dentro(raiz, ruta):
    return ruta == raiz or ruta.startswith(raiz.rstrip("/") + "/")


def partes(relativa):
    """«css/estilo.css» → ["css", "estilo.css"]; «.» → []."""
    if not isinstance(relativa, str) or not relativa or len(relativa) > TOPE_RUTA or RE_CONTROL.search(relativa):
        raise ErrorSitio("ruta no válida")
    if relativa.startswith("/") or "\\" in relativa:
        raise ErrorSitio("ruta no válida: debe ser relativa a la carpeta del sitio")
    trozos = [p for p in relativa.split("/") if p not in ("", ".")]
    if any(p == ".." or len(p.encode()) > 255 for p in trozos):
        raise ErrorSitio("ruta no válida: no puede salir de la carpeta del sitio")
    return trozos


def resolver(raiz, relativa, raiz_admitida=True):
    """Ruta absoluta del elemento, sin resolver el último componente."""
    raiz = os.path.realpath(raiz)
    trozos = partes(relativa)
    if not trozos:
        if not raiz_admitida:
            raise ErrorSitio("no se puede hacer eso con la carpeta principal del sitio")
        return raiz
    padre = os.path.realpath(os.path.join(raiz, *trozos[:-1]))
    if not dentro(raiz, padre):
        raise ErrorSitio("ruta no válida: un enlace simbólico sale de la carpeta del sitio")
    return os.path.join(padre, trozos[-1])


def seguir(raiz, ruta):
    """Para leer o listar: si es un enlace, tiene que apuntar dentro de la carpeta."""
    real = os.path.realpath(ruta)
    if not dentro(os.path.realpath(raiz), real):
        raise ErrorSitio("ese enlace simbólico apunta fuera de la carpeta del sitio")
    return real


def relativa(raiz, ruta):
    rel = os.path.relpath(ruta, os.path.realpath(raiz))
    return "." if rel == "." else rel


def nombre_valido(nombre):
    if not nombre or "/" in nombre or nombre in (".", "..") or RE_CONTROL.search(nombre) or len(nombre.encode()) > 255:
        raise ErrorSitio("nombre no válido")
    return nombre
