"""Configuración del portal de administradores de dominio. Todo llega del entorno."""

import os


def _obligatoria(nombre: str) -> str:
    valor = os.getenv(nombre, "")
    if not valor:
        raise RuntimeError(f"Falta {nombre} en el entorno del portal de dominio")
    return valor


DB_HOST = os.getenv("PD_DB_HOST", "127.0.0.1")
DB_PORT = int(os.getenv("PD_DB_PORT", "5432"))
DB_NAME = os.getenv("PD_DB_NAME", "maildb")
DB_USER = os.getenv("PD_DB_USER", "panel_dominio")
DB_PASS = _obligatoria("PD_DB_PASS")
# «require» si la base está en otro equipo.
DB_SSL = "require" if os.getenv("PD_DB_SSL", "").lower() in ("1", "si", "require") else False

HORAS_SESION = int(os.getenv("PD_HORAS_SESION", "8"))
INTENTOS_MAXIMOS = 5
MINUTOS_BLOQUEO = 15
