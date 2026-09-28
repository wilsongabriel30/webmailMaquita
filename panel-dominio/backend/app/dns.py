"""Verificación DNS del dominio: lo que el resto del mundo ve al escribirle.

Solo consulta; no cambia nada. Sirve para que la organización, que es quien administra su DNS,
compruebe que MX, SPF, DKIM y DMARC están bien. El dominio sale de la lista de dominios
asignados, nunca del texto de la petición.
"""

import asyncio
import re
from asyncio.subprocess import DEVNULL, PIPE

from fastapi import APIRouter, Depends, HTTPException

from app import config_extra
from app.sesion import admin_actual

router = APIRouter(prefix="/api/dns", tags=["dns"])

_CLAVE = re.compile(r"(?:^|;)p=[A-Za-z0-9+/]{20,}")


def orden(tipo: str, nombre: str) -> list[str]:
    """La orden de dig. El nombre va con -q, que lo toma siempre como nombre y nunca como opción;
    dig no entiende el separador «--» (con él no consultaba nada y todo salía «sin registro»)."""
    return ["dig", "+short", "+time=3", "+tries=1", "-t", tipo, "-q", nombre]


async def consultar(tipo: str, nombre: str) -> list[str]:
    try:
        proc = await asyncio.create_subprocess_exec(
            *orden(tipo, nombre), stdout=PIPE, stderr=DEVNULL)
        salida, _ = await asyncio.wait_for(proc.communicate(), timeout=8)
    except (asyncio.TimeoutError, OSError):
        return []
    if proc.returncode != 0:
        return []
    lineas = [l.strip() for l in salida.decode(errors="replace").splitlines() if l.strip() and not l.startswith(";")]
    # Un TXT largo llega en trozos entre comillas: "v=DKIM1; p=abc" "def"
    return [l.replace('" "', "").strip('"') for l in lineas][:20]


def juzgar(mx: list[str], txt: list[str], dmarc: list[str], dkim: dict[str, list[str]]) -> dict:
    spf = [t for t in txt if t.lower().startswith("v=spf1")]
    politica = [t for t in dmarc if t.lower().startswith("v=dmarc1")]
    # Una clave vacía (p=) es una firma revocada: no cuenta.
    firmas = {s: v for s, v in dkim.items() if any(_CLAVE.search(x.replace(" ", "")) for x in v)}
    return {
        "mx": {"bien": bool(mx), "registros": mx,
               "mensaje": "Hay servidor de correo publicado." if mx else "Sin registro MX: nadie puede escribir a este dominio."},
        "spf": {"bien": len(spf) == 1, "registros": spf,
                "mensaje": "SPF correcto." if len(spf) == 1 else
                ("Hay más de un registro SPF: debe quedar uno solo." if spf else "Sin SPF: cualquiera puede hacerse pasar por este dominio. Agrega un TXT que empiece por v=spf1.")},
        "dkim": {"bien": bool(firmas), "registros": [f"{s}: {v[0][:60]}…" for s, v in firmas.items()],
                 "mensaje": "Firma DKIM publicada." if firmas else "No se encontró firma DKIM en los selectores habituales. Pide la clave pública al administrador general."},
        "dmarc": {"bien": bool(politica), "registros": politica,
                  "mensaje": "DMARC publicado." if politica else "Sin DMARC: agrega un TXT en _dmarc con v=DMARC1; p=quarantine."},
    }


@router.get("/{dominio}")
async def verificar(dominio: str, admin: dict = Depends(admin_actual)):
    dominio = str(dominio or "").strip().lower()
    if dominio not in admin["dominios"]:
        raise HTTPException(404, "No encontrado")
    selectores = config_extra.SELECTORES_DKIM[:8]
    mx, txt, dmarc, *firmas = await asyncio.gather(
        consultar("MX", dominio), consultar("TXT", dominio), consultar("TXT", "_dmarc." + dominio),
        *[consultar("TXT", f"{s}._domainkey.{dominio}") for s in selectores])
    return {"dominio": dominio, **juzgar(mx, txt, dmarc, dict(zip(selectores, firmas)))}
