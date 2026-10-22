"""Forma exacta de las órdenes de autenticación de git (git_credencial.py) para maquita-sudo.

maquita-sudo carga este archivo por su ruta (lo instala deploy/sitios/instalar.sh en /usr/local/lib/maquita-sitios) y
no importa nada más de aquí: solo expresiones regulares. El secreto nunca va en los argumentos: viaja en una subida
.cred de /var/lib/maquita-sitios/subidas, que maquita-sitios lee y borra.
"""

import re

ORDENES = frozenset({"git-credencial", "git-credencial-guardar", "git-credencial-borrar"})
RE_DOMINIO = re.compile(r"^(?=.{4,200}$)([a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}$")
RE_SUBIDA = re.compile(r"^[0-9a-f]{32}\.cred$")


def valida(args):
    """True si `args` tiene la forma exacta de una de las órdenes."""
    if not args or args[0] not in ORDENES or not all(isinstance(a, str) for a in args):
        return False
    if len(args) == 2 and args[0] in ("git-credencial", "git-credencial-borrar"):
        return bool(RE_DOMINIO.fullmatch(args[1]))
    return (len(args) == 3 and args[0] == "git-credencial-guardar" and bool(RE_DOMINIO.fullmatch(args[1]))
            and bool(RE_SUBIDA.fullmatch(args[2])))
