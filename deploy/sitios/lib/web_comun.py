"""Validación común de las funciones web por sitio: rutas, direcciones y nombres que acaban en la configuración
de nginx.

Nada de lo que escribe la persona llega a nginx sin pasar por aquí: solo se admite un juego cerrado de caracteres
(sin espacios, comillas, barras inversas, «$», «;», «{», «}», «#» ni saltos de línea), así que un valor no puede
cerrar la directiva ni abrir otra. Todo lo demás se rechaza con un mensaje, no se «limpia» en silencio.
"""

import re
from urllib.parse import urlsplit

from comun import ErrorSitio

# Ruta de una dirección web: lo que se compara con $uri (ya decodificado por nginx, por eso sin «%»).
RE_RUTA = re.compile(r"^/[A-Za-z0-9._~/+-]{0,200}$")
# Dirección de destino: esquema, nombre y lo que siga, con caracteres que no cierran una cadena de nginx.
RE_URL = re.compile(r"^https?://[A-Za-z0-9.-]{1,253}(?::\d{1,5})?(?:[/?#][A-Za-z0-9._~%/+=&?#:@!,-]{0,500})?$")
RE_NOMBRE = re.compile(r"^(?=.{1,253}$)(?:\*\.)?([a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}$")


def ruta(valor, que="ruta"):
    """Ruta normalizada («/carpeta», sin barra final salvo «/»). Sin «..», «//» ni carpetas ocultas."""
    if not isinstance(valor, str):
        raise ErrorSitio(f"{que} no válida")
    valor = valor.strip()
    if not valor.startswith("/"):
        valor = "/" + valor
    if len(valor) > 1:
        valor = valor.rstrip("/") or "/"
    if not RE_RUTA.fullmatch(valor) or "//" in valor:
        raise ErrorSitio(f"{que} no válida: empieza por «/» y solo lleva letras sin tilde, números y . _ ~ / + -")
    partes = valor.split("/")[1:]
    if any(p in (".", "..") or p.startswith(".") for p in partes if p):
        raise ErrorSitio(f"{que} no válida: sin «..» ni carpetas ocultas (que empiezan por punto)")
    return valor


def regex(valor):
    """La ruta ya validada como expresión regular de nginx (solo «.» y «+» son especiales en su juego)."""
    return valor.replace(".", r"\.").replace("+", r"\+")


def url(valor):
    if not isinstance(valor, str):
        raise ErrorSitio("dirección de destino no válida")
    valor = valor.strip()
    if not RE_URL.fullmatch(valor):
        raise ErrorSitio("dirección de destino no válida: http:// o https://, un nombre y una ruta sin espacios, "
                         "comillas ni los signos $ ; { } \\")
    partes = urlsplit(valor)
    if not partes.hostname or partes.hostname.startswith(("-", ".")) or ".." in partes.hostname:
        raise ErrorSitio("dirección de destino no válida")
    return valor


def nombre(valor):
    """Nombre de dominio, con «*.» delante si vale para todos sus subdominios."""
    valor = (valor or "").strip().lower() if isinstance(valor, str) else ""
    if not RE_NOMBRE.fullmatch(valor):
        raise ErrorSitio(f"dominio no válido: {str(valor)[:60]}")
    return valor


def booleano(valor):
    if isinstance(valor, bool):
        return valor
    if valor in (0, 1, "0", "1", "si", "no"):
        return valor in (1, "1", "si")
    raise ErrorSitio("valor sí/no no válido")


def lista(valor, maximo, que):
    if valor is None:
        return []
    if not isinstance(valor, list):
        raise ErrorSitio(f"{que}: se esperaba una lista")
    if len(valor) > maximo:
        raise ErrorSitio(f"{que}: como máximo {maximo}")
    return valor
