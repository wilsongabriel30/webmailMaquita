"""Acceso Condicional (Conditional Access) — políticas condición→acción en logins.

Evalúa las políticas ACTIVAS contra un evento de login (riesgo, país, motivos) y
aplica la acción más fuerte. Aditivo y seguro: todas las políticas vienen OFF;
si no hay políticas activas, no hace nada (el correo no se afecta).
"""
import logging

logger = logging.getLogger("conditional_access")
_ORDER = {"alertar": 1, "requerir_2fa": 2, "bloquear": 3}


async def _active(db):
    try:
        return [dict(r) for r in await db.fetch(
            "SELECT name, condition, action FROM conditional_access_policies WHERE enabled=true")]
    except Exception:
        return []


def _matches(cond, risk, country, reasons, trusted):
    rsn = " ".join(reasons or []).lower()
    if cond == "riesgo_alto":
        return risk == "high"
    if cond == "pais_no_confiable":
        return bool(country) and country not in (trusted or [])
    if cond == "viaje_imposible":
        return "imposible" in rsn
    return False


async def evaluate_and_apply(db, username, risk, country, reasons, trusted):
    matched = [p for p in await _active(db)
               if _matches(p["condition"], risk, country, reasons, trusted)]
    if not matched:
        return []
    strongest = max((p["action"] for p in matched), key=lambda a: _ORDER.get(a, 0))
    try:
        if strongest == "bloquear":
            await db.execute("UPDATE mailbox SET active=false, modified=now() WHERE username=$1", username)
            await db.execute(
                "INSERT INTO threat_actions (action,target,detail,actor,auto) "
                "VALUES ('account_locked',$1,$2,'acceso-condicional',true)",
                username, f"Bloqueado por acceso condicional ({country}, riesgo {risk})")
        elif strongest == "requerir_2fa":
            await db.execute(
                "INSERT INTO threat_actions (action,target,detail,actor,auto) "
                "VALUES ('require_2fa',$1,$2,'acceso-condicional',true)",
                username, f"Requiere 2FA por acceso condicional ({country})")
        else:
            await db.execute(
                "INSERT INTO threat_actions (action,target,detail,actor,auto) "
                "VALUES ('alerta',$1,$2,'acceso-condicional',true)",
                username, f"Alerta de acceso condicional ({country}, riesgo {risk})")
    except Exception as e:
        logger.warning("acceso condicional no aplicado: %s", e)
    return [{"policy": p["name"], "action": p["action"]} for p in matched]
