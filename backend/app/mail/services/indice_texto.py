"""¿Tiene esta cuenta índice de texto completo ya construido? ¿Entran en él los adjuntos?

La indexación inicial (de noche, `busqueda-indexar-noche`, o la que lanza el instalador,
`maquita-fts indexar-inicial`) anota cada cuenta terminada en un archivo de cuentas «hechas», una dirección
por línea: `/var/lib/maquita-busqueda/hechas.txt`. Se lee también el de la instalación anterior
(`/var/lib/fts-indexar/hechos.txt`, de cuando el motor era Xapian). Con índice, buscar dentro del
texto de todo el buzón son segundos; sin él hay que descifrar los mensajes uno a uno y son minutos.
De eso depende que la búsqueda en el texto se acote por fecha o no.

Los adjuntos entran en el índice cuando está instalado el decodificador (deploy/dovecot/fts): su
configuración de Dovecot existe. Entonces buscar «dentro del texto» encuentra también palabras de los
PDF, documentos de Office y comprimidos adjuntos.
"""

import os

_RUTAS_HECHOS = (
    "/var/lib/maquita-busqueda/hechas.txt",
    "/var/lib/fts-indexar/hechos.txt",
)
_CONF_ADJUNTOS = "/etc/dovecot/maquita.d/61-busqueda-adjuntos.conf"
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
