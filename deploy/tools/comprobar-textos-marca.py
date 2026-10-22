#!/usr/bin/env python3
"""Candado: ningún texto que ve la gente lleva escrito el nombre de quien desarrolla.

El nombre del producto y el de la organización salen de la marca configurada
(`app_name` / `org_name`, ver frontend/src/lib/marca.ts). Este guion falla si vuelve a
aparecer «Maquita» en el código de los frontends fuera de lo permitido: comentarios,
claves técnicas de almacenamiento, detección de las aplicaciones por User-Agent, el
marcador de reuniones que lee el servidor y mensajes de consola.

También revisa las Aplicaciones del Drive (Editor de PDF y Tableros, en
`almacen/aplicaciones/`): sus textos salen de la marca del Drive (`drive_name`, ver
`marca_drive.py`). Allí, además de «Maquita», tampoco valen «Raíces» ni «FARO» (los
nombres del sistema central del que vienen), y se miran también las cadenas de Python
(no los comentarios ni los docstrings, que no ve nadie).

Y revisa las cadenas de Python de los backends (`backend/app`, `panel-dominio/backend/app`),
f-strings incluidas: son los mensajes que el servidor manda a la gente (comentarios de
tareas, avisos, páginas, correos automáticos). Ahí se permiten las rutas y nombres técnicos
(`/opt/maquita-webmail`, `maquita-sudo`, `maquita.d`...), los registros (`logger.*`) y los
marcadores que leen otras piezas; el nombre visible sale de `org_name` / `app_name`
(app/branding/service.py).

Uso: python3 deploy/tools/comprobar-textos-marca.py   (desde la raíz del repositorio)
"""
import io
import os
import re
import sys
import tokenize

RAICES = ["frontend/src", "frontend/index.html", "frontend/public/manifest.json", "frontend/public/sw.js",
          "admin-panel/frontend/src", "admin-panel/frontend/index.html", "panel-dominio/frontend/src"]
EXTENSIONES = (".ts", ".tsx", ".html", ".json", ".js")
NOMBRE = re.compile(r"maquita", re.I)

# Aplicaciones del Drive: plantillas, JS y cadenas de Python. `vendor/` es de terceros.
APLICACIONES = ["almacen/aplicaciones/pdf_editor", "almacen/aplicaciones/bi"]
EXTENSIONES_APLICACIONES = (".html", ".js", ".py")
NOMBRE_APLICACIONES = re.compile(r"(?i:maquita)|Ra[íi]ces\b|\bFARO\b")
METADATOS_PY = re.compile(r"\s*__(author|copyright)__\s*=")  # metadatos del paquete: no los ve nadie

# Backends: cadenas de Python que pueden acabar delante de la gente.
BACKENDS = ["backend/app", "panel-dominio/backend/app"]
REGISTRO_PY = re.compile(r"\b(log|logger|logging|_log|registro)\.(debug|info|warning|warn|error|exception|critical)\(")
# Nombres técnicos de los backends: rutas, servicios, claves y marcadores que no ve nadie.
PERMITIDO_BACKEND = [
    re.compile(r"maquita\.(d|webmail)\b"),                 # carpeta de dovecot y nombre del registro
    re.compile(r"\b[a-z]+-maquita\b"),                     # identificadores técnicos (cliente OIDC)
    re.compile(r"^([rbf]*)(['\"])maquita\2$"),             # identificador técnico suelto (reino OIDC)
    re.compile(r"Maquita Compliance"),                      # nombre de la llave GPG de las evidencias
    re.compile(r"Meet Maquita\)"),                          # marcador de reuniones antiguo (expresión regular)
    re.compile(r"\(generado por Maquita; no editar a mano\)"),  # marca del bloque sieve: la buscan los scripts guardados
    re.compile(r"github\.com/\S+"),                         # agente de usuario hacia servicios externos
    re.compile(r"^@maquita$"),                              # UID de los contactos (vCard): cambiarlo los duplica
    re.compile(r"\borg\.maquita\.[a-z.]+"),                 # identificador del perfil de Apple: cambiarlo lo duplica
]

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


