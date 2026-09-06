"""Reglas de severidad/acción a partir de las señales (determinista, sin IA).

Es la primera capa: rápida y explicable. La IA (triage) es una segunda opinión.
"""

LOW, MEDIUM, HIGH = "low", "medium", "high"


def evaluate(sig: dict) -> dict:
    """sig = {risky_high, dlp, safelink_bad, login_fail, score} -> dict de decisión."""
    reasons = []
    if sig.get("risky_high"):
        reasons.append(
            f"{sig['risky_high']} login(s) de riesgo alto (viaje imposible/geo)"
        )
    if sig.get("dlp"):
        reasons.append(f"{sig['dlp']} violación(es) DLP")
    if sig.get("safelink_bad"):
        reasons.append(f"{sig['safelink_bad']} clic(s) a enlaces peligrosos")
    if sig.get("login_fail"):
        reasons.append(f"{sig['login_fail']} fallos de login (fuerza bruta)")

    score = sig.get("score", 0)
    # señal fuerte de cuenta comprometida: riesgo alto + actividad de salida (DLP)
    if sig.get("risky_high") and sig.get("dlp"):
        return {
            "severity": HIGH,
            "action": "lock",
            "reasons": reasons,
            "rationale": "Login de riesgo alto + actividad de salida (DLP): patrón de cuenta comprometida.",
        }
    if score >= 8:
        return {
            "severity": HIGH,
            "action": "review",
            "reasons": reasons,
            "rationale": "Acumulación alta de señales de riesgo.",
        }
    if score >= 4:
        return {
            "severity": MEDIUM,
            "action": "review",
            "reasons": reasons,
            "rationale": "Señales de riesgo moderadas.",
        }
    return {
        "severity": LOW,
        "action": "monitor",
        "reasons": reasons,
        "rationale": "Señales bajas.",
    }
