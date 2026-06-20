"""AIR — Automated Investigation & Response (modular, IA-asistido).

Correlaciona señales de riesgo, hace triage con la IA local (Qwen) y, si se
habilita, contiene cuentas comprometidas. Seguro por defecto: detecta+recomienda.
"""
from app.air.engine import run_cycle  # noqa: F401
