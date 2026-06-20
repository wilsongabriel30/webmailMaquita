"""Triage asistido por IA (neurona estratégica, Qwen vía Ollama).

Da una SEGUNDA OPINIÓN sobre un incidente: resumen + recomendación + confianza.
Best-effort: si la IA no responde, el incidente sigue con la decisión del playbook.
"""
import json
import logging

logger = logging.getLogger("air.triage")

_SYSTEM = (
    "Eres un analista SOC. Recibes señales de seguridad de un buzón de correo. "
    "Responde SOLO un JSON: {\"resumen\":\"...\",\"recomendacion\":\"lock|review|monitor\","
    "\"confianza\":0-100}. Sé conciso y prudente: 'lock' solo ante evidencia clara "
    "de cuenta comprometida (login de riesgo alto + envío anómalo/DLP)."
)


async def assess(username: str, signals: dict, playbook: dict) -> dict:
    try:
        from app.ai.router import _call_llm
    except Exception:
        return {}
    prompt = (f"Buzón: {username}\nSeñales: {json.dumps(signals, ensure_ascii=False)}\n"
              f"Regla determinista: {playbook['severity']} -> {playbook['action']} "
              f"({playbook['rationale']})\nEvalúa y responde el JSON.")
    try:
        raw = await _call_llm(prompt, system=_SYSTEM, temperature=0.1, max_tokens=300)
        i, j = raw.find("{"), raw.rfind("}")
        if i >= 0 and j > i:
            data = json.loads(raw[i:j + 1])
            return {"resumen": str(data.get("resumen", ""))[:500],
                    "recomendacion": data.get("recomendacion", ""),
                    "confianza": int(data.get("confianza", 0) or 0)}
    except Exception as e:
        logger.warning("triage IA falló para %s: %s", username, e)
    return {}
