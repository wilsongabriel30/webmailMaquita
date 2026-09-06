"""Copiloto de Seguridad — Q&A de seguridad en lenguaje natural, grounded en datos reales."""

import json

from app.copiloto.context import gather

_SYSTEM = (
    "Eres Copiloto de Seguridad de Fundación Maquita, un analista SOC. Responde la "
    "pregunta del administrador USANDO SOLO los datos de seguridad provistos "
    "(no inventes nada; si los datos no alcanzan, dilo claramente). Español, "
    "conciso y accionable: explica qué pasa y, si aplica, una acción sugerida."
)


async def ask(db, question: str, days: int = 7) -> dict:
    ctx = await gather(db, days)
    try:
        from app.ai.router import _call_llm
    except Exception:
        return {"answer": "IA no disponible.", "context": ctx}
    prompt = (
        f"DATOS DE SEGURIDAD (últimos {days} días):\n"
        f"{json.dumps(ctx, ensure_ascii=False, default=str)}\n\n"
        f"PREGUNTA DEL ADMINISTRADOR: {question}\n\n"
        "Responde con base en esos datos."
    )
    answer = await _call_llm(prompt, system=_SYSTEM, temperature=0.1, max_tokens=600)
    return {"answer": answer or "(sin respuesta)", "context": ctx}
