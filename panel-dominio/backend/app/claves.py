"""Contraseñas: las del portal (bcrypt) y las de los buzones (SHA512-CRYPT, como Dovecot).

El portal no tiene sudo ni habla con Dovecot: el hash del buzón se calcula con `openssl`,
que no necesita ningún privilegio. La contraseña viaja por la entrada estándar, nunca como
argumento (los argumentos se ven en la lista de procesos).
"""

import asyncio
import hmac
import re
from asyncio.subprocess import PIPE

import bcrypt

PREFIJO = "{SHA512-CRYPT}"
_HASH = re.compile(r"^\$6\$(?:rounds=\d+\$)?([A-Za-z0-9./]{1,16})\$[A-Za-z0-9./]{86}$")
# Hash de relleno: cuando el usuario no existe se compara igual, para tardar lo mismo.
_RELLENO = bcrypt.hashpw(b"relleno-sin-uso", bcrypt.gensalt())


def hash_portal(clave: str) -> str:
    return bcrypt.hashpw(clave.encode(), bcrypt.gensalt(rounds=12)).decode()


def comprobar_portal(clave: str, guardado: str | None) -> bool:
    try:
        return bcrypt.checkpw(clave.encode(), (guardado.encode() if guardado else _RELLENO)) and bool(guardado)
    except ValueError:
        return False


async def _openssl(clave: str, *extra: str) -> str:
    proc = await asyncio.create_subprocess_exec(
        "openssl", "passwd", "-6", *extra, "-stdin", stdin=PIPE, stdout=PIPE, stderr=PIPE,
    )
    salida, _ = await proc.communicate(clave.encode() + b"\n")
    resultado = salida.decode().strip()
    if proc.returncode != 0 or not _HASH.match(resultado):
        raise RuntimeError("No se pudo calcular el hash de la contraseña")
    return resultado


async def hash_buzon(clave: str) -> str:
    calculado = await _openssl(clave)
    # Garantía contra desincronización: el hash recién hecho debe validar la misma clave.
    if not await comprobar_buzon(clave, PREFIJO + calculado):
        raise RuntimeError("El hash calculado no valida la contraseña")
    return PREFIJO + calculado


async def comprobar_buzon(clave: str, guardado: str) -> bool:
    if not guardado.startswith(PREFIJO):
        return False
    m = _HASH.match(guardado[len(PREFIJO):])
    if not m or "rounds=" in guardado:
        return False
    otra_vez = await _openssl(clave, "-salt", m.group(1))
    return hmac.compare_digest(otra_vez, guardado[len(PREFIJO):])
