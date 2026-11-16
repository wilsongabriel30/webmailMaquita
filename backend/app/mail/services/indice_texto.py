"""¿Tiene esta cuenta índice de texto completo ya construido? ¿Entran en él los adjuntos?

La indexación inicial (de noche, `busqueda-indexar-noche`, o la que lanza el instalador,
`maquita-fts indexar-inicial`) anota cada cuenta terminada en un archivo de cuentas «hechas», una dirección
por línea: `/var/lib/maquita-busqueda/hechas.txt`. Se lee también el de la instalación anterior
(`/var/lib/fts-indexar/hechos.txt`, de cuando el motor era Xapian). Con índice, buscar dentro del
texto de todo el buzón son segundos; sin él hay que descifrar los mensajes uno a uno y son minutos.
De eso depende que la búsqueda en el texto se acote por fecha o no.

Cuentas que aún no figuran como «hechas» (15/11/2026, informe de Andes: «el buscador no encuentra
palabras del texto, solo de asunto y remitente, aunque el índice está activo»). Una cuenta solo se
anota de noche, cuando termina su indexación inicial: la creada hoy, o la que espera turno, buscaba
solo en los encabezados aunque Dovecot ya indexa cada correo al llegar. Ahora, si el servidor tiene
el motor de búsqueda instalado y la carpeta abierta es pequeña (`CARPETA_ABARCABLE` mensajes como
mucho), la búsqueda entra también en el texto: lo que falte por indexar en una carpeta así se
completa en esa misma búsqueda. En las carpetas grandes de cuentas sin anotar se sigue esperando a
la indexación nocturna: completar ahí el índice al buscar son minutos.

Los adjuntos entran en el índice cuando está instalado el decodificador (deploy/dovecot/fts): su
configuración de Dovecot existe. Entonces buscar «dentro del texto» encuentra también palabras de los
PDF, documentos de Office y comprimidos adjuntos.
"""

import os
import re

_RUTAS_HECHOS = (
    "/var/lib/maquita-busqueda/hechas.txt",
    "/var/lib/fts-indexar/hechos.txt",
)
_CONF_ADJUNTOS = "/etc/dovecot/maquita.d/61-busqueda-adjuntos.conf"
_CONF_MOTOR = "/etc/dovecot/maquita.d/60-busqueda.conf"
CARPETA_ABARCABLE = (
    2000  # mensajes; hasta aquí se busca en el texto sin esperar a la noche
)
_RE_EXISTS = re.compile(r"^\*?\s*(\d+)\s+EXISTS\b", re.IGNORECASE)
_cache: tuple[tuple, frozenset[str]] = ((), frozenset())


def _rutas() -> tuple[str, ...]:
    propia = os.environ.get("FTS_HECHOS")
    return (propia,) if propia else _RUTAS_HECHOS


def _sellos(rutas: tuple[str, ...]) -> tuple:
    sellos = []
    for ruta in rutas:
        try:
            sellos.append((ruta, os.stat(ruta).st_mtime))
        except OSError:
            continue
    return tuple(sellos)


def cuenta_indexada(usuario: str) -> bool:
    """True si la cuenta figura como indexada. Ante cualquier duda, False (se acota)."""
    global _cache
    if not usuario:
        return False
    sellos = _sellos(_rutas())
    if not sellos:
        return False
    if sellos != _cache[0]:
        cuentas: set[str] = set()
        for ruta, _ in sellos:
            try:
                with open(ruta, encoding="utf-8", errors="replace") as f:
                    cuentas.update(x.strip().lower() for x in f if x.strip())
            except OSError:
                continue
        _cache = (sellos, frozenset(cuentas))
    return usuario.strip().lower() in _cache[1]


def adjuntos_indexados() -> bool:
    """True si el índice incluye el texto de los adjuntos (decodificador instalado)."""
    return os.path.exists(os.environ.get("FTS_CONF_ADJUNTOS", _CONF_ADJUNTOS))


def motor_instalado() -> bool:
    """True si el servidor tiene búsqueda de texto completo: su configuración o su lista de cuentas.

    `FTS_CONF_MOTOR` permite señalar otro archivo en un servidor con el motor configurado a mano.
    """
    if os.path.exists(os.environ.get("FTS_CONF_MOTOR", _CONF_MOTOR)):
        return True
    return bool(_sellos(_rutas()))


def mensajes_de_la_carpeta(lineas_select) -> int | None:
    """Cuántos mensajes tiene la carpeta, según la respuesta a SELECT (`12 EXISTS`)."""
    for linea in lineas_select or []:
        if isinstance(linea, (bytes, bytearray)):
            linea = bytes(linea).decode("ascii", errors="replace")
        m = _RE_EXISTS.match(str(linea).strip())
        if m:
            return int(m.group(1))
    return None


def carpeta_abarcable(lineas_select) -> bool:
    """True si, sin estar la cuenta anotada, se puede buscar ya en el texto de esta carpeta."""
    total = mensajes_de_la_carpeta(lineas_select)
    return total is not None and total <= CARPETA_ABARCABLE and motor_instalado()
