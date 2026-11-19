"""Direcciones de los destinatarios de una petición, sin nombres ni signos < >.

El 19/11/2026 la recuperación de un correo falló con 422 porque la interfaz enviaba
«Mishel Pilicita <correo@ejemplo.org>» en vez de la dirección sola. La interfaz ya se corrigió;
aquí el servidor deja de depender de ella: acepta ambas formas y se queda con la dirección.
"""

from email.utils import getaddresses


def solo_direcciones(valores: list[str] | tuple[str, ...] | None) -> list[str]:
    """Direcciones en minúsculas, sin repetir y en el orden recibido.

    Lo que no sea una dirección se devuelve tal cual (en minúsculas) para que la validación
    posterior lo rechace con su mensaje; aquí no se descarta nada en silencio.
    """
    resultado: list[str] = []
    for _nombre, direccion in getaddresses(
        [v for v in (valores or ()) if v and v.strip()]
    ):
        direccion = direccion.strip().lower()
        if direccion and direccion not in resultado:
            resultado.append(direccion)
    return resultado
