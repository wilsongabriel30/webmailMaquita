#!/usr/bin/env python3
"""Barrido de DATOS PERSONALES en ficheros que van al repositorio.

Uso:
  barrido-datos-personales.py --staged            (hook pre-commit: lo que se va a commitear)
  barrido-datos-personales.py --arbol [RAIZ]      (CI: todo el arbol de trabajo)
  barrido-datos-personales.py FICHERO...          (ficheros sueltos)

Sale con 1 si detecta algo, 0 si no. Imprime fichero y motivo.

POR QUE EXISTE
El 1 de septiembre de 2026 entro en el repositorio publico un fichero con 193
pares de correo y nombre completo de personas reales. Paso el barrido de
secretos porque gitleaks busca claves y tokens, no personas. Este barrido busca
lo que gitleaks no busca.

QUE BUSCA, y por que con UMBRALES
Un correo o un telefono sueltos en una documentacion son normales; lo que no
debe pasar es el VOLUMEN: un directorio de personas. Por eso se cuenta por
fichero y solo se avisa a partir de un numero. Las cedulas son la excepcion:
una sola cedula real ya es dato personal, asi que se validan con su digito
verificador para no confundirlas con cualquier numero de diez cifras.

  - Correos:   >= UMBRAL_CORREOS direcciones DISTINTAS en un fichero.
  - Telefonos: >= UMBRAL_TELEFONOS numeros ecuatorianos distintos (movil 09…,
               fijo 0[2-7]…, o +593…).
  - Cedulas:   >= 1 cedula ecuatoriana con verificador VALIDO (modulo 10).
  - Directorio: >= UMBRAL_PARES pares correo -> nombre de persona en JSON/CSV.

QUE NO MIRA
Directorios de pruebas y documentacion de ejemplo (ver EXCLUIR), dominios de
ejemplo (example.com, etc.) y ficheros binarios. Si un caso legitimo salta,
se anade aqui la excepcion CON el motivo, no se baja el umbral.
"""
import json
import os
import re
import subprocess
import sys

UMBRAL_CORREOS = 15
UMBRAL_TELEFONOS = 10
UMBRAL_PARES = 10

EXCLUIR_DIRS = ("node_modules", "venv", ".git", "dist", "__pycache__", "tests", "test")
EXCLUIR_SUFIJOS = (".png", ".jpg", ".jpeg", ".gif", ".ico", ".woff", ".woff2", ".ttf",
                   ".pdf", ".zip", ".gz", ".tar", ".pyc", ".lock", ".svg", ".min.js")
DOMINIOS_EJEMPLO = ("example.com", "example.org", "example.net", "test.com", "localhost",
                    "maquita.test", "dominio.com", "empresa.com", "correo.com")
# Cuentas de sistema o de ejemplo que aparecen legitimamente en configuracion
CUENTAS_SISTEMA = ("postmaster", "abuse", "noreply", "no-reply", "root", "admin",
                   "webmaster", "hostmaster", "dmarc", "sistemas", "soporte", "info",
                   "usuario", "user", "prueba", "test", "ejemplo")

RE_CORREO = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
RE_TELEFONO = re.compile(r"(?<!\d)(?:\+593\s?9\d{8}|09\d{8}|0[2-7]\d{7})(?!\d)")
RE_CEDULA = re.compile(r"(?<!\d)(\d{10})(?!\d)")
# "correo@dominio": "Nombre Apellido"  o  correo,Nombre Apellido
RE_PAR_JSON = re.compile(r'"([A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,})"\s*:\s*"([^"]{5,80})"')
RE_PAR_CSV = re.compile(r'^([A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,})\s*[,;]\s*([^,;\n]{5,80})', re.M)


def cedula_valida(c):
    """Cedula ecuatoriana: provincia 01-24 o 30, tercer digito < 6, verificador modulo 10."""
    if len(c) != 10 or not c.isdigit():
        return False
    prov = int(c[:2])
    if not (1 <= prov <= 24 or prov == 30):
        return False
    if int(c[2]) >= 6:
        return False
    suma = 0
    for i, d in enumerate(c[:9]):
        n = int(d) * (2 if i % 2 == 0 else 1)
        suma += n - 9 if n > 9 else n
    verificador = (10 - suma % 10) % 10
    return verificador == int(c[9])


