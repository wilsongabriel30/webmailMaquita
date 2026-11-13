"""Botón «Enviar mensaje» de las alertas: envía a la persona el aviso y deja constancia.

Sale por sendmail, como los demás avisos del servidor, con el remitente de los avisos
(ORG_REMITENTE_AVISOS) y las respuestas dirigidas a Tecnología. Tres ajustes opcionales en
/etc/maquita-mail/organizacion.env:
  ORG_REMITENTE_MENSAJES_ALERTAS   remitente propio de estos mensajes (por defecto, el de los avisos)
  ORG_CORREO_TECNOLOGIA            a quién llegan las respuestas (por defecto, el primero de ORG_CORREOS_AVISOS)
  ORG_URL_APP_CORREO               enlace de la aplicación de correo (vacío: el mensaje no la menciona)

Cada envío se guarda en alertas_mensajes_persona (quién, a quién, cuándo y el texto). Si ya se
escribió a esa cuenta en las últimas 24 horas, hay que confirmar para enviar otro.
"""

import asyncio
import json
from asyncio.subprocess import PIPE

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from app import organizacion
from app.alertas_seguridad import mensaje_a_persona as redaccion
from app.alertas_seguridad.ataques import HORAS, agrupar
from app.auth.dependencies import require_role
from app.seguridad import zona

solo_administradores = require_role("superadmin", "admin")
router = APIRouter(prefix="/api/alertas-seguridad/mensajes", tags=["alertas-seguridad"])
TABLA = "alertas_mensajes_persona"
HORAS_FRENO = 24
SENDMAIL = "/usr/sbin/sendmail"

_ACCESOS_DE_LA_CUENTA = f"""
SELECT cuenta, ip, pais, servicio, ok, fallos, hora FROM seg_accesos_detalle
WHERE cuenta = $1 AND servicio IN ('imap', 'pop3', 'smtp') AND hora > now() - interval '{HORAS} hours'
"""
_ULTIMOS = f"""
SELECT DISTINCT ON (cuenta) cuenta, enviado, enviado_por,
       enviado > now() - interval '{HORAS_FRENO} hours' AS reciente
FROM {TABLA} WHERE cuenta = ANY($1::text[]) ORDER BY cuenta, enviado DESC
"""


class Envio(BaseModel):
    cuenta: str
    asunto: str
    cuerpo: str
    confirmar: bool = (
        False  # ya se le escribió hace menos de 24 horas y se quiere enviar otro
    )


def _db(r: Request):
    return r.app.state.db


async def disponible(db) -> bool:
    """La instalación tiene la tabla del registro (migración del 13/11/2026)."""
    try:
        return bool(await db.fetchval("SELECT to_regclass($1)", TABLA))
    except Exception:
        return False


def remitente() -> str:
    return organizacion.valor("ORG_REMITENTE_MENSAJES_ALERTAS") or organizacion.valor(
        "ORG_REMITENTE_AVISOS", f"postmaster@{organizacion.dominio_principal()}"
    )


def responder_a() -> str:
    return (
        organizacion.valor("ORG_CORREO_TECNOLOGIA")
        or (organizacion.correos_de_avisos() or [""])[0]
    )


def _pais_propio() -> str:
    return (organizacion.valor("ORG_PAIS_BASE", "ec") or "ec").upper()


def _borrador(ataque: dict, nombre: str) -> dict:
    primera = ataque["direcciones"][0] if ataque.get("direcciones") else {}
    return redaccion.redactar(
        ataque["cuenta"],
        nombre,
        ataque.get("ultimo"),
        desde_red_interna=(primera.get("pais") or "").upper() == "LAN",
        url_correo=organizacion.url_correo(),
        enlace_app=organizacion.valor("ORG_URL_APP_CORREO"),
        zona=zona.zona(""),
    )


async def anotar(db, ataques: list[dict]) -> None:
    """Añade a cada alerta `mensaje`: si procede escribir a la persona, el texto y el último envío."""
    if not ataques or not await disponible(db):
        return
    cuentas = [a["cuenta"] for a in ataques]
    ultimos = {f["cuenta"]: f for f in await db.fetch(_ULTIMOS, cuentas)}
    nombres = {
        f["username"]: f["name"] or ""
        for f in await db.fetch(
            "SELECT username, name FROM mailbox WHERE username = ANY($1::text[])",
            cuentas,
        )
    }
    pais = _pais_propio()
    for a in ataques:
        u = ultimos.get(a["cuenta"])
        se_puede = redaccion.procede(
            a, a.get("existe", False), a.get("protegida", False), pais
        )
        borrador = (
            _borrador(a, nombres.get(a["cuenta"], ""))
            if se_puede
            else {"asunto": "", "cuerpo": ""}
        )
        a["mensaje"] = {
            "se_puede_enviar": se_puede,
            **borrador,
            "enviado": u["enviado"].isoformat() if u else None,
            "enviado_por": u["enviado_por"] if u else "",
            "reciente": bool(u and u["reciente"]),
        }


