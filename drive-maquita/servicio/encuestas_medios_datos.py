# -*- coding: utf-8 -*-
"""Formularios del Almacén — datos propios de cada foto o video recibido (11/11/2026).

Punto único para anotar en la ficha de un archivo pendiente lo que el archivo dice de sí mismo
(`datos`): las fotos con `encuestas_foto_datos`, los videos (teléfono o dron) con
`encuestas_video_datos`. Lo usan la subida web y la de la app. Nunca hace fallar una subida."""
import json
import logging
import os

import encuestas_archivos as archivos

log = logging.getLogger(__name__)


def anotar(encuesta_id, ficha):
    """Devuelve la ficha con `datos` (y la deja así en disco) si el archivo trae algo que leer."""
    try:
        extension = archivos.extension_de(ficha.get('nombre', ''))
        camino = archivos.camino_pendiente(encuesta_id, ficha.get('id'))
        if not camino:
            return ficha
        if extension in ('jpg', 'jpeg'):
            import encuestas_foto_datos
            datos = encuestas_foto_datos.leer(camino)
        else:
            import encuestas_video_datos
            datos = encuestas_video_datos.leer(camino) if extension in encuestas_video_datos.EXTENSIONES else None
        if not datos:
            return ficha
        ficha = dict(ficha, datos=datos)
        with open(os.path.splitext(camino)[0] + '.json', 'w', encoding='utf-8') as salida:
            json.dump(ficha, salida, ensure_ascii=False)
    except Exception:
        log.exception('No se pudieron leer los datos del archivo %s', ficha.get('id') if isinstance(ficha, dict) else ficha)
    return ficha
