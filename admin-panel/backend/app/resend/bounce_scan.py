"""Detecta que cuentas recibieron rebotes recientemente, leyendo el log de Postfix.

Sirve para poblar el selector del panel sin tener que recorrer todos los buzones
(que seria lento). El detalle de cada rebote se lee despues del buzon, en mailbox_read.
"""
import asyncio
import re
from asyncio.subprocess import PIPE

# Linea tipica del log cuando Postfix devuelve un correo al remitente:
#   postfix/bounce[123]: 657914008F854: sender non-delivery notification: DAC6A400A25CD
_LINEA_REBOTE = re.compile(r"postfix/bounce\[\d+\]: ([0-9A-F]+): sender non-delivery")
# El remitente aparece en otra linea del mismo queue-id: "657914008F854: from=<x@y>, size=..."
_REMITENTE = re.compile(r"([0-9A-F]+): from=<([^>]+)>")

LOGS = "/var/log/mail.log /var/log/mail.log.1"


async def _leer_logs() -> str:
    """Devuelve el contenido de los logs de correo recientes (sin comprimir)."""
    proc = await asyncio.create_subprocess_shell(
        f"cat {LOGS} 2>/dev/null", stdout=PIPE, stderr=PIPE
    )
    out, _ = await proc.communicate()
    return out.decode("utf-8", "ignore")


async def cuentas_con_rebotes() -> list[dict]:
    """Lista de cuentas con rebotes recientes y cuantos tuvieron.

    Devuelve: [{"cuenta": "x@maquita.com.ec", "rebotes": 3}, ...] ordenado de mas a menos.
    """
    texto = await _leer_logs()

    # 1. queue-ids que acabaron rebotados
    ids_rebotados = set(_LINEA_REBOTE.findall(texto))
    if not ids_rebotados:
        return []

    # 2. remitente de cada uno de esos queue-ids
    conteo: dict[str, int] = {}
    for qid, remitente in _REMITENTE.findall(texto):
        if qid in ids_rebotados and remitente:
            conteo[remitente] = conteo.get(remitente, 0) + 1

    return [
        {"cuenta": cuenta, "rebotes": n}
        for cuenta, n in sorted(conteo.items(), key=lambda x: -x[1])
    ]
