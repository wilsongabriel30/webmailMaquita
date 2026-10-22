"""Zona horaria de los tableros: la configurada en el panel o, si no hay, la del servidor."""

from __future__ import annotations

import os
import re
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

_RE_ZONA = re.compile(r"[A-Za-z_]{1,20}(?:/[A-Za-z0-9_+-]{1,30}){0,2}")


def valida(nombre: str) -> bool:
    if not nombre or not _RE_ZONA.fullmatch(nombre):
        return False
    try:
        ZoneInfo(nombre)
    except (ZoneInfoNotFoundError, ValueError):
        return False
    return True


def del_servidor() -> str:
    candidatos = [os.environ.get("TZ", "").lstrip(":")]
    try:
        with open("/etc/timezone", encoding="utf-8") as f:
            candidatos.append(f.read().strip())
    except OSError:
        pass
    try:
        destino = os.readlink("/etc/localtime")
        if "zoneinfo/" in destino:
            candidatos.append(destino.split("zoneinfo/", 1)[1])
    except OSError:
        pass
    for c in candidatos:
        if valida(c):
            return c
    return "UTC"


def nombre(configurada: str) -> str:
    return configurada if valida(configurada) else del_servidor()


def zona(configurada: str) -> ZoneInfo:
    return ZoneInfo(nombre(configurada))
