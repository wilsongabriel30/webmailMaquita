"""Configuración de los tableros (tabla seg_config): valores por omisión, límites y lectura."""

from __future__ import annotations

from . import zona

# campo → (por omisión, mínimo, máximo) para los enteros
ENTEROS = {
    "retencion_dias": (400, 30, 3650),
    "retencion_detalle_dias": (90, 7, 3650),
    "umbral_fallos": (5, 2, 1000),
    "ventana_fallos_min": (15, 1, 240),
    "umbral_cuentas_ip": (10, 2, 10000),
    "hora_min_historial": (50, 5, 100000),
    "hora_porcentaje_max": (1, 1, 50),
    "avisos_por_hora": (6, 0, 100),
    "escalar_tras_horas": (4, 0, 168),
}
BOOLEANOS = {
    "regla_pais_nuevo": True,
    "regla_fallos_y_exito": True,
    "regla_hora_inusual": True,
    "regla_muchas_cuentas_ip": True,
    "avisos": True,
}
SEVERIDADES = ("baja", "media", "alta")
CAMPOS = tuple(ENTEROS) + tuple(BOOLEANOS) + ("zona_horaria", "aviso_severidad_minima")


def por_omision() -> dict:
    d = {k: v[0] for k, v in ENTEROS.items()}
    d.update(BOOLEANOS)
    d.update({"zona_horaria": "", "aviso_severidad_minima": "alta"})
    return d


def validar(datos: dict) -> dict:
    """Devuelve la configuración completa y saneada; ValueError con un motivo legible si algo no vale."""
    salida = por_omision()
    for k, (_, minimo, maximo) in ENTEROS.items():
        if k in datos and datos[k] is not None:
            try:
                v = int(datos[k])
            except (TypeError, ValueError):
                raise ValueError(f"{k}: debe ser un número entero")
            if not minimo <= v <= maximo:
                raise ValueError(f"{k}: debe estar entre {minimo} y {maximo}")
            salida[k] = v
    for k in BOOLEANOS:
        if k in datos and datos[k] is not None:
            salida[k] = bool(datos[k])
    z = str(datos.get("zona_horaria") or "").strip()
    if z and not zona.valida(z):
        raise ValueError("zona_horaria: no es una zona válida (p. ej. America/Guayaquil)")
    salida["zona_horaria"] = z
    s = str(datos.get("aviso_severidad_minima") or "alta")
    if s not in SEVERIDADES:
        raise ValueError("aviso_severidad_minima: baja, media o alta")
    salida["aviso_severidad_minima"] = s
    if salida["retencion_detalle_dias"] > salida["retencion_dias"]:
        raise ValueError("retencion_detalle_dias no puede ser mayor que retencion_dias")
    return salida


async def leer(db) -> dict:
    try:
        fila = await db.fetchrow("SELECT * FROM seg_config WHERE id = 1")
    except Exception:
        fila = None  # migración sin aplicar: valores por omisión
    datos = por_omision()
    if fila:
        for k in CAMPOS:
            if k in fila.keys() and fila[k] is not None:
                datos[k] = fila[k]
    return datos


async def guardar(db, datos: dict, usuario: str) -> None:
    campos = list(CAMPOS)
    asignaciones = ", ".join(f"{c} = ${i + 1}" for i, c in enumerate(campos))
    n = len(campos)
    await db.execute("INSERT INTO seg_config (id) VALUES (1) ON CONFLICT (id) DO NOTHING")
    await db.execute(
        f"UPDATE seg_config SET {asignaciones}, actualizado_por = ${n + 1}, actualizado_en = now() WHERE id = 1",
        *[datos[c] for c in campos], usuario[:255])
