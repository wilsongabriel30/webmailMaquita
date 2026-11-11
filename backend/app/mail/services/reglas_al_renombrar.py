"""Las reglas siguen a la carpeta cuando se renombra o se mueve (10/11/2026).

Caso real: una persona renombró «000_UAFE» como «UAFE» y su regla seguía diciendo
`fileinto :create "INBOX.000_UAFE"`, así que la carpeta vieja volvía a aparecer con cada correo.
Aquí se reescriben, en el script Sieve de la persona, las acciones `fileinto` que apuntan a la
carpeta renombrada o a cualquiera de sus hijas, y se vuelve a activar el script.
"""

from __future__ import annotations

import logging
import re

from app.sieve.escapado import desescapar, escapar

logger = logging.getLogger("maquita.webmail.reglas_al_renombrar")

_FILEINTO = re.compile(r'(fileinto\b(?:\s+:\w+)*\s+)"((?:[^"\\]|\\.)*)"')


def reescribir(script: str, viejo: str, nuevo: str) -> tuple[str, int]:
    """Devuelve (script, cuántas acciones cambiaron). «viejo.hija» pasa a «nuevo.hija»."""
    cambios = 0

    def _sustituir(m: re.Match) -> str:
        nonlocal cambios
        carpeta = desescapar(m.group(2))
        if carpeta == viejo:
            destino = nuevo
        elif carpeta.startswith(viejo + "."):
            destino = nuevo + carpeta[len(viejo) :]
        else:
            return m.group(0)
        cambios += 1
        return m.group(1) + '"' + escapar(destino) + '"'

    return _FILEINTO.sub(_sustituir, script), cambios


async def actualizar(username: str, password: str, viejo: str, nuevo: str) -> int:
    """Reescribe el script activo de la persona. Nunca lanza: el renombrado ya se hizo."""
    try:
        from app.sieve.router import (
            SCRIPT_NAME,
            sieve_connect,
            sieve_disconnect,
            sieve_getscript,
            sieve_putscript,
            sieve_setactive,
        )

        reader, writer = await sieve_connect(username, password)
        try:
            script = await sieve_getscript(reader, writer, SCRIPT_NAME)
            if not script:
                return 0
            nuevo_script, cambios = reescribir(script, viejo, nuevo)
            if cambios:
                await sieve_putscript(reader, writer, SCRIPT_NAME, nuevo_script)
                await sieve_setactive(reader, writer, SCRIPT_NAME)
                logger.info(
                    "reglas de %s: %d acción(es) pasan de %r a %r",
                    username,
                    cambios,
                    viejo,
                    nuevo,
                )
            return cambios
        finally:
            await sieve_disconnect(writer)
    except Exception as exc:
        logger.warning(
            "reglas de %s al renombrar %r → %r: %s", username, viejo, nuevo, exc
        )
        return 0
