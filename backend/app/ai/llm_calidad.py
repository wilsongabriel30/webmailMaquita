"""Enrutamiento del «modelo de calidad» de la IA del correo (04/11/2026).

Las funciones de calidad (redactar/responder, resumir y «Conversa con tu correo») usan un modelo
más grande (p. ej. qwen2.5:14b en la Tesla P40) si se define IA_MODEL_CALIDAD; el resto de
funciones (asunto, autocompletado, clasificación, agentes) siguen con IA_MODEL.

- IA_MODEL_CALIDAD vacío -> desactivado: todo funciona exactamente como antes.
- IA_GPU_CALIDAD (por defecto «P40") -> GPU que se pide a la pasarela (`preferir_gpu`). La
  RTX 5070 comparte memoria con Whisper: el modelo grande NO debe ir allí.
- IA_TIMEOUT_CALIDAD (segundos) -> el 14B en frío tarda hasta ~90 s; caliente, 2-10 s.

Si la llamada de calidad falla o vuelve vacía, `_call_llm` reintenta UNA vez con la
configuración normal (respaldo automático), dentro del presupuesto que deja nginx (120 s).
"""

import time

# nginx corta /api/ a los 120 s: el intento de calidad más el respaldo deben caber antes.
PRESUPUESTO_TOTAL_S = 112.0
# Tiempo mínimo que se concede al respaldo aunque el intento de calidad haya agotado el suyo.
RESPALDO_MINIMO_S = 15.0


def config_calidad(ia: dict, settings) -> dict | None:
    """Copia de la config de IA apuntando al modelo de calidad, o None si está desactivado."""
    modelo = (getattr(settings, "ia_model_calidad", "") or "").strip()
    if not modelo:
        return None
    gpu = (getattr(settings, "ia_gpu_calidad", "") or "").strip() or "P40"
    timeout = float(getattr(settings, "ia_timeout_calidad", 0) or 95)
    timeout = min(timeout, PRESUPUESTO_TOTAL_S - RESPALDO_MINIMO_S)
    return {**ia, "model": modelo, "preferir_gpu": gpu, "timeout": timeout}


def config_respaldo(ia: dict, inicio: float) -> dict:
    """Config normal para el respaldo, con el tiempo que queda del presupuesto total."""
    restante = PRESUPUESTO_TOTAL_S - (time.monotonic() - inicio)
    normal = float(ia.get("timeout") or 60)
    return {**ia, "timeout": max(RESPALDO_MINIMO_S, min(normal, restante))}
