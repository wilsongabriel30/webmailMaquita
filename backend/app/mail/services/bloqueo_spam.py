"""«Marcar como spam» bloquea al remitente; «No es spam» lo desbloquea (05/11/2026).

Antes marcar spam solo entrenaba al filtro estadístico: el siguiente boletín del mismo remitente
podía volver a la bandeja (era lo que pasaba en Zimbra). Ahora la dirección del «From» pasa al
bloque de remitentes bloqueados del usuario y sale de su lista de confianza; al revés con
«No es spam». Las direcciones de los dominios propios no se bloquean: un correo que los suplanta
no debe servir para mandar a No deseado lo que escriben los compañeros.

Igual que el entrenamiento, es secundario: nunca lanza excepciones.
"""

import logging

from app import organizacion
from app.mail.services.confianza_auto import remitentes_de
from app.sieve import bloqueados_bloque, confianza_bloque
from app.sieve.router import (
    SCRIPT_NAME,
    sieve_connect,
    sieve_disconnect,
    sieve_getscript,
    sieve_putscript,
    sieve_setactive,
)

log = logging.getLogger(__name__)

# Dominios de la casa: ORG_DOMINIOS de /etc/maquita-mail/organizacion.env (app.organizacion).
DOMINIOS_PROPIOS = organizacion.dominios_propios()


def _ajenos(direcciones: list[str]) -> list[str]:
    return [d for d in direcciones if d.rsplit("@", 1)[-1] not in DOMINIOS_PROPIOS]


async def reescribir(
    username: str, password: str, bloquear: list[str], desbloquear: list[str]
) -> list[str]:
    """Aplica los cambios en un solo viaje a ManageSieve. Devuelve las direcciones bloqueadas nuevas."""
    reader, writer = await sieve_connect(username, password)
    try:
        actual = await sieve_getscript(reader, writer, SCRIPT_NAME)
        bloqueados = bloqueados_bloque.extraer(actual)
        confiables = confianza_bloque.extraer(actual)
        nuevos = [d for d in bloquear if d not in bloqueados][
            : max(0, bloqueados_bloque.MAXIMO - len(bloqueados))
        ]
        lista = sorted((set(bloqueados) | set(nuevos)) - set(desbloquear))
        confianza = sorted(set(confiables) - set(nuevos))
        if lista == bloqueados and confianza == confiables:
            return []
        script = confianza_bloque.aplicar(actual, confianza)
        script = bloqueados_bloque.aplicar(script, lista)
        await sieve_putscript(reader, writer, SCRIPT_NAME, script)
        await sieve_setactive(reader, writer, SCRIPT_NAME)
        return nuevos
    finally:
        await sieve_disconnect(writer)


async def bloquear_remitentes(
    username: str, password: str, mensajes_crudos
) -> list[str]:
    try:
        direcciones = _ajenos(remitentes_de(mensajes_crudos, username))
        if not direcciones:
            return []
        return await reescribir(username, password, direcciones, [])
    except Exception as e:
        log.warning("No se pudo bloquear remitentes de %s: %s", username, e)
        return []


async def desbloquear_remitentes(username: str, password: str, mensajes_crudos) -> None:
    try:
        direcciones = remitentes_de(mensajes_crudos, username)
        if direcciones:
            await reescribir(username, password, [], direcciones)
    except Exception as e:
        log.warning("No se pudo desbloquear remitentes de %s: %s", username, e)
