"""Agente de Seguridad — AIR autónomo.

Investiga señales de riesgo con la IA y, si dry_run=False (y la política lo
permite vía threat_config), contiene cuentas comprometidas. Reusa el motor AIR.
"""
from app.agents.base import Agent


class SecurityAgent(Agent):
    name = "seguridad"
    descripcion = "Vigila señales de riesgo, investiga con IA y contiene cuentas comprometidas."

    async def run(self, ctx, dry_run: bool = True) -> dict:
        from app.air.engine import run_cycle
        inc = await run_cycle(ctx.db, ctx.redis, hours=24, use_ai=True,
                              auto_respond=not dry_run)
        actions = [{
            "type": "contener" if i["responded"] else "recomendar",
            "target": i["username"],
            "detail": (i.get("ai") or {}).get("resumen") or "; ".join(i["reasons"]),
            "applied": i["responded"],
        } for i in inc]
        contenidos = sum(1 for i in inc if i["responded"])
        return {"agent": self.name, "descripcion": self.descripcion,
                "summary": f"{len(inc)} incidente(s); {contenidos} contenido(s)",
                "actions": actions}
