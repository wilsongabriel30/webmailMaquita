"""Plazo para recuperar correos: validación y lectura del valor del archivo de configuración."""

from pathlib import Path

ENV_MINUTOS = "RECALL_MAX_MINUTOS"
POR_DEFECTO_LEIDOS = 60
MAXIMO = 43200  # 30 días


def validar(minutos_leidos: int, minutos_sin_leer: int) -> str | None:
    """Mensaje de error para la persona, o None si los dos plazos son válidos."""
    for nombre, valor in (
        ("ya leídos", minutos_leidos),
        ("sin leer", minutos_sin_leer),
    ):
        if valor < 0 or valor > MAXIMO:
            return f"El plazo de los correos {nombre} debe estar entre 0 y {MAXIMO} minutos (30 días)."
    if minutos_sin_leer and minutos_leidos > minutos_sin_leer:
        return "El plazo de los correos ya leídos no puede ser mayor que el de los correos sin leer."
    return None


def del_archivo(texto_env: str) -> dict:
    """Lo que rige mientras no se guarde nada desde el panel."""
    minutos = POR_DEFECTO_LEIDOS
    for linea in (texto_env or "").splitlines():
        linea = linea.strip()
        if linea.startswith("#") or "=" not in linea:
            continue
        clave, valor = linea.split("=", 1)
        if clave.strip() == ENV_MINUTOS:
            try:
                minutos = max(1, int(valor.strip().strip('"').strip("'")))
            except ValueError:
                minutos = POR_DEFECTO_LEIDOS
    return {"minutos_leidos": minutos, "minutos_sin_leer": 0}


def leer_env_del_correo() -> dict:
    """Lee backend/.env de la instalación; si no se puede, los valores por defecto."""
    ruta = Path(__file__).resolve().parents[4] / "backend" / ".env"
    try:
        return del_archivo(ruta.read_text(encoding="utf-8"))
    except Exception:
        return del_archivo("")
