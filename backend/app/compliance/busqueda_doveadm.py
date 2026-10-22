"""Órdenes doveadm del eDiscovery: por maquita-sudo y con las palabras clave dentro de la búsqueda.

Antes la búsqueda pedía a doveadm todos los mensajes de la carpeta en el rango de fechas y luego
filtraba las palabras clave en Python con el asunto, las direcciones y una vista previa del cuerpo
(los primeros caracteres): no veía el resto del texto ni los adjuntos, y abría los mensajes uno a uno.
Ahora las palabras van en la propia consulta (`text …`, unidas con OR): con el índice de texto
completo activo (fts-flatcurve) Dovecot responde desde el índice, que incluye el texto de los
adjuntos si el decodificador está instalado; sin índice, Dovecot busca igual, leyendo los mensajes.

Las órdenes pasan por maquita-sudo (el único programa que sudoers concede a www-data), que vuelve a
validar cada argumento. Buscar no modifica nada: ni los mensajes ni las retenciones legales.
"""

MAQUITA_SUDO = "/usr/local/sbin/maquita-sudo"
_MAX_PALABRA = 200
_MAX_PALABRAS = 50


def orden_doveadm(*args: str) -> list[str]:
    return ["/usr/bin/sudo", "-n", MAQUITA_SUDO, "doveadm", *args]


def palabra_limpia(valor: str) -> str:
    """Sin caracteres de control ni guiones al principio (doveadm y maquita-sudo los leerían como opción)."""
    limpio = "".join(c for c in str(valor) if c >= " " and c != "\x7f").strip()
    return limpio.lstrip("-").strip()[:_MAX_PALABRA]


def consulta_busqueda(
    carpeta: str, desde: str = "", hasta: str = "", palabras=()
) -> list[str]:
    """Argumentos de `doveadm search -u <buzón> …` (consulta en la sintaxis de doveadm-search-query)."""
    consulta = ["mailbox", carpeta]
    if desde:
        consulta += ["since", desde[:10]]
    if hasta:
        consulta += ["before", hasta[:10]]
    limpias = [p for p in (palabra_limpia(p) for p in palabras or ()) if p][
        :_MAX_PALABRAS
    ]
    if limpias:
        # «OR a OR b c»: cualquiera de las palabras, en cabeceras, cuerpo o adjuntos.
        for palabra in limpias[:-1]:
            consulta += ["OR", "text", palabra]
        consulta += ["text", limpias[-1]]
    return consulta
