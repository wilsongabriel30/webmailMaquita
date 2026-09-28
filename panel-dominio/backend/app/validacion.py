"""Validaciones de lo que escribe un administrador de dominio. Sin base de datos: se prueban solas."""

import re

from fastapi import HTTPException

_LOCAL = re.compile(r"^[a-z0-9](?:[a-z0-9._-]{0,62}[a-z0-9])?$")
_DOMINIO = re.compile(r"^[a-z0-9](?:[a-z0-9.-]{0,251}[a-z0-9])?$")
_CONTROL = re.compile(r"[\x00-\x1f\x7f]")

GIB = 1024 ** 3
CUOTA_POR_DEFECTO = 5 * GIB
CLAVE_MINIMA = 10


def normalizar_direccion(valor) -> str:
    direccion = str(valor or "").strip().lower()
    if direccion.count("@") != 1:
        raise HTTPException(400, "La dirección debe tener la forma usuario@dominio")
    local, dominio = direccion.split("@")
    if not _LOCAL.match(local) or ".." in local:
        raise HTTPException(400, "El nombre de la cuenta solo admite letras, números, punto, guion y guion bajo")
    if not _DOMINIO.match(dominio) or ".." in dominio:
        raise HTTPException(400, "Dominio inválido")
    return direccion


def texto_limpio(valor, maximo: int = 255) -> str:
    """Sin saltos de línea ni caracteres de control: estos textos acaban en cabeceras y listados."""
    return _CONTROL.sub(" ", str(valor or "")).strip()[:maximo]


def exigir_clave_fuerte(clave, direccion: str = "") -> str:
    clave = str(clave or "")
    if len(clave) < CLAVE_MINIMA:
        raise HTTPException(400, f"La contraseña debe tener al menos {CLAVE_MINIMA} caracteres")
    if len(clave) > 128:
        raise HTTPException(400, "La contraseña es demasiado larga")
    clases = sum(bool(re.search(p, clave)) for p in (r"[a-z]", r"[A-Z]", r"\d", r"[^A-Za-z0-9]"))
    if clases < 3:
        raise HTTPException(400, "La contraseña debe combinar al menos tres de: minúsculas, mayúsculas, números y símbolos")
    local = direccion.split("@")[0]
    if len(local) >= 4 and local in clave.lower():
        raise HTTPException(400, "La contraseña no puede contener el nombre de la cuenta")
    return clave


def cuota_permitida(pedida, maxima_del_dominio: int, actual: int | None = None) -> int:
    """Cuota en bytes. El tope es el del dominio o, si no tiene, la cuota por defecto.

    Una cuenta que ya tenía más que el tope (la dio el administrador general) la conserva
    mientras no se intente subir.
    """
    tope = maxima_del_dominio if maxima_del_dominio and maxima_del_dominio > 0 else CUOTA_POR_DEFECTO
    if pedida is None:
        return actual if actual is not None else min(CUOTA_POR_DEFECTO, tope)
    try:
        pedida = int(pedida)
    except (TypeError, ValueError):
        raise HTTPException(400, "Cuota inválida")
    if pedida <= 0:
        raise HTTPException(400, "La cuota debe ser mayor que cero")
    if actual is not None and pedida <= actual:
        return pedida
    if pedida > tope:
        raise HTTPException(400, f"La cuota máxima para este dominio es {tope / GIB:g} GB")
    return pedida


def destinos_de_alias(valor) -> list[str]:
    if isinstance(valor, str):
        valor = re.split(r"[,;\s]+", valor)
    destinos = []
    for d in valor or []:
        if not str(d).strip():
            continue
        direccion = normalizar_direccion(d)
        if direccion not in destinos:
            destinos.append(direccion)
    if not destinos:
        raise HTTPException(400, "Indica al menos una cuenta de destino")
    if len(destinos) > 100:
        raise HTTPException(400, "Demasiados destinos (máximo 100)")
    return destinos
