"""Aviso de correo nuevo en una carpeta distinta de INBOX (10/11/2026).

El sondeo de carpetas (`sondeo_carpetas.py`) publicaba `new_mail` solo al navegador abierto; la app de
escritorio y el push web (con la pestaña cerrada o en segundo plano) solo se avisaban desde INBOX, así
que un correo que una regla archiva en «001 Maria Jesus» no sonaba en ninguna parte si la persona no
tenía el webmail delante. Aquí se manda lo mismo que para INBOX, diciendo en qué carpeta cayó.
"""

from __future__ import annotations

import logging

from app.websocket.resumen_correo_nuevo import textos_aviso

logger = logging.getLogger("maquita.webmail.avisos_subcarpeta")


def nombre_visible(carpeta: str) -> str:
    """«INBOX.2_ Financiero.Contabilidad» → «2_ Financiero / Contabilidad» (lo que ve la persona)."""
    partes = [p for p in carpeta.split(".") if p]
    if partes and partes[0].upper() == "INBOX":
        partes = partes[1:]
    return " / ".join(partes) or carpeta


async def avisar(
    db,
    usuario: str,
    carpeta: str,
    nuevos: int,
    sin_leer: int,
    uid: int | None,
    resumen: dict | None,
) -> None:
    """Avisa a la app de escritorio y por push. Nunca lanza."""
    try:
        from app.websocket.router import aviso_correo_al_canal

        await aviso_correo_al_canal(
            usuario, nuevos, sin_leer, uid, db, resumen=resumen, carpeta=carpeta
        )
    except Exception as exc:
        logger.debug("aviso al canal por %s de %s: %s", carpeta, usuario, exc)
    try:
        from app.push import service as _push

        titulo, texto = textos_aviso(nuevos, resumen)
        url = "/webmail/?folder=%s" % carpeta + ("&uid=%d" % uid if uid else "")
        await _push.enviar_a_usuario(
            db, usuario, titulo, "En «%s»: %s" % (nombre_visible(carpeta), texto), url
        )
    except Exception as exc:
        logger.debug("push por %s de %s: %s", carpeta, usuario, exc)
