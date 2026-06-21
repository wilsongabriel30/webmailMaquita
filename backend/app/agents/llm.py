"""Acceso a la neurona (Qwen vía el gateway de IA). Best-effort."""


async def ask(prompt: str, system: str = "", temperature: float = 0.2,
              max_tokens: int = 400) -> str:
    try:
        from app.ai.router import _call_llm
        return await _call_llm(prompt, system=system, temperature=temperature,
                               max_tokens=max_tokens)
    except Exception:
        return ""
