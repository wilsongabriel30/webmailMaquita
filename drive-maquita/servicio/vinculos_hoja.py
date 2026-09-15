# -*- coding: utf-8 -*-
"""Renombrar la hoja de DESTINO de un vínculo de datos (11/09/2026).

Caso que lo motivó: la hoja de respuestas de un formulario en el libro se llama
como el formulario; si la persona cambia el título del formulario, la pestaña
debe seguirle. El libro puede estar abierto en OnlyOffice en ese momento, y lo
que se escriba en disco lo pisa su siguiente guardado, así que:

- con el libro CERRADO se renombra en el acto (`renombrar_en_libro`);
- con el libro ABIERTO se deja anotado (`destino_hoja_previa`) y el callback de
  cierre lo aplica (`aplicar_renombres_pendientes`, desde `refrescar_por_destino`).

En ambos casos `vinculos_datos.destino_hoja` ya lleva el nombre nuevo, para que
la siguiente escritura del vínculo vaya a la pestaña correcta.
"""
import io
import logging

import openpyxl

import almacen_bd as bd
from seguridad_rutas import ruta_fisica

log = logging.getLogger('almacen.vinculos.hoja')


def libro_abierto(usuario, ruta_libro):
    """¿Hay alguien con el libro abierto en el editor?"""
    try:
        from api_onlyoffice import _base_documento
        from guardado_forzado import _sala_abierta
        return _sala_abierta(_base_documento(usuario, ruta_libro))
    except Exception as excepcion:
        log.warning('no se pudo saber si %s está abierto: %s', ruta_libro, excepcion)
        return True          # ante la duda, tratarlo como abierto (no pisar)


def renombrar_en_libro(usuario, ruta_libro, viejo, nuevo):
    """Renombra la hoja en el archivo del libro. Devuelve True si lo hizo."""
    import nucleo_archivos as nucleo
    if not viejo or not nuevo or viejo == nuevo:
        return False
    fisica = ruta_fisica(usuario, ruta_libro)
    libro = openpyxl.load_workbook(fisica)
    try:
        if viejo not in libro.sheetnames:
            return False
        if nuevo in libro.sheetnames:
            # Ya existe la pestaña nueva (la creó el vínculo mientras el libro
            # estaba abierto): la vieja es la misma tabla, sobra.
            libro.remove(libro[viejo])
        else:
            libro[viejo].title = nuevo
        memoria = io.BytesIO()
        libro.save(memoria)
    finally:
        libro.close()
    memoria.seek(0)
    carpeta, _, nombre = ruta_libro.rpartition('/')
    nucleo.subir(usuario, carpeta or '/', nombre, memoria)
    try:
        from api_onlyoffice import invalidar_cache
        invalidar_cache(usuario, ruta_libro)
    except Exception as excepcion:
        log.warning('renombrar %s: no se refrescó el editor (%s)', ruta_libro, excepcion)
    log.info('hoja «%s» → «%s» en %s', viejo, nuevo, ruta_libro)
    return True


def programar_renombre(vinculo_id, viejo, nuevo):
    """Anota el cambio de nombre para aplicarlo cuando se cierre el libro."""
    bd.ejecutar("""UPDATE vinculos_datos
                      SET destino_hoja = %s,
                          destino_hoja_previa = COALESCE(destino_hoja_previa, %s)
                    WHERE id = %s""", (nuevo, viejo, vinculo_id))


def aplicar_renombres_pendientes(vinculos):
    """Para cada vínculo con `destino_hoja_previa`, renombra la hoja en el
    libro (ya cerrado) y limpia la anotación. Nunca lanza."""
    for v in vinculos:
        previa = v.get('destino_hoja_previa')
        if not previa:
            continue
        try:
            renombrar_en_libro(v['destino_usuario'], v['destino_ruta'],
                               previa, v['destino_hoja'])
        except Exception as excepcion:
            log.warning('vínculo %s: no se pudo renombrar «%s» → «%s»: %s',
                        v.get('id'), previa, v.get('destino_hoja'), excepcion)
            continue
        bd.ejecutar('UPDATE vinculos_datos SET destino_hoja_previa = NULL WHERE id = %s',
                    (v['id'],))
