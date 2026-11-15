"""Carga firmada de una orden de Flota (contrato T-88, v1) y su caso especial del túnel de soporte (T-120).

El agente lee los campos del túnel PLANOS, en el nivel superior de la carga, junto a `tipo` (probado el
13/11/2026: anidados solo bajo `parametros` responde «orden incompleta»). Se mantienen además duplicados
en `parametros`, sin la clave. La clave privada, si va, solo existe en `clave`.
"""

from __future__ import annotations

import base64
import json

from app.flota import firma
from app.flota.tunel_ajustes import ABRIR

CAMPOS_TUNEL = ("host", "puerto_ssh", "usuario", "puerto_remoto", "minutos")


def construir(
    *,
    orden_id: str,
    equipo_id: str,
    machine_guid: str,
    tipo: str,
    parametros: dict,
    emitida_en: str,
    caduca_en: str,
    emitida_por: str,
    clave: str | None = None,
) -> dict:
    carga = {
        "proposito": firma.PROPOSITO,
        "v": 1,
        "kid": firma.KID,
        "orden_id": orden_id,
        "equipo_id": equipo_id,
        "machine_guid": machine_guid,
        "tipo": tipo,
        "parametros": parametros,
        "emitida_en": emitida_en,
        "caduca_en": caduca_en,
        "emitida_por": emitida_por,
    }
    if tipo == ABRIR:
        planos = {campo: parametros[campo] for campo in CAMPOS_TUNEL}
        carga.update(planos)
        carga["parametros"] = planos
        if clave:
            carga["clave"] = clave
    return carga


def sin_clave(carga_b64: str) -> str | None:
    """La misma carga sin el campo `clave` (base64), o None si no la llevaba o no se puede leer.

    La firma deja de corresponder: solo se aplica a órdenes que el servidor ya no entrega.
    """
    try:
        carga = json.loads(base64.b64decode(carga_b64))
    except ValueError:
        return None
    if not isinstance(carga, dict) or "clave" not in carga:
        return None
    del carga["clave"]
    datos = json.dumps(carga, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    return base64.b64encode(datos.encode("utf-8")).decode()
