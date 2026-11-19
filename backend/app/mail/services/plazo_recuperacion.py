"""Plazo máximo para recuperar un correo enviado (11/11/2026).

Recuperar un correo lo quita del buzón del destinatario aunque ya lo haya leído. Sin límite de
tiempo eso permitía retirar correos de hace semanas (se probó con uno del 30/10), es decir, hacer
desaparecer constancias: instrucciones, aprobaciones, acuerdos. La recuperación es para corregir un
error recién cometido, no para reescribir lo ya comunicado.

Regla: solo se puede recuperar durante `RECALL_MAX_MINUTOS` (60 por defecto) desde que el correo
llegó al buzón del destinatario.

Ajuste del 19/11/2026 (Coordinación de TI): ese plazo vale para los correos que el destinatario
YA LEYÓ. Mientras siga sin leer no hay constancia que proteger, así que se puede recuperar en
cualquier momento (como el Outlook clásico): un correo enviado por error un viernes se puede
retirar el lunes si nadie lo abrió. Ver `fuera_de_plazo`.

Los dos plazos se fijan desde el panel de administración (Seguridad → «Plazo para recuperar
correos», tabla `recuperacion_plazo_politica`) y rigen en la siguiente recuperación, sin
reiniciar. Mientras no se guarde nada desde el panel vale lo anterior. Ver `Regla`. La fecha la pone el servidor al entregar (`date.received`), no
el remitente, así que no se puede alterar desde el cliente. Si la fecha no se puede comprobar,
no se recupera.
"""

from __future__ import annotations

from dataclasses import dataclass
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


@dataclass(frozen=True)
class Regla:
    """Plazos vigentes, en minutos.

    `minutos_leidos`: 0 = un correo ya leído no se recupera. `minutos_sin_leer`: 0 = sin límite.
    """

    minutos_leidos: int
    minutos_sin_leer: int = 0

    def minutos_externos(self) -> int:
        """Plazo para destinatarios de fuera, de los que no se sabe si leyeron: el de los leídos
        (si lo leído no se recupera, el del archivo de configuración, para poder pedir la retirada).
        """
        return self.minutos_leidos if self.minutos_leidos > 0 else minutos_maximos()


def regla_por_defecto() -> Regla:
    """Lo que rige sin nada guardado desde el panel: el plazo del `.env` para lo leído, sin límite lo demás."""
    return Regla(minutos_maximos(), 0)


async def regla_vigente(db) -> Regla:
    """Lo guardado desde el panel manda; si no hay nada (o la tabla aún no existe), la regla por defecto."""
    try:
        fila = await db.fetchrow(
            "SELECT minutos_leidos, minutos_sin_leer FROM recuperacion_plazo_politica WHERE id = 1"
        )
        if fila is None:
            return regla_por_defecto()
        return Regla(
            max(0, int(fila["minutos_leidos"])), max(0, int(fila["minutos_sin_leer"]))
        )
    except Exception:
        return regla_por_defecto()


def vencido(
    recibido: datetime | None, ahora: datetime | None = None, minutos: int | None = None
) -> bool:
    """¿Ya pasó el plazo (`minutos`, o el del archivo de configuración)? Sin fecha comprobable, sí."""
    if recibido is None:
        return True
    limite = minutos if minutos is not None else minutos_maximos()
    return (ahora or datetime.now()) - recibido > timedelta(minutes=max(1, limite))


def fuera_de_plazo(
    recibido: datetime | None,
    leido: bool | None,
    ahora: datetime | None = None,
    regla: Regla | None = None,
) -> bool:
    """¿Ya no se puede recuperar del buzón de un destinatario local?

    Sin leer (`leido` es False): vale el plazo de los no leídos, que por defecto no tiene límite.
    Leído, o sin poder saber si se leyó: vale el plazo de los leídos (0 = no se recupera) y sin
    fecha comprobable no se recupera.
    """
    regla = regla or regla_por_defecto()
    if leido is False:
        if regla.minutos_sin_leer <= 0:
            return False
        return vencido(recibido, ahora, regla.minutos_sin_leer)
    if regla.minutos_leidos <= 0:
        return True
    return vencido(recibido, ahora, regla.minutos_leidos)


def motivo(
    recibido: datetime | None, regla: Regla | None = None, leido: bool | None = None
) -> str:
    """Explicación para la persona que intenta recuperar y ya no puede."""
    regla = regla or regla_por_defecto()
    if leido is not False and regla.minutos_leidos <= 0 and leido is not None:
        return (
            "El destinatario ya lo leyó: con la regla vigente, un correo ya leído no se puede "
            "recuperar."
        )
    if leido is False:
        plazo = texto_plazo(regla.minutos_sin_leer)
        regla_texto = (
            f"Un correo sin leer se puede recuperar durante {plazo} después del envío."
        )
    else:
        plazo = texto_plazo(regla.minutos_externos())
        sin_leer = (
            "mientras nadie lo haya leído se puede recuperar en cualquier momento."
            if regla.minutos_sin_leer <= 0
            else f"sin leer, durante {texto_plazo(regla.minutos_sin_leer)}."
        )
        regla_texto = (
            f"Un correo ya leído solo se puede recuperar durante {plazo} después del envío; "
            + sin_leer
        )
    if recibido is None:
        return (
            "No se pudo comprobar cuándo se entregó este correo, así que no se puede recuperar. "
            + regla_texto
        )
    return (
        f"Fuera de plazo: se entregó el {recibido:%d/%m/%Y} a las {recibido:%H:%M}. "
        + regla_texto
    )
