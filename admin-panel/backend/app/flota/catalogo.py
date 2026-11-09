"""Tipos de orden de Flota Maquita (T-88) y su fase.

Fase 1 (activa): sin riesgo, sin tocar hardware. Fase 3 (hardware): definida pero BLOQUEADA hasta que
haya OK de protección de datos (LOPDP) y aviso al personal; se habilita con FLOTA_HARDWARE=true y,
aun así, exige doble confirmación (texto «CONFIRMO») en cada emisión.
"""

from __future__ import annotations

import os

from fastapi import HTTPException

TIPOS: dict[str, dict] = {
    "ping": {"fase": 1, "nombre": "Comprobar conexión", "desc": "El agente responde «ok» con su versión y hora local."},
    "inventario": {"fase": 1, "nombre": "Inventario", "desc": "El agente devuelve en «datos» el inventario del equipo (hardware, Windows, software, Kaspersky, SSH)."},
    "forzar_actualizacion": {"fase": 1, "nombre": "Forzar actualización de Teams Maquita", "desc": "Ejecuta ya la tarea de actualización en vez de esperar al ciclo de 3 h."},
    "usb_almacenamiento": {"fase": 3, "nombre": "Candado de USB (almacenamiento)", "desc": "parametros.accion = bloquear | permitir. No afecta teclado ni ratón.", "acciones": ("bloquear", "permitir")},
    "camara": {"fase": 3, "nombre": "Cámara", "desc": "parametros.accion = desactivar | activar (permiso del sistema, nunca captura).", "acciones": ("desactivar", "activar")},
    "microfono": {"fase": 3, "nombre": "Micrófono", "desc": "parametros.accion = desactivar | activar (permiso del sistema, nunca captura).", "acciones": ("desactivar", "activar")},
}


def hardware_habilitado() -> bool:
    return os.getenv("FLOTA_HARDWARE", "").lower() == "true"


def validar(tipo: str, parametros: dict, confirmacion: str) -> dict:
    """Devuelve los parámetros limpios o lanza HTTPException."""
    t = TIPOS.get(tipo)
    if not t:
        raise HTTPException(400, f"Tipo de orden desconocido: {tipo}")
    if t["fase"] >= 3:
        if not hardware_habilitado():
            raise HTTPException(403, "Las órdenes de hardware (fase 3) siguen bloqueadas hasta el OK de protección de datos y el aviso al personal.")
        if confirmacion != "CONFIRMO":
            raise HTTPException(400, "Orden de hardware: escriba CONFIRMO para emitirla.")
        accion = str((parametros or {}).get("accion") or "")
        if accion not in t["acciones"]:
            raise HTTPException(400, f"parametros.accion debe ser uno de {list(t['acciones'])}")
        return {"accion": accion}
    return {}


def para_panel() -> list[dict]:
    hw = hardware_habilitado()
    return [{"tipo": k, **{c: v for c, v in t.items() if c != "acciones"}, "acciones": list(t.get("acciones", ())),
             "habilitado": t["fase"] < 3 or hw} for k, t in TIPOS.items()]
