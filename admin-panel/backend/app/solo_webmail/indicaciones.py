"""Indicación en lenguaje llano para cada cuenta de la pantalla «Solo webmail».

Función pura (sin base de datos) para poder probarla: recibe lo que se sabe de la cuenta y
devuelve qué decirle al administrador antes de activar o quitar la protección.
"""

MIN_DIRECCIONES_ATAQUE = 3


def indicacion(
    protegida: bool,
    accesos_externos: int,
    claves_aplicacion: int,
    direcciones_con_fallos: int,
    hay_datos_de_uso: bool = True,
) -> dict:
    """Devuelve {"nivel": "ok|info|aviso|alerta", "texto": "..."}."""
    if protegida:
        if claves_aplicacion > 0:
            return {
                "nivel": "ok",
                "texto": "Protegida. Sus equipos (Outlook, celular) entran con contraseña de aplicación.",
            }
        return {
            "nivel": "ok",
            "texto": "Protegida. Solo entra por el webmail; desde fuera la contraseña no sirve.",
        }
    if not hay_datos_de_uso:
        return {
            "nivel": "info",
            "texto": "Sin datos de uso: confirme con la persona si usa Outlook o celular antes de protegerla.",
        }
    usa_equipos = accesos_externos > 0
    if direcciones_con_fallos >= MIN_DIRECCIONES_ATAQUE:
        texto = (
            f"Recibe intentos fallidos desde {direcciones_con_fallos} direcciones: revise «Alertas de seguridad» para ver "
            "de dónde vienen antes de decidir."
        )
        if usa_equipos and claves_aplicacion == 0:
            texto += (
                " Usa Outlook o celular: si la protege, primero debe crear una contraseña de aplicación o esos equipos "
                "dejarán de recibir correo."
            )
        return {"nivel": "alerta", "texto": texto}
    if not usa_equipos:
        return {
            "nivel": "info",
            "texto": "Se puede proteger sin afectar a la persona: no usa Outlook ni celular.",
        }
    if claves_aplicacion > 0:
        return {
            "nivel": "info",
            "texto": "Usa Outlook o celular y ya tiene contraseña de aplicación: se puede proteger.",
        }
    return {
        "nivel": "aviso",
        "texto": (
            "Usa Outlook o celular con su contraseña. Si la protege, esos equipos dejarán de funcionar hasta que cree "
            "una contraseña de aplicación desde su cuenta."
        ),
    }
