"""Errores del correo que la API debe traducir a una respuesta clara.

`CredencialIMAPInvalida` se lanza cuando el servidor de correo RECHAZA la
credencial guardada de la sesión: no es una avería del servidor, es que esa
sesión ya no sirve. Antes esto salía como 500 y la interfaz lo mostraba como
caída del sistema, cuando lo correcto es pedir que se vuelva a iniciar sesión.

Desde el 05/11/2026 la excepción guarda la respuesta de Dovecot y distingue el
rechazo de AUTENTICACIÓN (contraseña que ya no vale → se cierra esa sesión) de
otros «NO» del LOGIN (límite de conexiones, servidor ocupado), que no deben
cerrar nada.
"""

_MARCAS_AUTENTICACION = (
    "AUTHENTICATIONFAILED",
    "AUTHENTICATION FAILED",
    "AUTHORIZATIONFAILED",
)


def _texto_respuesta(resp) -> str:
    lineas = getattr(resp, "lines", None) or []
    partes = []
    for l in lineas:
        if isinstance(l, bytes):
            l = l.decode("utf-8", "replace")
        partes.append(str(l))
    return " | ".join(partes)[:300]


class CredencialIMAPInvalida(ConnectionError):
    """La credencial guardada ya no es válida: hay que iniciar sesión de nuevo."""

    def __init__(self, mensaje: str = "IMAP login failed", respuesta: str = ""):
        super().__init__(mensaje)
        self.respuesta = respuesta
        r = respuesta.upper()
        self.es_autenticacion = any(m in r for m in _MARCAS_AUTENTICACION)

    @classmethod
    def desde_respuesta(cls, resp, usuario: str = "") -> "CredencialIMAPInvalida":
        """Construye la excepción a partir de la respuesta `NO` del LOGIN de aioimaplib."""
        quien = f" for {usuario}" if usuario else ""
        return cls(f"IMAP login failed{quien}", _texto_respuesta(resp))
