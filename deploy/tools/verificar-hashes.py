#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Comprobar que el prefijo de cada contraseña dice la verdad sobre su contenido.

Por qué existe
--------------
El equipo de Andes reportó (09/09/2026) que una cuenta suya tenía guardado un hash con el prefijo
`{SHA512-CRYPT}` cuyo contenido NO era formato crypt. Dovecot no puede verificar eso jamás: la
persona escribe bien su contraseña, el servidor dice que no, y no hay ningún mensaje que explique
por qué. Estuvo un mes sin poder entrar.

No es un fallo raro: es lo que pasa al migrar. Zimbra guarda `{SSHA512}`, Dovecot por omisión
espera `SHA512-CRYPT`, y basta con etiquetar mal una fila —o quitarle el prefijo, que es peor,
porque entonces se interpreta con `default_password_scheme`— para dejar a alguien fuera. El fallo
no da la cara al importar: aparece la próxima vez que esa persona intente entrar.

Qué hace
--------
Lee la tabla de buzones y comprueba, para cada contraseña, que la forma del valor case con lo que
su prefijo promete. No descifra nada, no imprime hashes y no toca la base: solo mira y avisa.

Uso
---
    python3 verificar-hashes.py                 # informe
    python3 verificar-hashes.py --solo-activas  # solo cuentas que pueden entrar hoy

Sale con código 1 si encuentra algo incoherente, para poder colgarlo de una revisión periódica.
"""

import argparse
import base64
import binascii
import os
import re
import subprocess
import sys

CONSULTA = "SELECT username, password, active FROM mailbox ORDER BY username;"

# Lo que cada prefijo promete. La clave es el esquema; el valor, cómo se reconoce su contenido.
ESQUEMAS = {
    "SHA512-CRYPT": (
        "empieza por $6$",
        lambda v: v.startswith("$6$") and v.count("$") >= 3,
    ),
    "SHA256-CRYPT": (
        "empieza por $5$",
        lambda v: v.startswith("$5$") and v.count("$") >= 3,
    ),
    "MD5-CRYPT": (
        "empieza por $1$",
        lambda v: v.startswith("$1$") and v.count("$") >= 3,
    ),
    "BLF-CRYPT": ("empieza por $2", lambda v: v.startswith("$2")),
    "ARGON2ID": ("empieza por $argon2", lambda v: v.startswith("$argon2")),
    "CRYPT": ("empieza por $", lambda v: v.startswith("$")),
}

# Los que guardan base64: se comprueba que lo sea y que tenga el largo que corresponde.
BASE64 = {
    "SSHA512": 64,  # 64 bytes de resumen + sal
    "SSHA256": 32,
    "SSHA": 20,
    "SHA512": 64,
    "SHA256": 32,
    "SHA": 20,
}

# Estos guardan la contraseña legible. No es un fallo de formato, pero hay que decirlo.
EN_CLARO = {"PLAIN", "CLEARTEXT", "PLAIN-TRUNC"}


def leer_default_scheme() -> str:
    """El esquema que Dovecot supone cuando el valor NO trae prefijo."""
    try:
        salida = subprocess.run(
            ["doveconf", "-n"], capture_output=True, text=True, timeout=15
        ).stdout
        m = re.search(r"default_password_scheme\s*=\s*(\S+)", salida)
        if m:
            return m.group(1).upper()
    except Exception:
        pass
    return "SHA512-CRYPT"  # el de Dovecot por omisión


def revisar(valor: str, por_omision: str):
    """Devuelve (esquema, problema o None). No imprime ni devuelve el hash."""
    if valor is None or valor == "":
        return ("(vacío)", "no tiene contraseña guardada: esa cuenta no puede entrar")

    if valor.startswith("{"):
        cierre = valor.find("}")
        if cierre == -1:
            return ("(ilegible)", "empieza por { y nunca cierra la llave")
        esquema = valor[1:cierre].upper()
        contenido = valor[cierre + 1 :]
        explicito = True
    else:
        esquema = por_omision
        contenido = valor
        explicito = False

    if not contenido:
        return (esquema, "tiene el prefijo pero no hay hash detrás")

    if esquema in EN_CLARO:
        return (esquema, "la contraseña está guardada legible, sin cifrar")

    if esquema in ESQUEMAS:
        pinta, comprueba = ESQUEMAS[esquema]
        if not comprueba(contenido):
            aviso = "dice ser %s pero no %s" % (esquema, pinta)
            if not explicito:
                aviso += (
                    " (y no trae prefijo, asi que se interpreta como %s)" % por_omision
                )
            return (esquema, aviso)
        return (esquema, None)

    if esquema in BASE64:
        try:
            crudo = base64.b64decode(contenido, validate=True)
        except (binascii.Error, ValueError):
            return (esquema, "dice ser %s pero no es base64 valido" % esquema)
        minimo = BASE64[esquema]
        if len(crudo) < minimo:
            return (
                esquema,
                "dice ser %s pero solo trae %d bytes (hacen falta al menos %d)"
                % (esquema, len(crudo), minimo),
            )
        return (esquema, None)

    return (esquema, "esquema desconocido: comprobar que Dovecot lo admite")


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--solo-activas",
        action="store_true",
        help="mirar solo las cuentas que pueden entrar hoy",
    )
    p.add_argument("--bd", default=os.environ.get("MAILDB", "maildb"))
    args = p.parse_args()

    salida = subprocess.run(
        [
            "sudo",
            "-u",
            "postgres",
            "psql",
            "-d",
            args.bd,
            "-t",
            "-A",
            "-F",
            "\t",
            "-c",
            CONSULTA,
        ],
        capture_output=True,
        text=True,
        timeout=60,
    )
    if salida.returncode != 0:
        sys.exit("no se pudo leer la base: %s" % salida.stderr.strip()[:200])

    por_omision = leer_default_scheme()
    print("Esquema supuesto cuando no hay prefijo: %s\n" % por_omision)

    formas, problemas, total = {}, [], 0
    for linea in salida.stdout.splitlines():
        if not linea.strip():
            continue
        partes = linea.split("\t")
        if len(partes) < 3:
            continue
        usuario, valor, activa = partes[0], partes[1], partes[2] == "t"
        if args.solo_activas and not activa:
            continue
        total += 1
        esquema, problema = revisar(valor, por_omision)
        formas[esquema] = formas.get(esquema, 0) + 1
        if problema:
            problemas.append((usuario, activa, problema))

    print("Revisadas %d cuentas:" % total)
    for esquema, cuantas in sorted(formas.items(), key=lambda x: -x[1]):
        print("   %-16s %4d" % (esquema, cuantas))

    if not problemas:
        print(
            "\nTodas coherentes: el prefijo de cada una dice la verdad sobre su contenido."
        )
        return 0

    print("\n%d con problemas:\n" % len(problemas))
    for usuario, activa, problema in problemas:
        marca = "ACTIVA " if activa else "inactiva"
        print("   [%s] %-40s %s" % (marca, usuario, problema))
    print(
        "\nUna cuenta activa con el prefijo equivocado NO PUEDE ENTRAR, por bien que escriba su"
    )
    print(
        "contrasena, y el servidor no da ninguna pista de por que. Se arregla asignandole una"
    )
    print("contrasena nueva por el camino normal, que vuelve a escribir el hash bien.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
