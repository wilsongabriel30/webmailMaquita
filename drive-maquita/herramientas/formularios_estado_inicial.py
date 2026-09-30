#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Anota el estado inicial de las hojas de respuestas que aún no lo tienen.

Desde el 17/09/2026 la hoja vinculada ya no se rehace: se le añaden filas y
columnas (`encuestas_hoja_libro`). Para saber qué pregunta cambió de nombre hace
falta recordar su título anterior, y eso solo se sabe si el estado se anotó
ANTES de la edición. Este guion lo anota para todos los formularios con hoja.

No escribe ningún Excel. Se puede repetir: los que ya tienen estado se saltan.

Uso (VM 101, como `sistemas`, con el .env de Raíces cargado):
    cd /home/sistemas/almacen-maquita/servicio
    python ../herramientas/formularios_estado_inicial.py [--aplicar]
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'servicio'))

import encuestas_bd as ebd                      # noqa: E402
import encuestas_hoja as hoja_mod               # noqa: E402
import encuestas_hoja_libro as libro_mod        # noqa: E402
import encuestas_hoja_xml as xml_mod            # noqa: E402
import nucleo_archivos as nucleo                # noqa: E402
from api_encuestas import leer_definicion       # noqa: E402


def principal(aplicar):
    filas = ebd.bd.consultar("SELECT * FROM encuestas WHERE COALESCE(hoja_ruta, '') <> '' "
                             "ORDER BY creada_en")
    hechos = set()
    for fila in filas:
        etiqueta = '%s %s' % (fila['propietario'], fila['hoja_ruta'])
        try:
            definicion = leer_definicion(int(fila['propietario']), fila['ruta'])
            if not definicion or definicion['id'] in hechos:
                print('  salta (sin definición o repetida):', etiqueta)
                continue
            hechos.add(definicion['id'])
            if libro_mod.leer_estado(definicion['id']) is not None:
                print('  ya tiene estado:', etiqueta)
                continue
            fisica = nucleo.ruta_fisica(int(fila['propietario']), fila['hoja_ruta'])
            if not os.path.isfile(fisica):
                print('  sin archivo:', etiqueta)
                continue
            principal_fila = ebd.obtener(definicion['id']) or fila
            datos = hoja_mod.datos_de_hoja(principal_fila, definicion)
            encabezados, cuerpo = xml_mod.leer_tabla(open(fisica, 'rb').read())
            desplazamiento = len(datos['cabeceras']) - len(datos['listado'])
            titulos = {p['id']: datos['cabeceras'][desplazamiento + i]
                       for i, p in enumerate(datos['listado'])}
            hasta = libro_mod._hasta_deducido(encabezados, cuerpo, datos['enviadas'])
            preguntas = libro_mod._preguntas_deducidas(None, titulos, encabezados)
            pendientes = sum(1 for e in datos['enviadas'] if e and (hasta is None or e > hasta))
            print('  %s: %d/%d preguntas con columna, %d filas, %d respuestas por escribir'
                  % (etiqueta, len(preguntas), len(titulos), len(cuerpo), pendientes))
            if aplicar:
                libro_mod.guardar_estado(definicion['id'], hasta, preguntas)
        except xml_mod.SinTabla:
            print('  sin tabla «Respuestas»:', etiqueta)
        except Exception as excepcion:
            print('  ERROR %s: %s' % (etiqueta, excepcion))


if __name__ == '__main__':
    principal('--aplicar' in sys.argv)
