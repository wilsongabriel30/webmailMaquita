"""Lista de dominios de confianza de la recuperación entre servidores: validación y lectura del .env.

Funciones puras (sin base de datos) para poder probarlas.
"""

import re
from pathlib import Path

MAX_DOMINIOS = 200
_DOMINIO = re.compile(
    r"^(?=.{1,253}$)([a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}$"
)
ENV_RETIRAR = "RECALL_FEDERADO_RETIRAR_LEIDOS"
ENV_DOMINIOS = "RECALL_FEDERADO_DOMINIOS_CONFIANZA"


def limpiar(dominio: str) -> str:
    return (dominio or "").strip().lower().lstrip("@").rstrip(".")


def normalizar(dominios: list[str]) -> tuple[list[str], list[str]]:
    """Devuelve (válidos sin repetir y en orden, rechazados tal como se escribieron)."""
    validos: list[str] = []
    rechazados: list[str] = []
    for crudo in dominios or []:
        d = limpiar(crudo)
        if not d:
            continue
        if not _DOMINIO.match(d):
            rechazados.append(str(crudo).strip())
        elif d not in validos:
            validos.append(d)
    return validos, rechazados


def del_archivo(texto_env: str) -> dict:
    """Lo que dice el .env del correo (lo que rige mientras no se guarde nada desde el panel)."""
    valores: dict[str, str] = {}
    for linea in (texto_env or "").splitlines():
        linea = linea.strip()
        if not linea or linea.startswith("#") or "=" not in linea:
            continue
        clave, valor = linea.split("=", 1)
        valores[clave.strip()] = valor.strip().strip('"').strip("'")
    retirar = valores.get(ENV_RETIRAR, "").lower() in ("1", "true", "yes", "on", "si", "sí")
    dominios, _ = normalizar(valores.get(ENV_DOMINIOS, "").split(","))
    return {"retirar_leidos": retirar, "dominios_confianza": dominios}


def leer_env_del_correo() -> dict:
    """Lee backend/.env de la instalación; si no se puede, los valores por defecto."""
    ruta = Path(__file__).resolve().parents[4] / "backend" / ".env"
    try:
        return del_archivo(ruta.read_text(encoding="utf-8"))
    except Exception:
        return del_archivo("")
