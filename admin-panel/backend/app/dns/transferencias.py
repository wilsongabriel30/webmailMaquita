"""Transferencias de zona a servidores secundarios (panel → Zonas DNS → Secundarios).

A quién se permite pedir las zonas (allow-transfer), a quién se avisa de cada cambio (also-notify), clave
TSIG opcional y «maestro oculto». Lo guarda y aplica el ayudante maquita-dns (named-checkconf antes de
recargar y vuelta atrás si BIND lo rechaza). Aquí se valida la forma; el ayudante revalida todo.

Este router se incluye antes que el de «Zonas DNS» para que «/api/dns/transferencias» no lo tome
«/api/dns/{zona}».
"""

import ipaddress
import re
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from app.auth.dependencies import get_current_admin, require_superadmin
from app.dns.ayudante import auditar, ayudante, b64

router = APIRouter(prefix="/api/dns/transferencias", tags=["dns"])
RE_DESTINO = re.compile(r"\[([0-9a-fA-F:.]+)\](?::([0-9]{1,5}))?|([0-9.]+)(?::([0-9]{1,5}))?|([0-9a-fA-F:]+)")


def red(valor: str) -> str:
    try:
        r = ipaddress.ip_network(valor.strip(), strict=True)
    except ValueError:
        raise HTTPException(400, f"«{valor}» no es una IP ni una red válida")
    if r.prefixlen == 0:
        raise HTTPException(400, f"«{valor}» abriría las zonas a cualquiera")
    return str(r.network_address) if r.num_addresses == 1 else str(r)


def destino(valor: str) -> str:
    """IP con puerto opcional: 198.51.100.53, 198.51.100.53:5353, 2001:db8::53 o [2001:db8::53]:5353."""
    m = RE_DESTINO.fullmatch(valor.strip())
    if not m:
        raise HTTPException(400, f"«{valor}» no es una IP válida")
    ip = m.group(1) or m.group(3) or m.group(5)
    puerto = m.group(2) or m.group(4)
    try:
        ipaddress.ip_address(ip)
    except ValueError:
        raise HTTPException(400, f"«{valor}» no es una IP válida")
    if puerto is not None and not 1 <= int(puerto) <= 65535:
        raise HTTPException(400, f"«{valor}»: puerto fuera de rango")
    return valor.strip()


class Transferencias(BaseModel):
    transferir_a: list[str] = Field(default_factory=list, max_length=20)
    notificar_a: list[str] = Field(default_factory=list, max_length=20)
    maestro_oculto: bool = False
    tsig: Literal["mantener", "generar", "quitar"] = "mantener"


@router.get("")
async def ver(admin: dict = Depends(get_current_admin)):
    return await ayudante("dns", "transferencias-ver")


@router.put("")
async def guardar(body: Transferencias, r: Request, admin: dict = Depends(require_superadmin)):
    datos = {"transferir_a": [red(v) for v in body.transferir_a if v.strip()],
             "notificar_a": [destino(v) for v in body.notificar_a if v.strip()],
             "maestro_oculto": body.maestro_oculto, "tsig": body.tsig}
    res = await ayudante("dns", "transferencias", b64(datos))
    # Sin el secreto TSIG (nunca llega aquí): solo qué se cambió.
    await auditar(r, admin, "dns_transferencias", "servidor", datos)
    return res


@router.post("/secreto")
async def secreto(r: Request, admin: dict = Depends(require_superadmin)):
    """Muestra el secreto TSIG para copiarlo al secundario (orden explícita, queda en auditoría)."""
    res = await ayudante("dns", "transferencias-secreto")
    await auditar(r, admin, "dns_transferencias_ver_secreto", "servidor")
    return res
