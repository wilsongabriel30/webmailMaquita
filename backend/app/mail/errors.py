"""Errores del correo que la API debe traducir a una respuesta clara.

`CredencialIMAPInvalida` se lanza cuando el servidor de correo RECHAZA la
credencial guardada de la sesión: no es una avería del servidor, es que esa
sesión ya no sirve. Antes esto salía como 500 y la interfaz lo mostraba como
caída del sistema, cuando lo correcto es pedir que se vuelva a iniciar sesión.
"""


class CredencialIMAPInvalida(ConnectionError):
    """La credencial guardada ya no es válida: hay que iniciar sesión de nuevo."""