async def entregar(mensaje, sobre: str, destinatario: str) -> None:
    """Entrega por sendmail. El destinatario va como argumento (sin -t): solo recibe esa cuenta."""
    proc = await asyncio.create_subprocess_exec(
        SENDMAIL,
        "-i",
        "-f",
        sobre,
        "--",
        destinatario,
        stdin=PIPE,
        stdout=PIPE,
        stderr=PIPE,
    )
    _, error = await asyncio.wait_for(proc.communicate(mensaje.as_bytes()), 60)
    if proc.returncode != 0:
        raise RuntimeError(error.decode(errors="replace")[-300:])


async def _alerta_de(db, cuenta: str) -> dict | None:
    """La alerta vigente de esa cuenta, si es de las que admiten el mensaje."""
    if not await db.fetchval(
        "SELECT 1 FROM mailbox WHERE username = $1 AND active = true", cuenta
    ):
        return None
    protegida = bool(
        await db.fetchval("SELECT to_regclass('auth_cuentas_solo_web')")
        and await db.fetchval(
            "SELECT 1 FROM auth_cuentas_solo_web WHERE username = $1", cuenta
        )
    )
    ataques = agrupar(await db.fetch(_ACCESOS_DE_LA_CUENTA, cuenta))
    if not ataques or not redaccion.procede(
        ataques[0], True, protegida, _pais_propio()
    ):
        return None
    return ataques[0]


@router.post("")
async def enviar(body: Envio, r: Request, a: dict = Depends(solo_administradores)):
    """Envía el mensaje a la persona de la alerta y lo registra."""
    db = _db(r)
    if not await disponible(db):
        raise HTTPException(
            404, "Esta instalación aún no tiene el registro de mensajes de las alertas"
        )
    cuenta = (body.cuenta or "").strip().lower()
    asunto = redaccion.limpiar_asunto(body.asunto)
    cuerpo = redaccion.limpiar_cuerpo(body.cuerpo)
    if not asunto or not cuerpo:
        raise HTTPException(400, "Escriba el asunto y el texto del mensaje")
    if not await _alerta_de(db, cuenta):
        raise HTTPException(
            404,
            "Esa cuenta ya no tiene una alerta de este tipo. Actualice la página.",
        )
    previo = await db.fetchrow(
        f"SELECT enviado, enviado_por FROM {TABLA} WHERE cuenta = $1 "
        f"AND enviado > now() - interval '{HORAS_FRENO} hours' ORDER BY enviado DESC LIMIT 1",
        cuenta,
    )
    if previo and not body.confirmar:
        raise HTTPException(
            409,
            f"Ya se envió un mensaje a {cuenta} en las últimas {HORAS_FRENO} horas "
            f"(lo envió {previo['enviado_por']}). Confirme si quiere enviar otro.",
        )
    de = remitente()
    correo = redaccion.componer(de, responder_a(), cuenta, asunto, cuerpo)
    try:
        await entregar(correo, redaccion.direccion(de), cuenta)
    except Exception:
        raise HTTPException(
            502,
            "El servidor no pudo enviar el mensaje. Inténtelo de nuevo en un momento.",
        )
    fila = await db.fetchrow(
        f"INSERT INTO {TABLA} (cuenta, asunto, cuerpo, remitente, enviado_por) "
        "VALUES ($1, $2, $3, $4, $5) RETURNING id, enviado",
        cuenta,
        asunto,
        cuerpo,
        redaccion.direccion(de),
        a["username"],
    )
    await db.execute(
        "INSERT INTO admin_audit (admin_id, admin_username, action, target, details, ip_address) "
        "VALUES ($1, $2, $3, $4, $5::jsonb, $6)",
        a["id"],
        a["username"],
        "alerta_mensaje_a_persona",
        cuenta,
        json.dumps(
            {"mensaje_id": fila["id"], "asunto": asunto, "repetido": bool(previo)}
        ),
        r.headers.get("X-Real-IP", r.client.host if r.client else ""),
    )
    return {
        "ok": True,
        "cuenta": cuenta,
        "enviado": fila["enviado"].isoformat(),
        "enviado_por": a["username"],
    }
