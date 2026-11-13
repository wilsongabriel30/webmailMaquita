"""Ajustes del túnel de soporte de Flota (T-120). Todo sale del entorno del panel: en el código no hay
direcciones ni claves de ningún servidor real.

    FLOTA_TUNEL_HOST            dirección del servidor de túneles para equipos FUERA de la red (internet)
    FLOTA_TUNEL_HOST_INTERNO    la misma máquina vista desde la red interna o la VPN
    FLOTA_TUNEL_PUERTO_SSH      puerto SSH del servidor de túneles (por defecto 443)
    FLOTA_TUNEL_USUARIO         usuario solo-túnel del servidor (por defecto «tunel»)
    FLOTA_TUNEL_BROKER          «true» activa el modo automático (Fase B, ver `broker.py`); apagado por defecto

Las órdenes de túnel caducan pronto a propósito: mientras una orden con la clave dentro no se entrega,
esa clave descansa en la base de datos (ver `tunel_purga.py`).
"""

from __future__ import annotations

import os

ABRIR = "abrir_tunel_soporte"
CERRAR = "cerrar_tunel_soporte"
TIPOS = (ABRIR, CERRAR)

PUERTO_MIN, PUERTO_MAX = 22001, 22999
MINUTOS_MIN, MINUTOS_MAX, MINUTOS_DEF = 5, 240, 30
DURACIONES = (15, 30, 60, 120)
HORAS_VALIDEZ_DEF, HORAS_VALIDEZ_MAX = 2, 12


def _texto(nombre: str, defecto: str = "") -> str:
    return (os.getenv(nombre) or defecto).strip()


def host_fuera() -> str:
    return _texto("FLOTA_TUNEL_HOST")


def host_red() -> str:
    return _texto("FLOTA_TUNEL_HOST_INTERNO")


def puerto_ssh() -> int:
    try:
        return int(_texto("FLOTA_TUNEL_PUERTO_SSH", "443"))
    except ValueError:
        return 443


def usuario() -> str:
    return _texto("FLOTA_TUNEL_USUARIO", "tunel")


def automatico() -> bool:
    return _texto("FLOTA_TUNEL_BROKER").lower() == "true"


def para_panel() -> dict:
    """Lo que necesita el formulario del panel (nada de esto es secreto)."""
    return {
        "host_fuera": host_fuera(),
        "host_red": host_red(),
        "puerto_ssh": puerto_ssh(),
        "usuario": usuario(),
        "puerto_min": PUERTO_MIN,
        "puerto_max": PUERTO_MAX,
        "minutos_min": MINUTOS_MIN,
        "minutos_max": MINUTOS_MAX,
        "minutos_def": MINUTOS_DEF,
        "duraciones": list(DURACIONES),
        "horas_validez": HORAS_VALIDEZ_DEF,
        "automatico": automatico(),
    }
