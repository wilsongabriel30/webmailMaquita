"""
Nombre libre para una copia (14/09/2026).

«Copiar a» escribía en el destino sin mirar si ya había algo con ese nombre:
un archivo se SOBRESCRIBÍA en silencio y una carpeta fallaba con error 500.
Aquí se busca un nombre que no exista, como hace Google Drive:
«Informe.xlsx» → «Informe (copia).xlsx» → «Informe (copia 2).xlsx».
"""
import os
import posixpath

from seguridad_rutas import normalizar_ruta_virtual, ruta_fisica


def _existe(usuario_id: int, ruta_virtual: str) -> bool:
    return os.path.lexists(ruta_fisica(usuario_id, ruta_virtual))


def nombre_libre(usuario_id: int, ruta_virtual: str) -> str:
    """Devuelve `ruta_virtual` si está libre; si no, la primera variante «(copia N)»."""
    ruta = normalizar_ruta_virtual(ruta_virtual)
    if not _existe(usuario_id, ruta):
        return ruta
    carpeta, nombre = posixpath.split(ruta)
    base, extension = posixpath.splitext(nombre)
    if not base:                      # «.oculto»: sin extensión real
        base, extension = nombre, ''
    for numero in range(1, 1000):
        sufijo = ' (copia)' if numero == 1 else f' (copia {numero})'
        candidata = posixpath.join(carpeta, f'{base}{sufijo}{extension}')
        if not _existe(usuario_id, candidata):
            return candidata
    raise FileExistsError(ruta)


def dentro_de_si_misma(origen: str, destino: str) -> bool:
    """True si el destino queda DENTRO del origen (copiarlo ahí no acabaría nunca)."""
    o = normalizar_ruta_virtual(origen).rstrip('/')
    d = normalizar_ruta_virtual(destino).rstrip('/')
    return d.startswith(o + '/')
