"""Alertas de seguridad: lo que necesita atención hoy, en una sola pantalla y en lenguaje llano.

Reúne los intentos de adivinar contraseñas (con el botón para cerrar IMAP y SMTP de la cuenta),
los bloqueos por envío a muchas personas (envios_masivos.py), los inicios de sesión riesgosos
pendientes y las anomalías abiertas. El panel consulta /resumen
al entrar para avisar de inmediato si hay algo pendiente.
"""

import re

from fastapi import APIRouter, Depends, Request

from app import organizacion
from app.alertas_seguridad import envios_masivos
from app.alertas_seguridad.ataques import agrupar, explicar
from app.auth.dependencies import get_current_admin

router = APIRouter(prefix="/api/alertas-seguridad", tags=["alertas-seguridad"])
HORAS = 48
ORDEN = {"alta": 0, "media": 1, "resuelta": 2}
LISTA_NEGRA = "/etc/maquita-mail/blacklist-ips.txt"

_ACCESOS = f"""
SELECT cuenta, ip, pais, servicio, ok, fallos, hora FROM seg_accesos_detalle
WHERE servicio IN ('imap', 'pop3', 'smtp') AND hora > now() - interval '{HORAS} hours'
  AND cuenta IN (SELECT cuenta FROM seg_accesos_detalle
                 WHERE fallos > 0 AND servicio IN ('imap', 'pop3', 'smtp') AND hora > now() - interval '{HORAS} hours')
"""
_USO = """
SELECT COALESCE(sum(ok), 0) FROM seg_accesos_detalle
WHERE cuenta = $1 AND servicio IN ('imap', 'pop3', 'smtp') AND ip::text NOT IN ('127.0.0.1', '::1')
  AND hora > now() - interval '14 days'
"""


def _db(r: Request):
    return r.app.state.db


def _bloqueadas() -> set:
    try:
        with open(LISTA_NEGRA, encoding="utf-8", errors="replace") as f:
            return set(re.findall(r"^([0-9a-fA-F.:]+)\s*$", f.read(), re.M))
    except OSError:
        return set()


async def _existe(db, tabla: str) -> bool:
    try:
        return bool(await db.fetchval("SELECT to_regclass($1)", tabla))
    except Exception:
        return False


async def _ataques(db) -> list[dict]:
    if not await _existe(db, "seg_accesos_detalle"):
        return []
    ataques = agrupar(await db.fetch(_ACCESOS))
    if not ataques:
        return []
    con_lista = await _existe(db, "auth_cuentas_solo_web")
    bloqueadas = _bloqueadas()
    pais = (organizacion.valor("ORG_PAIS_BASE", "ec") or "ec").upper()
    for a in ataques:
        cuenta = a["cuenta"]
        existe = bool(
            await db.fetchval(
                "SELECT 1 FROM mailbox WHERE username = $1 AND active = true", cuenta
            )
        )
        protegida = bool(
            con_lista
            and await db.fetchval(
                "SELECT 1 FROM auth_cuentas_solo_web WHERE username = $1", cuenta
            )
        )
        claves = (
            await db.fetchval(
                "SELECT count(*) FROM contrasenas_aplicacion WHERE username = $1 AND revocada IS NULL",
                cuenta,
            )
            or 0
        )
        usa = bool(await db.fetchval(_USO, cuenta))
        for d in a["direcciones"]:
            d["bloqueada"] = d["ip"] in bloqueadas
        a.update(explicar(a, existe, protegida, usa, claves, pais))
        a.update(
            {
                "existe": existe,
                "protegida": protegida,
                "se_puede_proteger": con_lista and existe and not protegida,
            }
        )
    # Primero lo que pide actuar, al final lo ya resuelto; dentro de cada grupo, lo más reciente.
    ataques.sort(key=lambda x: ORDEN.get(x["gravedad"], 1))
    return ataques


async def _otras(db) -> dict:
    riesgosos = altos = anomalias = 0
    if await _existe(db, "risky_logins"):
        f = await db.fetchrow(
            "SELECT count(*) AS n, count(*) FILTER (WHERE risk = 'high') AS altos FROM risky_logins WHERE status = 'open'"
        )
        riesgosos, altos = f["n"], f["altos"]
    if await _existe(db, "seg_alertas"):
        anomalias = (
            await db.fetchval(
                "SELECT count(*) FROM seg_alertas WHERE estado = 'abierta'"
            )
            or 0
        )
    return {
        "inicios_riesgosos": riesgosos,
        "inicios_riesgosos_altos": altos,
        "anomalias": anomalias,
    }


def _pendientes(ataques: list[dict], otras: dict) -> int:
    return (
        sum(1 for a in ataques if a["gravedad"] in ("alta", "media") and a["existe"])
        + otras["inicios_riesgosos"]
        + otras["anomalias"]
    )


@router.get("")
async def alertas(r: Request, a=Depends(get_current_admin)):
    db = _db(r)
    ataques, otras = await _ataques(db), await _otras(db)
    envios = await envios_masivos.pendientes(db)
    return {
        "horas": HORAS,
        "ataques": ataques,
        "envios": envios,
        **otras,
        "pendientes": _pendientes(ataques, otras) + envios_masivos.sin_revisar(envios),
    }


@router.get("/resumen")
async def resumen(r: Request, a=Depends(get_current_admin)):
    db = _db(r)
    ataques, otras = await _ataques(db), await _otras(db)
    lista = await envios_masivos.pendientes(db)
    envios = envios_masivos.sin_revisar(lista)
    return {
        "pendientes": _pendientes(ataques, otras) + envios,
        "envios": envios,
        "envios_bloqueadas": len(
            {
                e["cuenta"]
                for e in lista
                if not e["atendido"] and e["existe"] and not e["activa"]
            }
        ),
        "ataques": sum(1 for x in ataques if x["gravedad"] == "alta"),
        "por_revisar": sum(
            1 for x in ataques if x["gravedad"] == "media" and x["existe"]
        ),
        **otras,
    }
