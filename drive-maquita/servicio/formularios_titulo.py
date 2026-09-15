# -*- coding: utf-8 -*-
"""Cuando cambia el TÍTULO de un formulario creado desde un libro (11/09/2026).

Google renombra la pestaña de respuestas si renombras el formulario. Aquí, al
guardar el formulario con otro título:

1. el archivo maestro de respuestas se rehace con la hoja interna llamada como
   el nuevo título (eso ya lo hacía `encuestas_hoja`), así que el vínculo debe
   apuntar a ese nombre nuevo (`origen_hoja`);
2. la pestaña del libro se renombra con el título (`destino_hoja`): en el acto
   si el libro está cerrado, o al cerrarse si está abierto (`vinculos_hoja`).

Antes de esto, cambiar el título rompía el vínculo en silencio: el origen ya no
tenía la hoja con el nombre viejo y las respuestas dejaban de llegar al libro
(caso de Wilson, 11/09 08:14, «Pruebas 1»).
"""
import logging

import almacen_bd as bd
import encuestas_hoja as hoja_mod
import formularios_nombres as nombres
import vinculos_hoja

log = logging.getLogger('almacen.formularios.titulo')


def al_cambiar_titulo(usuario, fila_encuesta, titulo_nuevo):
    """Alinea vínculos y pestaña del libro con el título nuevo. Nunca lanza."""
    try:
        _aplicar(usuario, fila_encuesta, titulo_nuevo)
    except Exception as excepcion:
        log.warning('título de %s: no se pudo alinear la hoja (%s)',
                    (fila_encuesta or {}).get('id'), excepcion)


def _aplicar(usuario, fila_encuesta, titulo_nuevo):
    ruta_respuestas = hoja_mod.ruta_de(fila_encuesta)
    if not ruta_respuestas:
        return
    from encuestas_excel import nombre_de_hoja
    from encuestas_modelo import plano
    from formularios_libro import hojas_del_libro

    hoja_origen = nombre_de_hoja(plano(titulo_nuevo))
    vinculos = bd.consultar(
        'SELECT * FROM vinculos_datos WHERE activo AND origen_ruta = %s',
        (ruta_respuestas,))
    for v in vinculos:
        # 1. El origen: la hoja interna del archivo maestro cambia de nombre.
        if v['origen_hoja'] != hoja_origen:
            bd.ejecutar('UPDATE vinculos_datos SET origen_hoja = %s WHERE id = %s',
                        (hoja_origen, v['id']))
        # 2. El destino: la pestaña del libro sigue al título.
        viejo = v['destino_hoja']
        usadas = hojas_del_libro(v['destino_usuario'], v['destino_ruta']) - {viejo}
        nuevo = nombres.hoja_libre(usadas, nombres.nombre_hoja(titulo_nuevo))
        if nuevo == viejo:
            continue
        if vinculos_hoja.libro_abierto(v['destino_usuario'], v['destino_ruta']):
            vinculos_hoja.programar_renombre(v['id'], viejo, nuevo)
            log.info('vínculo %s: libro abierto, «%s» → «%s» se aplicará al cerrar',
                     v['id'], viejo, nuevo)
        else:
            vinculos_hoja.renombrar_en_libro(v['destino_usuario'], v['destino_ruta'],
                                             viejo, nuevo)
            bd.ejecutar('UPDATE vinculos_datos SET destino_hoja = %s WHERE id = %s',
                        (nuevo, v['id']))
