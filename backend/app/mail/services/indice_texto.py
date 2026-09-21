"""¿Tiene esta cuenta índice de texto completo (FTS Xapian) ya construido?

La indexación inicial corre de noche y anota cada cuenta terminada en un archivo de «hechos»
(`/var/lib/fts-indexar/hechos.txt`, una dirección por línea). Con índice, buscar dentro del texto
de todo el buzón son segundos; sin él hay que descifrar los mensajes uno a uno y son minutos. De
eso depende que la búsqueda en el texto se acote por fecha o no.
"""

import os

_RUTA = os.environ.get("FTS_HECHOS", "/var/lib/fts-indexar/hechos.txt")
_cache: tuple[float, frozenset[str]] = (-1.0, frozenset())


def cuenta_indexada(usuario: str) -> bool:
    """True si la cuenta figura como indexada. Ante cualquier duda, False (se acota)."""
    global _cache
    if not usuario:
        return False
    try:
        mtime = os.stat(_RUTA).st_mtime
        if mtime != _cache[0]:
            with open(_RUTA, encoding="utf-8", errors="replace") as f:
                _cache = (mtime, frozenset(l.strip().lower() for l in f if l.strip()))
    except OSError:
        return False
    return usuario.strip().lower() in _cache[1]
