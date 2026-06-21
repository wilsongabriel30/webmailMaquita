"""Agente de Briefing — informe diario de seguridad en lenguaje natural.

Resume la actividad de riesgo del día (logins riesgosos, DLP, safelinks, AIR)
en un parte breve para el administrador. Read-only.
"""
from app.agents.base import Agent
from app.agents.llm import ask


class BriefingAgent(Agent):
    name = "briefing"
    descripcion = "Redacta un parte diario de seguridad del correo en lenguaje natural."

    async def run(self, ctx, dry_run: bool = True) -> dict:
        db = ctx.db

        async def cnt(sql):
            try:
                return await db.fetchval(sql) or 0
            except Exception:
                return 0

        d = {
            "logins_riesgo_alto": await cnt("SELECT count(*) FROM risky_logins WHERE created_at > now()-interval '24 hours' AND lower(risk)='high'"),
            "violaciones_dlp": await cnt("SELECT count(*) FROM dlp_violations WHERE created_at > now()-interval '24 hours'"),
            "clics_peligrosos": await cnt("SELECT count(*) FROM safelinks_clicks WHERE created_at > now()-interval '24 hours' AND lower(coalesce(verdict,'')) IN ('suspicious','malicious','blocked')"),
            "incidentes_air": await cnt("SELECT count(*) FROM threat_actions WHERE actor='AIR' AND created_at > now()-interval '24 hours'"),
            "en_cola": await cnt("SELECT count(*) FROM mailbox WHERE false"),
        }
        texto = await ask(
            f"Datos de seguridad del correo en las últimas 24h: {d}. "
            "Redacta un parte breve (4-6 líneas) para el administrador: qué pasó, "
            "si hay algo urgente, y una acción sugerida.",
            system="Eres el analista de seguridad de Maquita. Parte conciso y claro, en español.")
        return {"agent": self.name, "descripcion": self.descripcion,
                "summary": "Parte diario de seguridad", "facts": d,
                "actions": [], "ai": texto}
