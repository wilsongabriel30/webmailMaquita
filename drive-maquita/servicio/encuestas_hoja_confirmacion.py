# -*- coding: utf-8 -*-
"""
Formularios del Almacén — una respuesta no se da por escrita hasta que ESTÁ EN EL ARCHIVO
=========================================================================================
El complemento «respuestas en vivo» escribe las filas DENTRO de la sesión abierta
del editor y avisa con `/encuestas/vivo/aplicado`. Hasta el 22/09/2026 ese aviso
anotaba el estado como definitivo, pero lo que el complemento escribe solo llega
al `.xlsx` cuando OnlyOffice guarda el documento. Si el libro se cierra sin que
ese guardado cuaje —o el editor descarta los cambios—, la fila **no existe en
ningún sitio** y, como el estado decía que ya estaba escrita, el motor no la
reintentaba nunca. Caso real: «Nuevo Formulario (respuestas).xlsx», respuesta de
las 09:26 del 22/09/2026; ninguna versión del archivo llegó a tener filas.

Aquí vive la comprobación contra el archivo de verdad:

  · `fechas_en_hoja` — qué respuestas están escritas, leídas de la columna
    «Fecha» de la tabla;
  · `ultima_escrita` — hasta qué respuesta puede darse por buena;
  · `revisar` — al cerrarse el editor, recalcula el estado de los formularios
    que tenían una confirmación PROVISIONAL (la del complemento) y devuelve a
    pendiente lo que no haya llegado al disco.

La confirmación del complemento se sigue anotando —si no, el puente le mandaría
las mismas filas cada 5 s y saldrían duplicadas—, pero marcada como provisional.

Autoría: Equipo de Tecnología Maquita — 2026-09-22
"""
import logging
import os
from datetime import datetime, timedelta

log = logging.getLogger('almacen.encuestas.confirmacion')


def fechas_en_hoja(contenido):
    """Marcas de tiempo (al segundo) de la columna «Fecha» de la tabla.

    Devuelve None si el archivo no se puede leer o no tiene esa columna: no es
    lo mismo «no hay ninguna» que «no se sabe», y confundirlas borraría el
    estado de una hoja perfectamente escrita.
    """
    import encuestas_hoja_libro as libro
    import encuestas_hoja_xml as xml_mod
    try:
        encabezados, filas = xml_mod.leer_tabla(contenido)
    except Exception as excepcion:
        log.warning('no se pudo leer la tabla (%s)', excepcion)
        return None
    normales = [libro.normalizar(e) for e in encabezados]
    if 'FECHA' not in normales:
        return None
    columna = normales.index('FECHA')
    momentos = set()
    for fila in filas:
        if columna >= len(fila):
            continue
        try:
            momento = datetime(1899, 12, 30) + timedelta(days=float(fila[columna]))
        except (TypeError, ValueError):
            continue
        # Medio segundo: el editor guarda la fecha como número y al releerla
        # bailan los microsegundos.
        momentos.add((momento + timedelta(milliseconds=500)).replace(microsecond=0))
    return momentos


def ultima_escrita(contenido, enviadas):
    """La última respuesta que de verdad aparece en el archivo, o None.

    `enviadas` son las fechas de todas las respuestas del formulario.
    """
    momentos = fechas_en_hoja(contenido)
    if momentos is None:
        return False            # no se sabe: quien llame decide no tocar nada
    presentes = [e for e in sorted(x for x in enviadas if x)
                 if e.replace(tzinfo=None, microsecond=0) in momentos]
    return max(presentes) if presentes else None


def revisar(usuario, ruta_hoja):
    """Al cerrarse el editor: lo que el complemento dio por escrito y no está
    en el archivo vuelve a contar como pendiente."""
    import encuestas_bd as ebd
    import encuestas_hoja as hoja_mod
    import encuestas_hoja_libro as libro
    import nucleo_archivos as nucleo
    from api_encuestas import leer_definicion

    try:
        filas = ebd.bd.consultar(
            "SELECT * FROM encuestas WHERE hoja_ruta = %s "
            "AND (propietario = %s OR hoja_ruta LIKE '/unidades/%%')",
            (ruta_hoja, int(usuario)))
    except Exception as excepcion:
        log.warning('revisar %s: no se pudo consultar (%s)', ruta_hoja, excepcion)
        return
    contenido = None
    for fila in filas:
        estado = libro.leer_estado(fila['id'])
        if not estado or not estado.get('provisional'):
            continue
        if contenido is None:
            try:
                fisica = nucleo.ruta_fisica(int(fila['propietario']), ruta_hoja)
                contenido = open(fisica, 'rb').read() if os.path.isfile(fisica) else b''
            except Exception as excepcion:
                log.warning('revisar %s: no se pudo leer el archivo (%s)',
                            ruta_hoja, excepcion)
                return
        definicion = leer_definicion(int(fila['propietario']), fila['ruta'])
        if definicion is None:
            continue
        enviadas = hoja_mod.datos_de_hoja(fila, definicion)['enviadas']
        real = ultima_escrita(contenido, enviadas) if contenido else None
        if real is False:                    # ilegible: no se toca el estado
            continue
        if real == estado['hasta']:
            libro.guardar_estado(fila['id'], estado['hasta'], estado['preguntas'])
            continue
        log.info('hoja %s: el editor no guardó hasta %s; queda pendiente desde %s',
                 ruta_hoja, estado['hasta'], real)
        libro.guardar_estado(fila['id'], real, estado['preguntas'])
