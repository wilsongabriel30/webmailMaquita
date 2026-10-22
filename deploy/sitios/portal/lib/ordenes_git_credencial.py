"""Autenticación de git de un sitio desde el portal: la del despliegue de los sitios PHP y la de las aplicaciones
Node.js, Python y estáticas (deploy/sitios/lib/git_clave.py y git_credencial.py).

  git-credencial          ver: método, si está configurada, huella o final del token, fecha y la clave pública
                          generada. Es de lectura (ORDENES_LECTURA de portal.py y LECTURA de fichas.py).
  git-credencial-guardar  {metodo, repo, clave_privada | token | usuario, contrasena, regenerar}
  git-credencial-borrar   vuelve a «ninguna» (borra la clave o la credencial guardada)

El secreto llega aquí por el socket (nunca por la línea de órdenes) y se pasa a maquita-sitios en un archivo de
root 0600 de subidas/ con un nombre al azar, que maquita-sitios lee y borra: ni el registro de sudo ni el de este
intermediario lo ven (en el registro solo queda el nombre de la orden). Si el repositorio viene, tiene que estar en
Internet (red.py), como el de las aplicaciones propias.
"""

import json
import os
import re
import secrets

import red
import rutas
from errores import ErrorPortal
from ordenes_sitios import sitios

METODOS = ("clave-generada", "clave-propia", "token-https", "usuario-contrasena", "ninguna")
TEXTOS = {"repo": 400, "clave_privada": 16384, "token": 512, "usuario": 100, "contrasena": 512}
_CONTROL = re.compile(r"[\x00-\x08\x0b-\x1f\x7f]")  # la clave privada lleva saltos de línea


def estado(ctx):
    return sitios("git-credencial", ctx.sitio, tiempo=60)


def _datos(args):
    datos = args.get("credencial")
    if not isinstance(datos, dict) or set(datos) - set(TEXTOS) - {"metodo", "regenerar"}:
        raise ErrorPortal(400, "Datos de autenticación no válidos")
    if datos.get("metodo") not in METODOS:
        raise ErrorPortal(400, "Método de autenticación no válido")
    limpio = {"metodo": datos["metodo"], "regenerar": datos.get("regenerar") is True}
    for campo, maximo in TEXTOS.items():
        valor = datos.get(campo)
        if valor in (None, ""):
            continue
        if not isinstance(valor, str) or len(valor) > maximo or _CONTROL.search(valor) \
                or (campo != "clave_privada" and "\n" in valor):
            raise ErrorPortal(400, f"Dato no válido: {campo}")
        limpio[campo] = valor
    if limpio.get("repo"):
        limpio["repo"] = red.repositorio(limpio["repo"].strip())
    return limpio


def guardar(ctx):
    datos = _datos(ctx.args)
    nombre = f"{secrets.token_hex(16)}.cred"
    ruta = os.path.join(rutas.SUBIDAS, nombre)
    with open(os.open(ruta, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600), "w") as f:
        json.dump(datos, f, ensure_ascii=False)
    try:
        return sitios("git-credencial-guardar", ctx.sitio, nombre, tiempo=120)
    finally:
        if os.path.lexists(ruta):  # maquita-sitios la borra al leerla; si no llegó a leerla, aquí
            os.remove(ruta)


def borrar(ctx):
    return sitios("git-credencial-borrar", ctx.sitio, tiempo=60)


ORDENES = {
    "git-credencial": ("sitio", estado),
    "git-credencial-guardar": ("sitio", guardar),
    "git-credencial-borrar": ("sitio", borrar),
}
