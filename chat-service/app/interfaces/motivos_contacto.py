# -*- coding: utf-8 -*-
"""Decir la verdad cuando no se puede empezar una conversación (aviso de Andes, 08/09/2026).

El servidor respondía siempre «No puedes chatear con esta persona», también cuando el motivo
real era que **no pudo comprobar nada** (la base sin responder). Rechazar es correcto —fallo
cerrado—, pero el mensaje apuntaba a un bloqueo entre personas que no existe, y manda a soporte
a buscar donde no hay nada.
"""

_MENSAJES = {
    "mismo_usuario": "No puedes empezar una conversación contigo.",
    "destino_invalido": "No se reconoce a esa persona.",
    "otra_organizacion": "Esa persona pertenece a otra organización.",
    "bloqueo": "No puedes chatear con esta persona.",
    "tenant_no_consultable": ("No se pudo comprobar si puedes escribirle; vuelve a intentarlo "
                              "en un momento."),
    "sin_conversacion": "No compartís ninguna conversación.",
    "bloqueo_no_consultable": ("No se pudo comprobar si puedes escribirle; vuelve a intentarlo "
                               "en un momento."),
}

_POR_DEFECTO = "No se pudo empezar la conversación."


def mensaje(motivo: str) -> str:
    """Texto para la persona, según el motivo que dio la comprobación."""
    return _MENSAJES.get((motivo or "").strip(), _POR_DEFECTO)


def es_fallo_nuestro(motivo: str) -> bool:
    """True si el rechazo viene de que el servidor no pudo comprobar, no de una regla.

    Sirve para registrar distinto y para que el cliente sepa que reintentar tiene sentido.
    """
    return (motivo or "").strip() in ("tenant_no_consultable", "bloqueo_no_consultable")
