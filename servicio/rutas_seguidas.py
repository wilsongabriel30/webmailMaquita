# -*- coding: utf-8 -*-
"""
Mover o renombrar sin romper lo que apunta al archivo (Drive Maquita)
====================================================================
Varias cosas del Drive guardan la RUTA de un archivo en la base de datos:

  · un formulario: dónde está su `.forma` y su hoja de respuestas (`encuestas`);
  · los libros que reciben respuestas de un formulario (`formulario_destinos`);
  · lo compartido: a quién y con qué permiso (`compartidos`);
  · las copias fieles de una hoja (`espejos_hoja`) y los vínculos de datos
    (`vinculos_datos`), por los dos extremos.

Hasta hoy, mover o renombrar un archivo —o la carpeta que lo contiene— no las
actualizaba. El 28/09/2026 se movió la carpeta de «prueba IFO» dentro de la
unidad y el formulario dejó de aceptar respuestas («ya no está»); y al abrirlo
se le habría dado un id nuevo, separándolo de todas sus respuestas.

`actualizar(usuario, vieja, nueva)` se llama tras cada mover/renombrar que
termina bien, con las rutas del espacio del DUEÑO. Si es una carpeta, cambia
también todo lo que hay dentro. En una unidad compartida la ruta es única; en
el espacio personal solo se tocan las filas de ese dueño. Nunca lanza.

Autoría: Equipo de Tecnología Maquita — 2026-09-28
"""
import logging

import almacen_bd as bd

log = logging.getLogger('almacen.rutas_seguidas')

# (tabla, columna de ruta, columna del dueño de esa ruta)
COLUMNAS = (
    # Lo compartido sigue a la carpeta: sin esto, renombrar o mover algo
    # compartido dejaba sin acceso a todos y rompía su enlace (29/09/2026).
    ('compartidos', 'ruta', 'propietario_id'),
    ('encuestas', 'ruta', 'propietario'),
    ('encuestas', 'hoja_ruta', 'propietario'),
    ('formulario_destinos', 'destino_ruta', 'destino_usuario'),
    ('espejos_hoja', 'origen_ruta', 'origen_usuario'),
    ('espejos_hoja', 'destino_ruta', 'destino_usuario'),
    ('vinculos_datos', 'origen_ruta', 'origen_usuario'),
    ('vinculos_datos', 'destino_ruta', 'destino_usuario'),
)


def actualizar(usuario, vieja, nueva):
    """Cambia `vieja` (archivo o carpeta) por `nueva` donde esté guardada."""
    if not vieja or not nueva or vieja == nueva:
        return 0
    total = 0
    en_unidad = vieja.startswith('/unidades/')
    for tabla, columna, dueno in COLUMNAS:
        try:
            # Sin LIKE: los nombres pueden llevar «_» o «%», que son comodines.
            filas = bd.consultar(
                'UPDATE {t} SET {c} = %(nueva)s || substr({c}, length(%(vieja)s) + 1) '
                'WHERE ({c} = %(vieja)s OR left({c}, length(%(vieja)s) + 1) = %(vieja)s || \'/\') '
                '  AND (%(unidad)s OR {d} = %(usuario)s) RETURNING 1'
                .format(t=tabla, c=columna, d=dueno),
                {'vieja': vieja, 'nueva': nueva, 'unidad': en_unidad, 'usuario': int(usuario)})
            total += len(filas or [])
        except Exception as excepcion:
            # La tabla puede no existir todavía (se crean al primer uso).
            log.info('rutas %s.%s: %s', tabla, columna, excepcion)
    if total:
        log.info('%s → %s: %d rutas guardadas actualizadas', vieja, nueva, total)
    return total
