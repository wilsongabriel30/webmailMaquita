"""Plazo máximo para recuperar un correo enviado (11/11/2026).

Recuperar un correo lo quita del buzón del destinatario aunque ya lo haya leído. Sin límite de
tiempo eso permitía retirar correos de hace semanas (se probó con uno del 30/10), es decir, hacer
desaparecer constancias: instrucciones, aprobaciones, acuerdos. La recuperación es para corregir un
error recién cometido, no para reescribir lo ya comunicado.

Regla: solo se puede recuperar durante `RECALL_MAX_MINUTOS` (60 por defecto) desde que el correo
llegó al buzón del destinatario. La fecha la pone el servidor al entregar (`date.received`), no
el remitente, así que no se puede alterar desde el cliente. Si la fecha no se puede comprobar,
no se recupera.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from app.config import get_settings

ESTADO_FUERA_DE_PLAZO = "fuera_de_plazo"
MINUTOS_POR_DEFECTO = 60
_FORMATO_DOVEADM = "%Y-%m-%d %H:%M:%S"


def minutos_maximos() -> int:
    """Minutos durante los que se puede recuperar un correo (mínimo 1)."""
    try:
        minutos = int(
            getattr(get_settings(), "recall_max_minutos", MINUTOS_POR_DEFECTO)
        )
    except (TypeError, ValueError):
        minutos = MINUTOS_POR_DEFECTO
    return max(1, minutos)


def texto_plazo(minutos: int | None = None) -> str:
    """«1 hora», «2 horas», «30 minutos»."""
    m = minutos if minutos is not None else minutos_maximos()
    if m % 60 == 0:
        horas = m // 60
        return "1 hora" if horas == 1 else f"{horas} horas"
    return "1 minuto" if m == 1 else f"{m} minutos"


def interpretar_fecha(texto: str | None) -> datetime | None:
    """Fecha de `doveadm fetch date.received` («2026-11-11 08:15:02», hora del servidor)."""
    try:
        return datetime.strptime((texto or "").strip()[:19], _FORMATO_DOVEADM)
    except ValueError:
        return None


def mas_antigua(actual: datetime | None, nueva: datetime | None) -> datetime | None:
    """Con varias copias del mismo correo manda la primera que llegó."""
    if actual is None or nueva is None:
        return actual or nueva
    return min(actual, nueva)


def vencido(recibido: datetime | None, ahora: datetime | None = None) -> bool:
    """¿Ya pasó el plazo? Sin fecha comprobable se considera vencido."""
    if recibido is None:
        return True
    return (ahora or datetime.now()) - recibido > timedelta(minutes=minutos_maximos())


def motivo(recibido: datetime | None) -> str:
    """Explicación para la persona que intenta recuperar fuera de plazo."""
    plazo = texto_plazo()
    if recibido is None:
        return (
            "No se pudo comprobar cuándo se entregó este correo, así que no se puede recuperar. "
            f"Solo se recuperan correos durante {plazo} después del envío."
        )
    return (
        f"Fuera de plazo: se entregó el {recibido:%d/%m/%Y} a las {recibido:%H:%M}. "
        f"Un correo solo se puede recuperar durante {plazo} después del envío."
    )
