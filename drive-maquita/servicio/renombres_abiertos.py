# -*- coding: utf-8 -*-
"""
Que el guardado del editor siga al archivo aunque se renombre (Drive Maquita)
=============================================================================
El editor guarda por un «callback» que lleva la ruta con la que se ABRIÓ el
archivo. Si mientras está abierto se le cambia el nombre (desde el Drive o,
desde el 23/09/2026, desde la barra del propio editor) o se renombra su
carpeta, el siguiente guardado escribía en la ruta vieja: reaparecía el
archivo con el nombre antiguo y el renombrado se quedaba sin los últimos
cambios.

Aquí se anota cada renombrado y el callback pregunta «¿esta ruta sigue
existiendo? si no, ¿a dónde se fue?» antes de guardar. Sigue cadenas
(A → B → C) y renombrados de carpetas (todo lo que había debajo).

Autoría: Equipo de Tecnología Maquita — 2026-09-23
"""
import logging

import almacen_bd as bd

log = logging.getLogger('almacen.renombres_abiertos')

DIAS = 30            # más que cualquier sesión de edición
_esquema_listo = False


def _esquema():
    global _esquema_listo
    if _esquema_listo:
        return
    bd.ejecutar("""
        CREATE TABLE IF NOT EXISTS renombres_recientes (
            id          SERIAL PRIMARY KEY,
            usuario_id  INTEGER NOT NULL,
            ruta_vieja  TEXT NOT NULL,
            ruta_nueva  TEXT NOT NULL,
            creado_en   TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
        CREATE INDEX IF NOT EXISTS ix_renombres_vieja
            ON renombres_recientes(ruta_vieja);
    """)
    _esquema_listo = True


def anotar(usuario, ruta_vieja, ruta_nueva):
    """Nunca lanza: anotar es una ayuda, no puede tumbar el renombrado."""
    try:
        if not ruta_vieja or not ruta_nueva or ruta_vieja == ruta_nueva:
            return
        _esquema()
        bd.ejecutar('INSERT INTO renombres_recientes (usuario_id, ruta_vieja, ruta_nueva) '
                    'VALUES (%s, %s, %s)', (int(usuario), ruta_vieja, ruta_nueva))
        bd.ejecutar("DELETE FROM renombres_recientes "
                    "WHERE creado_en < NOW() - (%s || ' days')::interval", (str(DIAS),))
    except Exception as exc:
        log.warning('no se pudo anotar el renombrado %s → %s: %s',
                    ruta_vieja, ruta_nueva, exc)


def _aplicar_en_orden(usuario, ruta, desde):
    """Aplica, del más antiguo al más reciente, los renombrados que afectan a
    la ruta (el archivo o cualquiera de sus carpetas). Así se encadenan bien
    «renombro el archivo y luego su carpeta» o al revés.

    Solo cuentan los hechos DESPUÉS de abrir el editor (`desde`, epoch): uno
    anterior podría llevar el guardado a otro archivo que hoy tiene ese nombre.
    """
    # En el espacio personal las rutas se repiten entre personas: cuenta el
    # dueño. En una unidad, la ruta es la misma para todos.
    filas = bd.consultar(
        "SELECT ruta_vieja, ruta_nueva FROM renombres_recientes "
        "WHERE (usuario_id = %s OR ruta_vieja LIKE '/unidades/%%') "
        "AND creado_en >= to_timestamp(%s) "
        "ORDER BY id DESC LIMIT 2000", (int(usuario), float(desde)))
    actual = ruta
    for f in reversed(filas):
        vieja, nueva = f['ruta_vieja'], f['ruta_nueva']
        if actual == vieja or actual.startswith(vieja + '/'):
            actual = nueva + actual[len(vieja):]
    return actual


def seguir(usuario, ruta, existe, desde):
    """La ruta vigente de un archivo abierto. `existe(ruta)` dice si está en disco
    y `desde` (epoch) es cuándo se abrió el editor.

    Si la ruta existe, se devuelve tal cual (caso normal, sin consultar nada
    más que el disco). Nunca lanza: ante cualquier problema, la ruta original.
    """
    try:
        if existe(ruta):
            return ruta
        _esquema()
        actual = _aplicar_en_orden(usuario, ruta, desde)
        if actual != ruta and existe(actual):
            log.info('guardado de %s redirigido a %s (renombrado)', ruta, actual)
            return actual
    except Exception as exc:
        log.warning('seguir renombrado de %s: %s', ruta, exc)
    return ruta