def archivos_aplicaciones():
    for raiz in APLICACIONES:
        for carpeta, subcarpetas, nombres in os.walk(raiz):
            subcarpetas[:] = [d for d in subcarpetas if d not in ("vendor", "tests", "__pycache__")]
            for n in nombres:
                if n.endswith(EXTENSIONES_APLICACIONES) and not n.startswith("test_"):
                    yield os.path.join(carpeta, n)


# Python 3.12+ parte las f-strings en trozos: el texto literal llega como FSTRING_MIDDLE.
_FSTRING_MIDDLE = getattr(tokenize, "FSTRING_MIDDLE", None)


def cadenas_python(fuente: str):
    """(línea, texto) de cada cadena de Python que no es un docstring ni un comentario."""
    previo = tokenize.NEWLINE
    try:
        for tok in tokenize.generate_tokens(io.StringIO(fuente).readline):
            if tok.type == tokenize.STRING and previo not in (tokenize.NEWLINE, tokenize.NL, tokenize.INDENT,
                                                             tokenize.DEDENT):
                yield tok.start[0], tok.string
            elif _FSTRING_MIDDLE is not None and tok.type == _FSTRING_MIDDLE:
                yield tok.start[0], tok.string
            if tok.type not in (tokenize.COMMENT, tokenize.NL):
                previo = tok.type
    except (tokenize.TokenError, SyntaxError):
        return


def archivos_backend():
    for raiz in BACKENDS:
        for carpeta, subcarpetas, nombres in os.walk(raiz):
            subcarpetas[:] = [d for d in subcarpetas if d not in ("tests", "__pycache__", "venv", ".venv")]
            for n in nombres:
                if n.endswith(".py") and not n.startswith("test_"):
                    yield os.path.join(carpeta, n)


def revisar_backend(ruta, fuente, hallazgos):
    lineas = fuente.splitlines()
    for numero, cadena in cadenas_python(fuente):
        if REGISTRO_PY.search(lineas[numero - 1]):
            continue  # registro del servidor: lo leen quienes administran, no la gente
        for patron in PERMITIDO + PERMITIDO_BACKEND:
            cadena = patron.sub("", cadena)
        if NOMBRE.search(cadena):
            hallazgos.append(f"{ruta}:{numero}: {cadena.strip()[:140]}")


def revisar_lineas(ruta, lineas, nombre, hallazgos):
    en_bloque = False
    for numero, linea in lineas:
        if linea.lstrip().startswith("*"):
            continue  # cuerpo de un comentario de bloque con asteriscos
        codigo, en_bloque = sin_comentarios(linea, en_bloque)
        for patron in PERMITIDO:
            codigo = patron.sub("", codigo)
        if nombre.search(codigo):
            hallazgos.append(f"{ruta}:{numero}: {linea.strip()[:140]}")


def main() -> int:
    hallazgos = []
    for ruta in archivos():
        with open(ruta, encoding="utf-8", errors="replace") as f:
            revisar_lineas(ruta, enumerate(f, 1), NOMBRE, hallazgos)
    for ruta in archivos_aplicaciones():
        with open(ruta, encoding="utf-8", errors="replace") as f:
            fuente = f.read()
        if ruta.endswith(".py"):
            lineas = fuente.splitlines()
            for numero, cadena in cadenas_python(fuente):
                if METADATOS_PY.match(lineas[numero - 1]):
                    continue
                for patron in PERMITIDO:
                    cadena = patron.sub("", cadena)
                if NOMBRE_APLICACIONES.search(cadena):
                    hallazgos.append(f"{ruta}:{numero}: {cadena.strip()[:140]}")
        else:
            revisar_lineas(ruta, enumerate(fuente.splitlines(), 1), NOMBRE_APLICACIONES, hallazgos)
    for ruta in archivos_backend():
        with open(ruta, encoding="utf-8", errors="replace") as f:
            revisar_backend(ruta, f.read(), hallazgos)
    if hallazgos:
        print("Textos con el nombre escrito en el código (deben salir de la marca: lib/marca.ts;"
              " en los backends, org_name/app_name de app/branding/service.py;"
              " en las Aplicaciones del Drive, drive_name de marca_drive.py):")
        print("\n".join("  " + h for h in hallazgos))
        return 1
    print("OK: ningún texto visible lleva el nombre escrito en el código.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
