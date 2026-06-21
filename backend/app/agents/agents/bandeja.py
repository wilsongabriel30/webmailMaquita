"""Agente de Triage de Bandeja.

Lee la bandeja de un usuario (vía impersonación Dovecot master) y clasifica cada
correo con la IA local (Qwen): categoría + prioridad. Read-only (no mueve nada).
Parámetro: params["user"] = correo del buzón a triar.
"""
import json

from app.agents.base import Agent
from app.agents.llm import ask

CATS = "accion_requerida | informativo | newsletter | probable_spam"


class InboxTriageAgent(Agent):
    name = "bandeja"
    descripcion = "Lee la bandeja de un usuario y clasifica cada correo (categoría + prioridad) con IA."

    async def run(self, ctx, dry_run: bool = True) -> dict:
        user = (ctx.params or {}).get("user", "").strip().lower()
        base = {"agent": self.name, "descripcion": self.descripcion, "actions": []}
        if not user or "@" not in user:
            return {**base, "summary": "Indica el buzón a triar (params user)", "items": []}

        from app.mail.clients.imap_client import get_imap_connection
        from app.mail.services.message_service import list_messages
        try:
            imap = await get_imap_connection(f"{user}*admin", ctx.settings.master_password)
        except Exception as e:
            return {**base, "summary": f"No se pudo abrir el buzón de {user}: {e}", "items": []}
        try:
            res = await list_messages(imap, "INBOX", 1, 15, "")
            msgs = (res or {}).get("messages", []) if res else []
        finally:
            try:
                await imap.logout()
            except Exception:
                pass

        if not msgs:
            return {**base, "summary": f"Bandeja de {user}: sin correos recientes", "items": []}

        listado = [
            f"{i}. De: {(m.get('from') or '')[:60]} | Asunto: {(m.get('subject') or '(sin asunto)')[:80]} | {(m.get('snippet') or '')[:90]}"
            for i, m in enumerate(msgs[:15])
        ]
        raw = await ask(
            "Clasifica cada correo. Devuelve SOLO un JSON array: "
            f"[{{\"i\":n,\"categoria\":\"{CATS}\",\"prioridad\":\"alta|media|baja\"}}]\n\n"
            + "\n".join(listado),
            system="Eres un asistente que tría bandejas de correo. Responde JSON válido y conciso.",
            max_tokens=700)
        cls = {}
        try:
            a, b = raw.find("["), raw.rfind("]")
            for c in json.loads(raw[a:b + 1]):
                cls[int(c.get("i"))] = c
        except Exception:
            pass

        counts = {"accion_requerida": 0, "informativo": 0, "newsletter": 0, "probable_spam": 0}
        items = []
        for i, m in enumerate(msgs[:15]):
            c = cls.get(i, {})
            cat = c.get("categoria", "informativo")
            counts[cat] = counts.get(cat, 0) + 1
            items.append({"from": m.get("from", ""), "subject": m.get("subject", "(sin asunto)"),
                          "categoria": cat, "prioridad": c.get("prioridad", "media")})
        return {**base, "summary": f"Bandeja de {user}: {len(items)} correos triados",
                "facts": counts, "items": items}
