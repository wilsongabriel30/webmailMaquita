# -*- coding: utf-8 -*-
"""Aviso de mensaje nuevo a la PERSONA, no solo a la conversación abierta (N-28).

Hasta ahora un mensaje nuevo se emitía a la sala `conversation_<id>`, así que solo se enteraba
quien ya tenía esa conversación abierta. Por eso el aviso sonaba entre dos ventanas del Drive
con el chat desplegado, y no sonaba nada al escribir desde Raíces al Drive o al revés: ninguna
de las dos páginas estaba dentro de esa sala.

Aquí se emite además un `aviso_chat` a la sala personal de cada participante (`user_<id>`), a
la que toda ventana de esa persona se une nada más conectarse. Es un evento NUEVO: ningún
cliente anterior lo escucha, así que no cambia nada de lo que ya funcionaba.

El aviso lleva lo justo para pintar la notificación: quién escribe, en qué conversación y un
resumen corto. El contenido completo del mensaje viaja por la sala de la conversación, como
siempre, y nunca se escribe en el registro (M-07).
"""

RESUMEN_MAX = 140


def destinatarios(participantes, remitente_id):
    """A quién hay que avisar: participantes activos, sin silenciar, menos quien escribe.

    `participantes` es una lista de diccionarios con `user_id`, `is_active` e `is_muted`.
    """
    salida = []
    for p in participantes or []:
        uid = p.get("user_id")
        if uid is None:
            continue
        if p.get("is_active") is False:
            continue
        if p.get("is_muted"):
            continue
        if remitente_id is not None and str(uid) == str(remitente_id):
            continue
        if uid not in salida:
            salida.append(uid)
    return salida


def remitente_de(mensaje_data):
    """El id de quien escribe, venga con el nombre que venga según el camino de envío."""
    d = mensaje_data or {}
    remitente = d.get("remitente") if isinstance(d.get("remitente"), dict) else {}
    return d.get("remitente_id") or remitente.get("id") or d.get("sender_id")


def cuerpo_aviso(conversacion_id, mensaje_data):
    """Lo mínimo para pintar el aviso: quién, dónde y un resumen corto."""
    d = mensaje_data or {}
    remitente = d.get("remitente") if isinstance(d.get("remitente"), dict) else {}
    nombre = (remitente.get("nombre") or d.get("sender_name") or "").strip()
    texto = (d.get("contenido") or d.get("content") or "").strip()
    tipo = d.get("tipo") or d.get("type") or "text"
    if not texto and tipo != "text":
        texto = "Te ha enviado un archivo"
    return {
        "conversation_id": conversacion_id,
        "conversacion_id": conversacion_id,
        "sender_id": remitente_de(d),
        "sender_name": nombre,
        "remitente_nombre": nombre,
        "content": texto[:RESUMEN_MAX],
        "contenido": texto[:RESUMEN_MAX],
        "tipo": tipo,
        "message_id": d.get("id"),
    }


def emitir(socketio, conversacion_id, mensaje_data, buscar_participantes, registrar_error=None):
    """Emite `aviso_chat` a la sala personal de cada destinatario.

    Nunca levanta: un aviso que falla no puede tumbar la entrega del mensaje, que ya se hizo
    por la sala de la conversación.
    """
    if socketio is None:
        return []
    try:
        participantes = buscar_participantes(conversacion_id)
        gente = destinatarios(participantes, remitente_de(mensaje_data))
        if not gente:
            return []
        cuerpo = cuerpo_aviso(conversacion_id, mensaje_data)
        for uid in gente:
            socketio.emit("aviso_chat", cuerpo, room=f"user_{uid}")
        return gente
    except Exception as e:      # pragma: no cover - se prueba con un doble que revienta
        if registrar_error:
            registrar_error(e)
        return []
