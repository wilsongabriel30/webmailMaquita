"""Validación de las órdenes del túnel de soporte (T-120): `abrir_tunel_soporte` y `cerrar_tunel_soporte`.

Son de fase 1 (no tocan hardware) pero sensibles: abrir exige escribir «CONFIRMO», como la fase 3.
La clave privada NO forma parte de los parámetros: se trata aparte (`tunel_claves.comprobar`) y solo va
dentro de la carga firmada.
"""

from __future__ import annotations

import re

from fastapi import HTTPException

from app.flota import tunel_ajustes as aj

_HOST = re.compile(r"^[A-Za-z0-9]([A-Za-z0-9.-]{0,251}[A-Za-z0-9])?$")
_USUARIO = re.compile(r"^[a-z_][a-z0-9_-]{0,31}$")
UBICACIONES = ("fuera", "red")


def _entero(
    valor, campo: str, minimo: int, maximo: int, defecto: int | None
) -> int | None:
    if valor is None or valor == "":
        return defecto
    if isinstance(valor, bool):
        raise HTTPException(400, f"{campo} debe ser un número entero")
    try:
        n = int(str(valor).strip())
    except (TypeError, ValueError):
        raise HTTPException(400, f"{campo} debe ser un número entero") from None
    if not minimo <= n <= maximo:
        raise HTTPException(400, f"{campo} debe estar entre {minimo} y {maximo}")
    return n


def _host(p: dict) -> str:
    host = str(p.get("host") or "").strip()
    if not host:
        ubicacion = str(p.get("ubicacion") or "fuera")
        if ubicacion not in UBICACIONES:
            raise HTTPException(400, f"ubicacion debe ser una de {list(UBICACIONES)}")
        host = aj.host_red() if ubicacion == "red" else aj.host_fuera()
    if not host:
        raise HTTPException(
            400,
            "Indique la dirección del servidor de túneles: no hay ninguna configurada para esa ubicación del equipo.",
        )
    if not _HOST.match(host):
        raise HTTPException(400, "host debe ser una dirección IP o un nombre DNS")
    return host


def validar(tipo: str, parametros: dict, confirmacion: str) -> dict:
    """Parámetros limpios. En `abrir`, `puerto_remoto` queda en None si no viene: lo asigna el servidor."""
    if tipo == aj.CERRAR:
        return {}
    if confirmacion != "CONFIRMO":
        raise HTTPException(
            400,
            "Abrir un túnel de soporte da acceso remoto al equipo: escriba CONFIRMO para emitir la orden.",
        )
    p = parametros if isinstance(parametros, dict) else {}
    usuario = str(p.get("usuario") or aj.usuario()).strip()
    if not _USUARIO.match(usuario):
        raise HTTPException(400, "usuario no es un nombre de usuario válido")
    return {
        "host": _host(p),
        "puerto_ssh": _entero(
            p.get("puerto_ssh"), "puerto_ssh", 1, 65535, aj.puerto_ssh()
        ),
        "usuario": usuario,
        "puerto_remoto": _entero(
            p.get("puerto_remoto"), "puerto_remoto", aj.PUERTO_MIN, aj.PUERTO_MAX, None
        ),
        "minutos": _entero(
            p.get("minutos"), "minutos", aj.MINUTOS_MIN, aj.MINUTOS_MAX, aj.MINUTOS_DEF
        ),
    }


def validez(cuerpo: dict) -> int:
    """Horas de validez de una orden de túnel: corta, porque la orden puede llevar la clave dentro."""
    return _entero(
        cuerpo.get("horas_validez"),
        "horas_validez",
        1,
        aj.HORAS_VALIDEZ_MAX,
        aj.HORAS_VALIDEZ_DEF,
    )
