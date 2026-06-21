"""Agente de Postura — auditor de seguridad del correo (read-only).

Reúne hechos de configuración y pide a la IA 3 recomendaciones priorizadas.
"""
from app.agents.base import Agent
from app.agents.llm import ask


class PostureAgent(Agent):
    name = "postura"
    descripcion = "Audita la postura de seguridad del correo y recomienda mejoras con IA."

    async def run(self, ctx, dry_run: bool = True) -> dict:
        db = ctx.db

        async def val(sql):
            try:
                return await db.fetchval(sql)
            except Exception:
                return None

        total = await val("SELECT count(*) FROM mailbox WHERE active") or 0
        facts = {
            "buzones_activos": total,
            "dlp_activo": await val("SELECT enabled FROM dlp_config WHERE id=1"),
            "safelinks_activo": await val("SELECT enabled FROM safelinks_config WHERE id=1"),
            "con_2fa": await val("SELECT count(*) FROM user_totp WHERE enabled") or 0,
            "politicas_retencion": await val("SELECT count(*) FROM retention_policies WHERE is_active") or 0,
            "auto_contencion": await val("SELECT auto_disable_on_compromise FROM threat_config WHERE id=1"),
        }
        if total:
            facts["pct_2fa"] = round(100 * facts["con_2fa"] / total)
        rec = await ask(
            f"Postura de seguridad del correo institucional (hechos): {facts}. "
            "Da exactamente 3 recomendaciones concretas y priorizadas (alta/media/baja).",
            system="Eres un consultor de ciberseguridad de correo. Conciso, accionable, en español.")
        return {"agent": self.name, "descripcion": self.descripcion,
                "summary": "Auditoría de postura de seguridad", "facts": facts,
                "actions": [], "ai": rec}
