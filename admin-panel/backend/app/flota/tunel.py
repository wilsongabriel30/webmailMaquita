"""Túnel de soporte (T-120): lo que la emisión de órdenes necesita además de firmar.

- Fase A (manual, por defecto): el puerto y la clave privada del equipo se dan en el formulario. Si no
  viene puerto, se usa el que ya tenía el equipo o el menor libre.
- Fase B (automática, `FLOTA_TUNEL_BROKER=true`): se genera un par ed25519 nuevo en cada apertura, se
  revoca el anterior y se instala la clave pública en el servidor de túneles (`broker.py`); la privada
  viaja solo dentro de la orden firmada. Al cerrar o retirar el equipo se revoca.

La clave privada nunca sale de aquí hacia el registro, la columna `parametros` o la respuesta de la API:
`preparar` la devuelve aparte para que solo entre en la carga firmada.
"""

from __future__ import annotations

import logging

from fastapi import HTTPException

from app.flota import tunel_ajustes as aj
from app.flota import tunel_claves, tunel_puertos
from app.flota.broker import Broker, ErrorBroker, etiqueta_de

logger = logging.getLogger(__name__)


def un_solo_equipo(cuerpo: dict, destinos: list) -> None:
    if cuerpo.get("todos") is True or len(destinos) != 1:
        raise HTTPException(
            400,
            "Las órdenes del túnel de soporte se emiten a un solo equipo cada vez.",
        )


async def _automatico(conexion, destino: dict, pedido: int | None, broker: Broker):
    """Fase B: puerto libre según el servidor de túneles y el panel, par nuevo, baja + alta."""
    etiqueta = etiqueta_de(destino["nombre"], destino["equipo_id"])
    asignados = await tunel_puertos.mapa(conexion)
    ocupados = set(tunel_puertos.de_otros(asignados, destino["equipo_id"]))
    instaladas = await broker.listar()
    ocupados |= {p for p, etq in instaladas.items() if etq != etiqueta}
    puerto = pedido or asignados.get(destino["equipo_id"], {}).get("puerto")
    if puerto is None or puerto in ocupados:
        if pedido is not None:
            raise HTTPException(
                409, f"El puerto {pedido} ya está asignado a otro equipo: elija otro."
            )
        puerto = await broker.puerto_libre()
        if puerto in ocupados:
            puerto = tunel_puertos.menor_libre(ocupados)
    privada, publica, huella = tunel_claves.generar()
    await broker.baja(etiqueta)
    await broker.alta(etiqueta, puerto, publica)
    return puerto, privada, huella


async def preparar(
    conexion,
    destino: dict,
    parametros: dict,
    clave_pegada,
    *,
    broker: Broker | None = None,
) -> tuple[dict, str | None, dict]:
    """→ (parámetros que se firman, clave privada o None, parámetros para la columna y el registro).

    Se llama dentro de la transacción de la emisión. Lo tercero nunca contiene la clave: solo si la
    orden la lleva, su huella pública y el modo."""
    manual = tunel_claves.comprobar(clave_pegada)
    pedido = parametros.get("puerto_remoto")
    if manual is None and aj.automatico():
        await conexion.execute(tunel_puertos.SQL_CANDADO)
        try:
            puerto, clave, huella = await _automatico(
                conexion, destino, pedido, broker or Broker.desde_entorno()
            )
        except ErrorBroker as e:
            logger.error(
                "flota_tunel_broker_fallo | equipo=%s | %s", destino["nombre"], e
            )
            raise HTTPException(
                502,
                f"No se pudo registrar la clave del equipo en el servidor de túneles. {e}",
            ) from None
        modo = "automatico"
    else:
        puerto = await tunel_puertos.asignar(conexion, destino["equipo_id"], pedido)
        clave, huella = manual if manual else (None, None)
        modo = "manual"
    firmados = {**parametros, "puerto_remoto": puerto}
    visibles = {**firmados, "modo": modo, "clave_en_orden": clave is not None}
    if huella:
        visibles["clave_huella"] = huella
    return firmados, clave, visibles


async def revocar(destino: dict, *, broker: Broker | None = None) -> dict | None:
    """Fase B: quita del servidor de túneles la clave del equipo (al cerrar el túnel o retirar el equipo).

    Nunca interrumpe la acción del panel: si falla, se devuelve el aviso para dejarlo en el registro.
    """
    if not aj.automatico():
        return None
    try:
        await (broker or Broker.desde_entorno()).baja(
            etiqueta_de(destino["nombre"], destino["equipo_id"])
        )
        return {"clave_revocada": True}
    except ErrorBroker as e:
        logger.error("flota_tunel_broker_fallo | equipo=%s | %s", destino["nombre"], e)
        return {"clave_revocada": False, "aviso": str(e)}
