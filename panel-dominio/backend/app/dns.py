"""Verificación DNS del dominio: lo que el resto del mundo ve al escribirle.

Solo consulta; no cambia nada. El dominio sale de la lista de dominios asignados, nunca del
texto de la petición.

POR QUÉ SE PREGUNTA FUERA Y NO AL RESOLUTOR DEL SERVIDOR
Muchas redes tienen una versión interna de sus zonas (DNS dividido) y redirigen hacia ella
todo lo que sale por el puerto 53. Preguntando al resolutor local se ve la zona de casa, que
no es la que ven los demás: aquí llegó a decir que un dominio sano no tenía MX. Se pregunta
por HTTPS a un resolutor público, que no se puede redirigir.

TRES RESPUESTAS DISTINTAS, QUE NO SE DEBEN CONFUNDIR
- el registro existe o no existe (veredicto);
- el dominio entero no existe en internet (no está registrado o venció);
- no se pudo consultar (sin salida a internet): no se afirma nada.
"""

import asyncio
import json
import re
import urllib.parse
import urllib.request

from fastapi import APIRouter, Depends, HTTPException

from app import config_extra
from app.sesion import admin_actual

router = APIRouter(prefix="/api/dns", tags=["dns"])

NO_EXISTE = 3
_CLAVE = re.compile(r"(?:^|;)p=[A-Za-z0-9+/]{20,}")
_TIPOS = {"MX": 15, "TXT": 16}


def _pedir(url: str, nombre: str, tipo: str) -> dict:
    if not url.startswith("https://"):
        raise ValueError("El resolutor debe ser https")
    peticion = urllib.request.Request(
        url + "?" + urllib.parse.urlencode({"name": nombre, "type": tipo}),
        headers={"accept": "application/dns-json", "user-agent": "portal-dominio"})
    with urllib.request.urlopen(peticion, timeout=6) as r:  # nosemgrep: la dirección sale de la configuración, no de la petición
        return json.loads(r.read(200_000))


def leer(respuesta: dict, tipo: str) -> tuple[int, list[str]]:
    """(estado, registros) de una respuesta en formato JSON de DNS sobre HTTPS."""
    estado = int(respuesta.get("Status", -1))
    datos = [str(a.get("data", "")) for a in respuesta.get("Answer") or [] if a.get("type") == _TIPOS[tipo]]
    # Un TXT largo llega en trozos entre comillas: "v=DKIM1; p=abc" "def"
    return estado, [d.replace('" "', "").strip('"').strip() for d in datos][:20]


async def consultar(tipo: str, nombre: str) -> tuple[int | None, list[str]]:
    """Pregunta a los resolutores configurados, en orden. Estado None = no se pudo consultar."""
    for url in config_extra.RESOLUTORES_DOH:
        try:
            return leer(await asyncio.to_thread(_pedir, url, nombre, tipo), tipo)
        except Exception:
            continue
    return None, []


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


def sin_veredicto(mensaje: str) -> dict:
    return {k: {"bien": None, "registros": [], "mensaje": mensaje} for k in ("mx", "spf", "dkim", "dmarc")}


@router.get("/{dominio}")
async def verificar(dominio: str, admin: dict = Depends(admin_actual)):
    dominio = str(dominio or "").strip().lower()
    if dominio not in admin["dominios"]:
        raise HTTPException(404, "No encontrado")
    selectores = config_extra.SELECTORES_DKIM[:8]
    (e_mx, mx), (e_txt, txt), (e_dm, dmarc), *firmas = await asyncio.gather(
        consultar("MX", dominio), consultar("TXT", dominio), consultar("TXT", "_dmarc." + dominio),
        *[consultar("TXT", f"{s}._domainkey.{dominio}") for s in selectores])
    if e_mx is None or e_txt is None:
        return {"dominio": dominio, "consultado": False, "existe": None,
                **sin_veredicto("No se pudo consultar ahora. Inténtalo de nuevo en unos minutos.")}
    if e_mx == NO_EXISTE and e_txt == NO_EXISTE:
        return {"dominio": dominio, "consultado": True, "existe": False,
                **sin_veredicto("El dominio no existe en internet: no está registrado o venció. Nadie de fuera puede escribirle.")}
    return {"dominio": dominio, "consultado": True, "existe": True,
            **juzgar(mx, txt, dmarc, {s: f[1] for s, f in zip(selectores, firmas)})}
