"""
Entrenamiento del filtro antispam a partir de los reportes de los usuarios.

QUÉ RESUELVE
------------
Cuando un usuario marcaba un correo como spam, el sistema lo movía a Junk y
dejaba constancia en la base de datos... pero **el filtro no aprendía nada**:
el registro se guarda por `message_uid`, es decir, por ese mensaje concreto.
Correos idénticos del mismo remitente seguían llegando a la bandeja.

Este módulo cierra ese hueco: entrega el mensaje a **rspamd**, que sí tiene
clasificador bayesiano activo (con más de 13.000 mensajes aprendidos), para
que a partir de entonces reconozca los correos parecidos y los filtre solo.

CÓMO
----
`rspamc learn_spam` recibe el mensaje completo por la entrada estándar.
Es el mismo mecanismo que ya usa el sistema para su aprendizaje.

NOTA SOBRE LA VERIFICACIÓN
--------------------------
El contador de `rspamc stat` **se actualiza con retardo** (lee de Redis
periódicamente). Que no suba de inmediato NO significa que no haya aprendido:
lo fiable es el `success = true` de la respuesta. Comprobado el 2026-08-25.

PRINCIPIO
---------
El entrenamiento es **secundario**: si falla, no debe romper la acción
principal del usuario (mover el correo a Junk). Por eso nunca lanza
excepciones y siempre devuelve un booleano.

Doc: webmail/desenvoltura-enlaces-rastreo-20260824.md
"""

import asyncio
import logging

log = logging.getLogger(__name__)

RSPAMC = "/usr/bin/rspamc"
TIEMPO_MAXIMO = 15  # segundos


async def _entrenar(mensaje_crudo: bytes, accion: str) -> bool:
    """Ejecuta `rspamc <accion>` pasándole el mensaje por stdin."""
    if not mensaje_crudo:
        return False
    try:
        proc = await asyncio.create_subprocess_exec(
            RSPAMC, accion,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        salida, _ = await asyncio.wait_for(
            proc.communicate(input=mensaje_crudo), timeout=TIEMPO_MAXIMO
        )
        texto = (salida or b"").decode("utf-8", errors="ignore")
        # rspamd responde "success = true;" cuando incorpora el mensaje.
        # Si el mensaje ya estaba aprendido responde un error de duplicado,
        # que no es un fallo real: el objetivo ya está cumplido.
        if "success = true" in texto:
            return True
        if "already learned" in texto.lower():
            return True
        log.warning("rspamc %s no confirmo el aprendizaje: %s", accion, texto[:200])
        return False
    except asyncio.TimeoutError:
        log.warning("rspamc %s excedio el tiempo maximo", accion)
        return False
    except Exception as e:                      # noqa: BLE001
        # Nunca debe romper la accion principal del usuario.
        log.warning("rspamc %s fallo: %s", accion, e)
        return False


async def aprender_spam(mensaje_crudo: bytes) -> bool:
    """El usuario marcó el correo como SPAM: el filtro debe aprenderlo."""
    return await _entrenar(mensaje_crudo, "learn_spam")


async def aprender_no_spam(mensaje_crudo: bytes) -> bool:
    """El usuario marcó el correo como legítimo: corrige un falso positivo."""
    return await _entrenar(mensaje_crudo, "learn_ham")
