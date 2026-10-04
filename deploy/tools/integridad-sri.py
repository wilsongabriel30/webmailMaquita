#!/usr/bin/env python3
"""Comprueba (o corrige) las firmas de integridad (SRI) de un index.html publicado.

El despliegue retoca archivos después de construir (el nombre de la aplicación en
manifest.json, los iconos de la marca local). Si el archivo cambia y la firma de index.html
no, el navegador lo bloquea; cuando el bloqueado es el script principal, la página queda en
blanco aunque el servidor responda 200.

Uso:
  integridad-sri.py <directorio>              comprueba; sale con 1 si alguna firma no coincide
  integridad-sri.py <directorio> --corregir   reescribe en index.html las que no coinciden
  --base /webmail/                            prefijo público con que se sirve el directorio
"""
import base64
import hashlib
import os
import re
import sys

ETIQUETA = re.compile(r"<(?:script|link)\b[^>]*\bintegrity=[^>]*>", re.I)
FIRMA = re.compile(r"""\bintegrity=(["'])(sha(?:256|384|512))-([A-Za-z0-9+/=]+)\1""", re.I)
ORIGEN = re.compile(r"""\b(?:src|href)=(["'])([^"']+)\1""", re.I)


def ruta_local(directorio, url, base):
    url = url.split("?", 1)[0].split("#", 1)[0]
    if re.match(r"^(?:[a-z]+:)?//", url, re.I):
        return None  # recurso de otro origen: no se puede comprobar aquí
    if url.startswith(base):
        url = url[len(base):]
    return os.path.join(directorio, url.lstrip("/"))


def main(argv):
    args = [a for a in argv if not a.startswith("--")]
    corregir = "--corregir" in argv
    base = "/webmail/"
    if "--base" in argv:
        base = argv[argv.index("--base") + 1]
        args = [a for a in args if a != base]
    if len(args) != 1:
        print(__doc__)
        return 2
    directorio = args[0]
    indice = os.path.join(directorio, "index.html")
    try:
        html = open(indice, encoding="utf-8").read()
    except OSError as e:
        print(f"ERROR: no se puede leer {indice}: {e}")
        return 2

    total = malas = corregidas = 0

    def revisar(m):
        nonlocal total, malas, corregidas
        etiqueta = m.group(0)
        firma, origen = FIRMA.search(etiqueta), ORIGEN.search(etiqueta)
        if not firma or not origen:
            return etiqueta
        archivo = ruta_local(directorio, origen.group(2), base)
        if archivo is None:
            return etiqueta
        total += 1
        if not os.path.isfile(archivo):
            malas += 1
            print(f"  FALTA el archivo firmado: {origen.group(2)}")
            return etiqueta
        algoritmo = firma.group(2).lower()
        real = base64.b64encode(hashlib.new(algoritmo, open(archivo, "rb").read()).digest()).decode()
        if real == firma.group(3):
            return etiqueta
        if corregir:
            corregidas += 1
            print(f"  firma recalculada: {origen.group(2)}")
            return etiqueta.replace(firma.group(3), real)
        malas += 1
        print(f"  firma DESCUADRADA: {origen.group(2)}")
        return etiqueta

    nuevo = ETIQUETA.sub(revisar, html)
    if corregir and nuevo != html:
        tmp = indice + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            f.write(nuevo)
        os.replace(tmp, indice)
    print(f"  {total} firmas revisadas · {corregidas} recalculadas · {malas} con problema")
    return 1 if malas else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
