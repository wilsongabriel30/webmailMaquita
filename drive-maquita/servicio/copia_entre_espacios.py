# -*- coding: utf-8 -*-
"""
Copia entre espacios distintos del Almacén Maquita.
===================================================
`nucleo_archivos.copiar` copia dentro del espacio de UNA persona. Con el espacio
«Compartido conmigo» aparece un caso que antes no existía: llevarse a «Mi
unidad» una copia de algo que otra persona compartió (o al revés, dejar una
copia dentro de lo compartido). Origen y destino son de dueños distintos, así
que hay que resolver cada ruta con su propio dueño y avisar al índice del
dueño del DESTINO, que es quien se queda con la copia.

Autoría: Equipo de Tecnología Maquita — 2026-08-24
"""
import logging
import os
import shutil

import indice_busqueda as indice
import indice_contenido as contenido
from seguridad_rutas import normalizar_ruta_virtual, ruta_fisica

log = logging.getLogger('almacen.compartidos')


def copiar_entre_espacios(usuario_origen: int, ruta_origen: str,
                          usuario_destino: int, ruta_destino: str) -> None:
    """Copia de un espacio a otro. Los permisos ya se validaron en la API."""
    origen_virtual = normalizar_ruta_virtual(ruta_origen)
    destino_virtual = normalizar_ruta_virtual(ruta_destino)
    origen = ruta_fisica(usuario_origen, origen_virtual)
    destino = ruta_fisica(usuario_destino, destino_virtual)
    if not os.path.exists(origen):
        raise FileNotFoundError(ruta_origen)
    os.makedirs(os.path.dirname(destino), exist_ok=True)
    if os.path.isdir(origen):
        shutil.copytree(origen, destino)
    else:
        shutil.copy2(origen, destino)
    # El índice y el extractor de contenido son los del dueño del destino: la
    # copia es suya y debe encontrarla al buscar en su Drive.
    indice.agregar(usuario_destino, destino_virtual)
    contenido.encolar(usuario_destino, destino_virtual)
