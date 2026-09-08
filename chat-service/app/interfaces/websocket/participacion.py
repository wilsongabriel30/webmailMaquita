# -*- coding: utf-8 -*-
"""¿Puede esta persona escribir en esta conversación? (N-29)

El chat comprueba la participación preguntando al servicio, que trabaja sobre su propia sesión
y su caché. Cuando alguien empieza una conversación nueva y escribe en el acto —que es lo que
hace la interfaz: crear y enviar seguido— esa comprobación llegaba a decir que no, y el primer
mensaje se rechazaba con «No tienes acceso a esta conversacion». Se perdía justo el mensaje que
estrena la conversación, y quedaba una conversación vacía.

Ocurrió el 08/09/2026 a las 11:51:25: la conversación se creó en el mismo milisegundo del envío.

La regla no se relaja: si el servicio no lo ve, se confirma contra la base, que es la autoridad.
Solo se deja pasar a quien la base reconoce como participante activo.
"""


def es_participante(conversacion_id, usuario_id, ver_conversacion, participa_en_base,
                    registrar=None):
    """True si el servicio ve la conversación o si la base confirma la participación.

    `ver_conversacion(conversacion_id, usuario_id)` es la vista del servicio (con su caché).
    `participa_en_base(conversacion_id, usuario_id)` consulta la tabla de participantes.
    Ninguna de las dos puede tumbar la comprobación: si revientan, se sigue con la otra, y si
    fallan las dos la respuesta es «no».
    """
    try:
        if ver_conversacion(conversacion_id, usuario_id) is not None:
            return True
    except Exception as e:
        if registrar:
            registrar("servicio", e)

    try:
        confirmado = bool(participa_en_base(conversacion_id, usuario_id))
    except Exception as e:
        if registrar:
            registrar("base", e)
        return False

    if confirmado and registrar:
        registrar("recien_creada", None)
    return confirmado