def correo_relevante(correo):
    usuario, _, dominio = correo.lower().partition("@")
    if any(dominio.endswith(d) for d in DOMINIOS_EJEMPLO):
        return False
    if usuario in CUENTAS_SISTEMA:
        return False
    return True


def parece_nombre(texto):
    """Dos o mas palabras con mayuscula inicial: Nombre Apellido."""
    palabras = [p for p in texto.strip().split() if p]
    return len(palabras) >= 2 and sum(1 for p in palabras if p[:1].isupper()) >= 2


def analizar(ruta, contenido):
    motivos = []
    correos = {c for c in RE_CORREO.findall(contenido) if correo_relevante(c)}
    if len(correos) >= UMBRAL_CORREOS:
        motivos.append(f"{len(correos)} direcciones de correo distintas")
    telefonos = set(RE_TELEFONO.findall(contenido))
    if len(telefonos) >= UMBRAL_TELEFONOS:
        motivos.append(f"{len(telefonos)} telefonos distintos")
    cedulas = {c for c in RE_CEDULA.findall(contenido) if cedula_valida(c)}
    if cedulas:
        motivos.append(f"{len(cedulas)} cedula(s) con verificador valido")
    pares = [(c, n) for c, n in RE_PAR_JSON.findall(contenido) + RE_PAR_CSV.findall(contenido)
             if correo_relevante(c) and parece_nombre(n)]
    if len(pares) >= UMBRAL_PARES:
        motivos.append(f"{len(pares)} pares correo -> nombre de persona (directorio)")
    return motivos


def excluido(ruta):
    partes = ruta.replace("\\", "/").split("/")
    if any(p in EXCLUIR_DIRS for p in partes):
        return True
    return ruta.lower().endswith(EXCLUIR_SUFIJOS)


def leer(ruta):
    try:
        with open(ruta, "rb") as fh:
            datos = fh.read(2_000_000)
        if b"\x00" in datos[:4096]:
            return None
        return datos.decode("utf-8", errors="replace")
    except OSError:
        return None


def ficheros_staged():
    salida = subprocess.run(["git", "diff", "--cached", "--name-only", "--diff-filter=ACMR"],
                            capture_output=True, text=True).stdout
    for ruta in salida.split("\n"):
        ruta = ruta.strip()
        if not ruta or excluido(ruta):
            continue
        contenido = subprocess.run(["git", "show", f":{ruta}"], capture_output=True).stdout
        if b"\x00" in contenido[:4096]:
            continue
        yield ruta, contenido.decode("utf-8", errors="replace")


def ficheros_arbol(raiz):
    for carpeta, dirs, nombres in os.walk(raiz):
        dirs[:] = [d for d in dirs if d not in EXCLUIR_DIRS]
        for n in nombres:
            ruta = os.path.join(carpeta, n)
            rel = os.path.relpath(ruta, raiz)
            if excluido(rel):
                continue
            contenido = leer(ruta)
            if contenido is not None:
                yield rel, contenido


def main():
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        return 2
    if args[0] == "--staged":
        fuente = ficheros_staged()
    elif args[0] == "--arbol":
        fuente = ficheros_arbol(args[1] if len(args) > 1 else ".")
    else:
        fuente = ((r, leer(r) or "") for r in args)

    hallazgos = []
    for ruta, contenido in fuente:
        for motivo in analizar(ruta, contenido):
            hallazgos.append((ruta, motivo))

    if hallazgos:
        print("✗ DATOS PERSONALES detectados:")
        for ruta, motivo in hallazgos:
            print(f"   {ruta}: {motivo}")
        print("   Un directorio de personas no va al repositorio. Si es un falso positivo,")
        print("   anade la excepcion en barrido-datos-personales.py CON el motivo.")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
