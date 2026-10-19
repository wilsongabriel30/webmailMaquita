"""Validación de los argumentos del ayudante de sitios web.

El ayudante corre como root y recibe los argumentos del panel a través de maquita-sudo. Aunque el
envoltorio ya los valida, aquí se vuelven a comprobar: es el último punto antes de tocar el sistema.
"""

import re

from comun import ErrorSitio, de_base64

RE_DOMINIO = re.compile(r"^(?=.{4,200}$)([a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}$")
RE_CORREO = re.compile(r"^[a-z0-9][a-z0-9._+-]{0,63}@([a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}$")
RE_BASE64URL = re.compile(r"^[A-Za-z0-9_-]{1,200}$")
APLICACIONES = ("wordpress", "joomla", "moodle", "dolibarr", "matomo")

# Nombres que pertenecen al correo o al panel: nunca pueden ser un sitio.
PREFIJOS_RESERVADOS = ("mail.", "autodiscover.", "autoconfig.", "mta-sts.", "imap.", "smtp.", "pop3.")


def dominio(valor):
    if not isinstance(valor, str) or not RE_DOMINIO.match(valor):
        raise ErrorSitio("dominio no válido (solo minúsculas, números, guiones y puntos)")
    if valor.startswith("www."):
        raise ErrorSitio("escribe el dominio sin «www.»: el sitio responde también con www")
    if valor.startswith(PREFIJOS_RESERVADOS):
        raise ErrorSitio(f"{valor} está reservado para el correo")
    return valor


def correo(valor):
    if not isinstance(valor, str) or not RE_CORREO.match(valor):
        raise ErrorSitio("correo no válido")
    return valor


def aplicacion(valor):
    if valor not in APLICACIONES:
        raise ErrorSitio(f"aplicación no disponible: {valor}")
    return valor


def titulo(valor_b64):
    """Título del sitio, codificado en base64url por el panel."""
    if not isinstance(valor_b64, str) or not RE_BASE64URL.match(valor_b64):
        raise ErrorSitio("título no válido")
    try:
        texto = de_base64(valor_b64).strip()
    except Exception:
        raise ErrorSitio("título no válido")
    if not 1 <= len(texto) <= 100 or re.search(r"[\x00-\x1f\x7f<>]", texto):
        raise ErrorSitio("el título debe tener entre 1 y 100 caracteres, sin < ni >")
    return texto


def json_b64(valor, tope=8000):
    """Datos JSON en base64url (listas y formularios del panel)."""
    import json

    if not isinstance(valor, str) or len(valor) > tope:
        raise ErrorSitio("datos no válidos")
    try:
        return json.loads(de_base64(valor))
    except ValueError:
        raise ErrorSitio("datos no válidos")
