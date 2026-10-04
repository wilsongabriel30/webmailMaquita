#!/usr/bin/env python3
"""Candado: ningún texto que ve la gente lleva escrito el nombre de quien desarrolla.

El nombre del producto y el de la organización salen de la marca configurada
(`app_name` / `org_name`, ver frontend/src/lib/marca.ts). Este guion falla si vuelve a
aparecer «Maquita» en el código de los frontends fuera de lo permitido: comentarios,
claves técnicas de almacenamiento, detección de las aplicaciones por User-Agent, el
marcador de reuniones que lee el servidor y mensajes de consola.

Uso: python3 deploy/tools/comprobar-textos-marca.py   (desde la raíz del repositorio)
"""
import os
import re
import sys

RAICES = ["frontend/src", "frontend/index.html", "frontend/public/manifest.json", "frontend/public/sw.js",
          "admin-panel/frontend/src", "admin-panel/frontend/index.html", "panel-dominio/frontend/src"]
EXTENSIONES = (".ts", ".tsx", ".html", ".json", ".js")
NOMBRE = re.compile(r"maquita", re.I)

# Lo que SÍ puede llevar el nombre: no lo ve nadie, o es un contrato con otra pieza.
PERMITIDO = [
    re.compile(r"maquita[_-][a-z0-9_-]*", re.I),          # claves de almacenamiento local y cachés
    re.compile(r"Maquita(Mail|Teams|Almacen)"),           # User-Agent de las aplicaciones y puente nativo
    re.compile(r"X-MAQUITA-[A-Z-]+"),                     # marcador de reuniones en la descripción del evento
    re.compile(r"Meet Maquita: "),                        # idem: el servidor lo lee con una expresión regular
    re.compile(r"(window\.|__)maquita\w*|\bmaquitaApp\b|__maquita\w+"),  # puentes con las aplicaciones nativas
    re.compile(r"maquita:[a-z0-9:-]+"),                    # marcas internas de migración
    re.compile(r"/Maquita/i"),                            # detección de la aplicación en la lista de sesiones
    re.compile(r"console\.(error|warn|log|info|debug)\(.*"),  # registros de consola
    re.compile(r"maquita\.(org|com\.ec)", re.I),          # ejemplos de direcciones en pruebas internas
]


def sin_comentarios(linea: str, en_bloque: bool):
    """Quita comentarios // y /* */ (aproximado, suficiente para este candado)."""
    salida = ""
    i = 0
    while i < len(linea):
        if en_bloque:
            fin = linea.find("*/", i)
            if fin < 0:
                return salida, True
            i, en_bloque = fin + 2, False
            continue
        if linea.startswith("/*", i) or linea.startswith("{/*", i):
            en_bloque = True
            i += 2
            continue
        if linea.startswith("//", i) and (i == 0 or linea[i - 1] != ":"):
            break
        if linea.startswith("<!--", i):
            break
        salida += linea[i]
        i += 1
    return salida, en_bloque


def archivos():
    for raiz in RAICES:
        if os.path.isfile(raiz):
            yield raiz
        for carpeta, _, nombres in os.walk(raiz):
            for n in nombres:
                if n.endswith(EXTENSIONES) and ".test." not in n and ".spec." not in n:
                    yield os.path.join(carpeta, n)


def main() -> int:
    hallazgos = []
    for ruta in archivos():
        en_bloque = False
        with open(ruta, encoding="utf-8", errors="replace") as f:
            for numero, linea in enumerate(f, 1):
                if linea.lstrip().startswith("*"):
                    continue  # cuerpo de un comentario de bloque con asteriscos
                codigo, en_bloque = sin_comentarios(linea, en_bloque)
                for patron in PERMITIDO:
                    codigo = patron.sub("", codigo)
                if NOMBRE.search(codigo):
                    hallazgos.append(f"{ruta}:{numero}: {linea.strip()[:140]}")
    if hallazgos:
        print("Textos con el nombre escrito en el código (deben salir de la marca: lib/marca.ts):")
        print("\n".join("  " + h for h in hallazgos))
        return 1
    print("OK: ningún texto visible lleva el nombre escrito en el código.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
