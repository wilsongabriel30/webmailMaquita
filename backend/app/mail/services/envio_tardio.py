"""Envío que tarda más de lo que el cliente SMTP espera (05/11/2026).

Cuando Postfix tarda en confirmar el DATA (los milters analizan los adjuntos), el cliente
aiosmtplib agota su tiempo y el webmail devolvía un 500 «Timed out waiting for server
response» aunque el correo ya estuviera encolado: la persona lo reenviaba y salía dos veces.
Aquí se reconoce ese caso para responder con un aviso claro y un código que el cliente web
NO reencola automáticamente (409; un 502/503/504 lo mandaría a la cola de salida y lo
reenviaría solo).
"""

from __future__ import annotations

CODIGO = 409

MENSAJE = (
    "El servidor tardó demasiado en confirmar el envío, pero es muy probable que el correo SÍ haya "
    "salido. NO lo reenvíes todavía: espera un minuto y revisa la carpeta Enviados (o pregunta al "
    "destinatario). Si no aparece, vuelve a enviarlo."
)


def es_tiempo_agotado(exc: BaseException) -> bool:
    try:
        from aiosmtplib.errors import SMTPServerDisconnected, SMTPTimeoutError

        if isinstance(exc, (SMTPTimeoutError, SMTPServerDisconnected)):
            return True
    except Exception:  # noqa: BLE001
        pass
    texto = str(exc).lower()
    return "timed out" in texto or "timeout" in texto
