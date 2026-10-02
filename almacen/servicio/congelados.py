# -*- coding: utf-8 -*-
"""Drives congelados (multicuenta, fase 4).

Cuando alguien sale de la organización, su buzón se asigna a otra persona para que atienda el
correo mientras llega el reemplazo (días o meses). Su Drive no se toca ni se entrega: queda
congelado. Congelado quiere decir que NADIE entra (ni la persona, ni quien revisa el correo, ni
los enlaces públicos ya compartidos, ni el canal interno del chat), hasta que Tecnología lo
descongela, normalmente al poner al nuevo titular desde el panel.

Se comprueba en `ruta_fisica` (por ahí pasa todo acceso a disco) y, para dar un mensaje claro,
también en el candado del webmail y en los enlaces públicos. Caché de 30 s por usuario para no
consultar la base en cada acceso.
"""
import logging
import time

from almacen_bd import consultar, ejecutar

log = logging.getLogger('almacen.congelados')

_DDL = """
CREATE TABLE IF NOT EXISTS drives_congelados (
    usuario_id  integer PRIMARY KEY,
    correo      text,
    motivo      text,
    por         text,
    desde       timestamptz NOT NULL DEFAULT now()
)
"""
_tabla_ok = False
_CACHE_SEG = 30
_cache: dict[int, tuple[float, dict | None]] = {}


def _tabla() -> None:
    global _tabla_ok
    if not _tabla_ok:
        ejecutar(_DDL)
        _tabla_ok = True


def info(usuario_id) -> dict | None:
    """Fila del congelado (correo, motivo, por, desde) o None. Con caché corta."""
    try:
        uid = int(usuario_id)
    except (TypeError, ValueError):
        return None
    ahora = time.monotonic()
    en_cache = _cache.get(uid)
    if en_cache and ahora - en_cache[0] < _CACHE_SEG:
        return en_cache[1]
    try:
        _tabla()
        filas = consultar('SELECT usuario_id, correo, motivo, por, desde FROM drives_congelados WHERE usuario_id = %s', (uid,))
        dato = dict(filas[0]) if filas else None
    except Exception as exc:  # la base caída no debe abrir un Drive congelado: se asume congelado
        log.error('No se pudo consultar drives_congelados para %s: %s', uid, exc)
        return en_cache[1] if en_cache else {'usuario_id': uid, 'motivo': 'sin_verificar'}
    _cache[uid] = (ahora, dato)
    return dato


def esta_congelado(usuario_id) -> bool:
    return info(usuario_id) is not None


def congelar(usuario_id: int, correo: str, motivo: str, por: str) -> dict:
    _tabla()
    ejecutar(
        """INSERT INTO drives_congelados (usuario_id, correo, motivo, por) VALUES (%s, %s, %s, %s)
           ON CONFLICT (usuario_id) DO UPDATE SET correo = EXCLUDED.correo, motivo = EXCLUDED.motivo,
                                                  por = EXCLUDED.por, desde = now()""",
        (int(usuario_id), correo, (motivo or '')[:200], (por or '')[:120]),
    )
    _cache.pop(int(usuario_id), None)
    log.warning('Drive %s (%s) CONGELADO por %s: %s', usuario_id, correo, por, motivo)
    return info(usuario_id) or {}


def descongelar(usuario_id: int, por: str) -> bool:
    _tabla()
    habia = esta_congelado(usuario_id)
    ejecutar('DELETE FROM drives_congelados WHERE usuario_id = %s', (int(usuario_id),))
    _cache.pop(int(usuario_id), None)
    if habia:
        log.warning('Drive %s descongelado por %s', usuario_id, por)
    return habia


MENSAJE = ('Este Drive está congelado por Tecnología: su titular dejó la organización y los archivos '
           'se conservan sin acceso hasta que se asigne un nuevo titular.')
