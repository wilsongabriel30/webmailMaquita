"""Piezas comunes del módulo Dispositivos del panel: base de datos, auditoría y validaciones."""

import json
import re
from datetime import date

from fastapi import HTTPException, Request

_CONTROL = re.compile(r"[\x00-\x1f\x7f]")


def db(r: Request):
    return r.app.state.db


async def auditar(r: Request, admin: dict, accion: str, objetivo: str, detalles: dict | None = None):
    await r.app.state.db.execute(
        "INSERT INTO admin_audit (admin_id, admin_username, action, target, details, ip_address) "
        "VALUES ($1,$2,$3,$4,$5::jsonb,$6)",
        admin["id"], admin["username"], accion, objetivo,
        json.dumps(detalles, default=str) if detalles else None,
        r.headers.get("X-Real-IP", r.client.host if r.client else ""),
    )


def texto(valor, maximo: int) -> str | None:
    """Texto de una línea, sin caracteres de control; vacío → None."""
    if valor is None:
        return None
    v = _CONTROL.sub(" ", str(valor)).strip()[:maximo]
    return v or None


def imei_valido(imei: str) -> bool:
    """14-17 dígitos (lo que reportan los teléfonos, también los de doble SIM); si son exactamente
    15, se exige el dígito de control de Luhn para atrapar errores de tecleo."""
    imei = imei or ""
    if not re.fullmatch(r"\d{14,17}", imei):
        return False
    if len(imei) != 15:
        return True
    total = 0
    for i, c in enumerate(imei):
        n = int(c)
        if i % 2 == 1:
            n = n * 2 - 9 if n * 2 > 9 else n * 2
        total += n
    return total % 10 == 0


def fecha(valor) -> date | None:
    if not valor:
        return None
    try:
        return date.fromisoformat(str(valor)[:10])
    except ValueError:
        raise HTTPException(400, "Fecha inválida (use AAAA-MM-DD)")


def depreciacion(valor_compra, fecha_compra: date | None, vida_util_meses: int, hoy: date | None = None) -> dict | None:
    """Línea recta sin valor residual. Devuelve None si faltan datos."""
    if valor_compra is None or fecha_compra is None or not vida_util_meses:
        return None
    hoy = hoy or date.today()
    meses = max(0, (hoy.year - fecha_compra.year) * 12 + (hoy.month - fecha_compra.month))
    meses = min(meses, vida_util_meses)
    valor = float(valor_compra)
    depreciado = round(valor * meses / vida_util_meses, 2)
    return {
        "meses_transcurridos": meses, "vida_util_meses": vida_util_meses,
        "depreciacion_acumulada": depreciado, "valor_en_libros": round(valor - depreciado, 2),
        "totalmente_depreciado": meses >= vida_util_meses,
    }
