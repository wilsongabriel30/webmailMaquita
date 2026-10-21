"""Páginas de error propias (403, 404, 500, 502, 503): un archivo .html de la carpeta pública para cada código.

Son las que muestra nginx cuando el error es suyo: un archivo que no existe, una carpeta prohibida, PHP caído o
sobrecargado. Las páginas que genera la propia aplicación (el 404 de WordPress) siguen siendo las de la aplicación.
Solo en sitios con carpeta pública servida por nginx (no en las aplicaciones propias de Python o Node.js).
"""

import os

import web_comun as w
from comun import ErrorSitio

CODIGOS = ("403", "404", "500", "502", "503")
EXTENSIONES = (".html", ".htm")
MAX_CANDIDATOS = 200


def _raiz(meta):
    import nginx_web

    raiz = nginx_web.raiz_web(meta)
    if not raiz:
        raise ErrorSitio("este sitio no tiene carpeta pública servida por nginx (aplicación propia)")
    return raiz


def validar(meta, datos, existe=True):
    """{código: "/ruta.html"}. Con `existe` se comprueba que el archivo esté dentro de la carpeta pública."""
    if not isinstance(datos, dict):
        raise ErrorSitio("páginas de error no válidas")
    raiz = _raiz(meta) if existe else None
    limpio = {}
    for codigo, archivo in datos.items():
        codigo = str(codigo)
        if codigo not in CODIGOS:
            raise ErrorSitio(f"código no admitido: {codigo[:5]} (solo {', '.join(CODIGOS)})")
        if archivo in (None, ""):
            continue
        archivo = w.ruta(archivo, "página de error")
        if not archivo.lower().endswith(EXTENSIONES):
            raise ErrorSitio("la página de error tiene que ser un archivo .html")
        if existe:
            real = os.path.realpath(os.path.join(raiz, archivo.lstrip("/")))
            if not real.startswith(os.path.realpath(raiz) + "/") or not os.path.isfile(real):
                raise ErrorSitio(f"no existe {archivo} en la carpeta pública")
        limpio[codigo] = archivo
    return limpio


def fragmentos(meta, ajustes):
    if not ajustes:
        return {}
    import nginx_web

    if not nginx_web.raiz_web(meta):
        return {}
    a = validar(meta, ajustes, existe=False)
    return {"servidor": "\n".join(["# Páginas de error propias"] + [f"error_page {c} {a[c]};" for c in CODIGOS if c in a])}


def candidatos(meta):
    """Archivos .html de la carpeta pública (hasta tres niveles) para elegir en el panel."""
    import nginx_web

    raiz = nginx_web.raiz_web(meta)
    if not raiz or not os.path.isdir(raiz):
        return []
    salida = []
    for actual, carpetas, archivos in os.walk(raiz):
        relativa = os.path.relpath(actual, raiz)
        nivel = 0 if relativa == "." else relativa.count("/") + 1
        carpetas[:] = sorted(c for c in carpetas if not c.startswith(".") and nivel < 3
                             and c not in ("wp-admin", "wp-includes", "node_modules", "vendor"))
        for a in sorted(archivos):
            if a.lower().endswith(EXTENSIONES):
                ruta = "/" + (a if relativa == "." else f"{relativa}/{a}")
                try:
                    salida.append(w.ruta(ruta))
                except ErrorSitio:
                    continue
                if len(salida) >= MAX_CANDIDATOS:
                    return salida
    return salida


def estado(meta, ajustes):
    return {"paginas": ajustes or {}, "codigos": list(CODIGOS), "candidatos": candidatos(meta)}
