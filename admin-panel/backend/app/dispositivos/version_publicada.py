"""Versión de la app publicada en `/webmail/descargas/maquita-mail.json` (leída del disco).

El manifiesto lo copia Tecnología al publicar cada versión (`descargas-app/`). Con él se marca qué
teléfonos van atrasados y desde cuándo (campo `fecha` del manifiesto).
"""

import json
import os
from datetime import date

RUTA = os.environ.get(
    "DISP_MANIFIESTO_APP", "/opt/maquita-webmail/descargas-app/maquita-mail.json"
)


def leer() -> dict:
    """{versionName, versionCode, fecha} o {} si no hay manifiesto."""
    try:
        with open(RUTA, encoding="utf-8") as f:
            m = json.load(f)
        return {
            "versionName": str(m.get("versionName") or ""),
            "versionCode": int(m.get("versionCode") or 0),
            "fecha": str(m.get("fecha") or ""),
        }
    except Exception:
        return {}


def partes(v: str | None) -> tuple:
    """'1.2.8' -> (1, 2, 8) para comparar; lo que no sea número cuenta como 0."""
    out = []
    for p in str(v or "").split("."):
        d = "".join(ch for ch in p if ch.isdigit())
        out.append(int(d) if d else 0)
    return tuple(out) or (0,)


def atrasada(version_equipo: str | None, publicada: dict) -> bool:
    if not publicada.get("versionName") or not version_equipo:
        return False
    return partes(version_equipo) < partes(publicada["versionName"])


def dias_publicada(publicada: dict) -> int | None:
    try:
        return (date.today() - date.fromisoformat(publicada.get("fecha", "")[:10])).days
    except Exception:
        return None
