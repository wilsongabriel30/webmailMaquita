"""Qué correos NO entran al índice del asistente aunque estén en una carpeta indexable (08/11/2026).

La dirección pidió que el spam, la publicidad masiva y los mensajes automáticos del servidor no
«ensucien» las respuestas del asistente. Se decide con las cabeceras, sin leer el cuerpo:

- «spam»: el filtro del servidor ya lo marcó (X-Spam-Flag: YES) aunque esté en la Bandeja.
- «servidor»: rebotes y avisos automáticos (MAILER-DAEMON, postmaster, Auto-Submitted ≠ no).
- «publicidad»: envíos masivos con enlace para darse de baja (List-Unsubscribe) y Precedence
  bulk/list/junk.

Los correos de los dominios de la casa (los habilitados en rag_domains, p. ej. los avisos de
Raíces Tareas) nunca se omiten: son trabajo. Lo omitido se anota en rag_omitidos para no volver
a leerlo cada noche (ver app.rag.omitidos).
"""

import re

CAMPOS_EXTRA = (
    "X-Spam-Flag",
    "Precedence",
    "Auto-Submitted",
    "List-Unsubscribe",
    "Return-Path",
)

_RE_SERVIDOR = re.compile(
    r"(mailer-daemon|postmaster|no[-_.]?reply@.*\b(bounce|mailer)\b)", re.I
)
_RE_CORREO = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")


def dominio_de(direccion: str) -> str:
    m = _RE_CORREO.search(direccion or "")
    return m.group(0).rsplit("@", 1)[1].lower() if m else ""


def es_de_la_casa(cab: dict, dominios_casa) -> bool:
    return dominio_de(cab.get("de", "")) in set(d.lower() for d in dominios_casa or ())


def motivo_omision(cab: dict, dominios_casa=()) -> str | None:
    """None si el correo se indexa; si no, «spam», «servidor» o «publicidad»."""
    if es_de_la_casa(cab, dominios_casa):
        return None
    extra = {
        k.lower(): (v or "").strip().lower()
        for k, v in (cab.get("extra") or {}).items()
    }
    if extra.get("x-spam-flag", "").startswith("yes"):
        return "spam"
    de = (cab.get("de") or "").lower()
    retorno = extra.get("return-path", "")
    auto = extra.get("auto-submitted", "")
    if _RE_SERVIDOR.search(de) or _RE_SERVIDOR.search(retorno) or retorno == "<>":
        return "servidor"
    if auto and auto != "no":
        return "servidor"
    precedencia = extra.get("precedence", "")
    if extra.get("list-unsubscribe") and precedencia in {"bulk", "list", "junk"}:
        return "publicidad"
    return None


async def dominios_casa(db) -> set[str]:
    """Dominios habilitados para el asistente: sus remitentes nunca se omiten."""
    try:
        filas = await db.fetch("SELECT domain FROM rag_domains WHERE enabled=true")
        return {str(f["domain"]).lower() for f in filas}
    except Exception:
        return set()
