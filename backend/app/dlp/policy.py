"""
DLP — Política de decisión (Nivel 1, 2026-08-28).

Regla: los hallazgos solo BLOQUEAN cuando hay al menos un destinatario
EXTERNO (dominio que no es de Maquita ni está en la lista de confianza).
Entre cuentas internas la acción máxima es 'warn'.

El "enviar de todas formas" (override) sobre un bloqueo solo lo puede usar un
administrador y debe indicar un motivo, que queda en dlp_violations.reason.
"""

from __future__ import annotations

import json
import time

_SEVERITY = {"allow": 0, "audit": 1, "warn": 2, "block": 3}
_cache = {"ts": 0.0, "local": set(), "trusted": set()}
_TTL = 60.0


def _domain(addr: str) -> str:
    a = (addr or "").strip().lower()
    if "<" in a and ">" in a:
        a = a[a.rfind("<") + 1 : a.rfind(">")]
    return a.rsplit("@", 1)[1] if "@" in a else ""


async def _domains(db) -> tuple[set, set]:
    now = time.monotonic()
    if now - _cache["ts"] < _TTL:
        return _cache["local"], _cache["trusted"]
    local, trusted = set(), set()
    try:
        rows = await db.fetch("SELECT domain FROM domain WHERE active = true")
        local = {r["domain"].lower() for r in rows}
    except Exception:
        pass
    try:
        row = await db.fetchrow("SELECT trusted_domains FROM dlp_config WHERE id = 1")
        val = row["trusted_domains"] if row else None
        if isinstance(val, str):
            val = json.loads(val or "[]")
        trusted = {str(d).lower().strip() for d in (val or []) if d}
    except Exception:
        pass
    _cache.update(ts=now, local=local, trusted=trusted)
    return local, trusted


async def external_recipients(db, recipients) -> list[str]:
    """Destinatarios cuyo dominio no es local ni de confianza."""
    local, trusted = await _domains(db)
    out = []
    for r in recipients or []:
        d = _domain(r)
        if d and d not in local and d not in trusted:
            out.append(r)
    return out


async def remitentes_exentos(db) -> set:
    """Remitentes autorizados a enviar datos sensibles fuera de la organización.

    Nómina es el caso real: los roles de pago llevan cédula y van a correos
    personales. Bloquearlos rompe un proceso legítimo y mensual.

    Exento NO significa invisible: la violación se sigue registrando y sigue
    apareciendo en la pantalla de incidentes. Solo cambia que el correo sale.
    Así se puede revisar si un remitente autorizado empieza a enviar algo raro.
    """
    try:
        fila = await db.fetchrow(
            "SELECT remitentes_exentos FROM dlp_config WHERE id = 1"
        )
    except Exception:
        return set()
    if not fila or not fila["remitentes_exentos"]:
        return set()
    valor = fila["remitentes_exentos"]
    if isinstance(valor, str):
        import json as _json

        try:
            valor = _json.loads(valor)
        except Exception:
            return set()
    return {str(x).strip().lower() for x in (valor or []) if str(x).strip()}


async def decide(
    db, scan: dict, recipients, is_admin: bool = False, sender: str = ""
) -> dict:
    """Aplica la política al resultado de service.scan().

    Devuelve el mismo dict más: external (lista), can_override (bool) y
    exento (bool). Si no hay externos, un 'block' se rebaja a 'warn'.
    Si el remitente está en la lista de exentos, un 'block' también se rebaja,
    pero la violación se registra igual para poder revisarla.
    """
    ext = await external_recipients(db, recipients)
    action = scan.get("action", "allow")
    if action == "block" and not ext:
        action = "warn"
        for f in scan.get("findings", []):
            if f.get("action") == "block":
                f["action"] = "warn"
    exento = False
    if action == "block" and sender:
        if sender.strip().lower() in await remitentes_exentos(db):
            exento = True
            action = "warn"
            for f in scan.get("findings", []):
                if f.get("action") == "block":
                    f["action"] = "warn"
    return {
        **scan,
        "action": action,
        "external": ext,
        "exento": exento,
        "can_override": bool(is_admin) if action == "block" else True,
    }


async def is_admin(db, username: str) -> bool:
    try:
        row = await db.fetchrow(
            "SELECT 1 FROM admin WHERE username = $1 AND active = true", username
        )
        return row is not None
    except Exception:
        return False
