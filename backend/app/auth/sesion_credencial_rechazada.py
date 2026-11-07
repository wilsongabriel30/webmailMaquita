"""Cierre de la sesión cuya contraseña guardada ya no vale en el servidor de correo.

Caso real (05/11/2026): la contraseña del buzón cambió fuera del webmail (a las 08:51)
y una pestaña abierta desde la noche anterior siguió viva porque el refresco del token
no comprueba la contraseña. Los listados funcionaban (el pool de IMAP compartía
conexiones ya abiertas) pero cada adjunto abría una conexión nueva y Dovecot la
rechazaba: 337 fallos de autenticación en un día y un 401 crudo en pantalla.

Aquí, ante un rechazo de AUTENTICACIÓN (no ante un límite de conexiones ni una caída),
se cierra SOLO esa sesión: el siguiente refresco falla y la interfaz vuelve a la
pantalla de inicio de sesión. Las demás sesiones del usuario (otra pestaña, la
aplicación de escritorio) con la contraseña vigente siguen funcionando.
"""

import logging

from fastapi import Request

from app.auth.sesiones import cerrar_sid

log = logging.getLogger("maquita.webmail.sesion")


async def cerrar_si_credencial_rechazada(request: Request, exc: Exception) -> bool:
    """Cierra la sesión de la petición si `exc` es un rechazo de autenticación IMAP.
    Devuelve True si se cerró. Nunca lanza: un fallo aquí no debe tapar el 401."""
    if not getattr(exc, "es_autenticacion", False):
        return False
    sid = getattr(request.state, "sid", None)
    username = getattr(request.state, "username", None)
    if not sid or not username:
        return False
    try:
        await cerrar_sid(
            request.app.state.db_pool,
            request.app.state.redis,
            username,
            sid,
            "contrasena_rechazada_por_imap",
        )
        log.warning(
            "SESION_CERRADA_CREDENCIAL user=%s sid=%s ruta=%s respuesta=%r",
            username,
            sid,
            request.url.path,
            getattr(exc, "respuesta", ""),
        )
        return True
    except Exception as e:  # pragma: no cover - defensa
        log.error("No se pudo cerrar la sesión %s de %s: %s", sid, username, e)
        return False
