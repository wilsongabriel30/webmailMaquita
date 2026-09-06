# -*- coding: utf-8 -*-
"""Capacidades de OnlyOffice nacidas de un ENLACE PÚBLICO (F-07, tercera revisión).

Antes: el config público emitía tokens de descarga y callback de 7 días ligados solo al
propietario y la ruta; borrar el enlace o quitarle la edición no invalidaba nada ya emitido.
Ahora cada capacidad lleva el id y la versión del share (`s`, `sv`) y se revalida en cada
descarga/callback: el share debe existir, no haber vencido, conservar su versión y, para
guardar, seguir permitiendo editar. La capacidad de descarga pública dura minutos, no días.

Módulo sin Flask ni base de datos: quien llama trae la fila del share.
"""
from datetime import datetime, timezone

MINUTOS_DESCARGA_PUBLICA = 30


def ligadura(comp: dict) -> dict:
    """Reclamos que atan una capacidad al share del que nace."""
    return {"s": int(comp["id"]), "sv": int(comp.get("version") or 1)}


def nace_de_enlace(datos: dict) -> bool:
    return "s" in datos


def vigente(comp: dict | None, datos: dict, uso: str, ahora: datetime | None = None) -> bool:
    """True si el share `comp` (fila actual, o None si ya no existe) sigue respaldando la
    capacidad `datos` para el `uso` pedido ('descarga' o 'callback')."""
    if not comp:
        return False
    ahora = ahora or datetime.now(timezone.utc)
    if comp.get("expira_en") is not None and comp["expira_en"] < ahora:
        return False
    if int(comp.get("version") or 1) != int(datos.get("sv") or 0):
        return False
    if uso == "callback" and not comp.get("puede_editar"):
        return False
    return True
