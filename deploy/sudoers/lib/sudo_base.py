# -*- coding: utf-8 -*-
"""Lo común de los validadores de maquita-sudo: el rechazo, las formas de buzón, dominio y base64url, y la
limpieza de argumentos. Lo cargan maquita-sudo y los demás módulos de esta carpeta (/usr/local/lib/maquita-sudo/).
"""
import re
import subprocess

DOVEADM = "/usr/bin/doveadm"

_RE_BUZON = re.compile(r"^[a-z0-9][a-z0-9._+-]{0,63}@[a-z0-9]([a-z0-9-]*[a-z0-9])?(\.[a-z0-9]([a-z0-9-]*[a-z0-9])?)+$")
_RE_TOKEN = re.compile(r"^[^\x00-\x1f\x7f]{1,300}$")
_RE_QID = re.compile(r"^[A-Za-z0-9]{6,20}$")
_RE_JAIL = re.compile(r"^[a-z0-9_-]{1,40}$")
_RE_PROP = re.compile(r"^[a-zA-Z]{1,30}$")
_RE_VALOR = re.compile(r"^[A-Za-z0-9 .:/,_@$=-]{0,500}$")
_RE_SIEVE = re.compile(r"^/var/vmail/[a-z0-9.-]+/[a-z0-9._+-]+/[A-Za-z0-9._-]+\.sieve$")
_RE_SINCE = re.compile(r"^(-[0-9]{1,5}[smhd]|[0-9]{4}-[0-9]{2}-[0-9]{2}( [0-9]{2}:[0-9]{2}(:[0-9]{2})?)?)$")
_RE_DOMINIO_SITIO = re.compile(r"^(?=.{4,200}$)([a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}$")
_RE_B64URL = re.compile(r"^[A-Za-z0-9_-]{1,200}$")
_RE_B64URL_LARGO = re.compile(r"^[A-Za-z0-9_-]{1,8000}$")
_RE_B64URL_MUY_LARGO = re.compile(r"^[A-Za-z0-9_-]{1,40000}$")
_RE_ID_REGISTRO = re.compile(r"^[0-9a-f]{8}$")


class Rechazo(Exception):
    pass


def es_buzon(v: str) -> bool:
    return isinstance(v, str) and len(v) <= 254 and bool(_RE_BUZON.fullmatch(v.lower()))



def _buzon_existe(buzon: str) -> bool:
    """El dominio propio se comprueba contra Dovecot: si el buzón no existe, no hay orden."""
    try:
        r = subprocess.run([DOVEADM, "user", "-u", buzon], capture_output=True, timeout=10)
        return r.returncode == 0
    except Exception:
        return False


def _tokens_limpios(args):
    for a in args:
        if not isinstance(a, str) or not _RE_TOKEN.fullmatch(a):  # fullmatch: «$» admite un salto final
            raise Rechazo("argumento con caracteres de control o vacío")
