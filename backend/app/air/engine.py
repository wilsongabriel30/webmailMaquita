"""Orquestador AIR: señales -> playbook -> (triage IA) -> respuesta/registro.

Seguro por defecto: SOLO detecta y recomienda. La contención automática
ocurre únicamente si auto_respond=True Y threat_config.auto_disable_on_compromise.
"""

import logging

from app.air import playbooks, responder
from app.air import signals as sig_mod
from app.air import triage as triage_mod

logger = logging.getLogger("air.engine")


async def _auto_enabled(db) -> bool:
    try:
        row = await db.fetchrow(
            "SELECT auto_disable_on_compromise FROM threat_config WHERE id=1"
        )
        return bool(row and row["auto_disable_on_compromise"])
    except Exception:
        return False


async def run_cycle(
    db, redis, hours: int = 24, use_ai: bool = True, auto_respond: bool = False
) -> list[dict]:
    auto_ok = auto_respond and await _auto_enabled(db)
    users = await sig_mod.collect(db, hours)
    incidents = []
    for username, sig in sorted(users.items(), key=lambda kv: -kv[1]["score"]):
        if sig["score"] == 0:
            continue
        pb = playbooks.evaluate(sig)
        ai = (
            await triage_mod.assess(username, sig, pb)
            if (use_ai and pb["severity"] != "low")
            else {}
        )
        inc = {"username": username, "signals": sig, **pb, "ai": ai, "responded": False}

        # contención automática solo con evidencia fuerte + habilitado explícitamente
        if auto_ok and pb["action"] == "lock":
            await responder.lock_account(
                db, redis, username, pb["rationale"], auto=True
            )
            inc["responded"] = True
        else:
            detail = "; ".join(pb["reasons"]) or pb["rationale"]
            if ai:
                detail += (
                    f" | IA(Qwen): {ai.get('recomendacion','')} "
                    f"({ai.get('confianza',0)}%) {ai.get('resumen','')}"
                )
            await responder.record_incident(db, username, pb["severity"], detail)
        incidents.append(inc)
    logger.info("AIR ciclo: %d incidentes (auto=%s)", len(incidents), auto_ok)
    return incidents
