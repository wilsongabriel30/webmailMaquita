# -*- coding: utf-8 -*-
"""Devuelve a pendiente lo que el estado da por escrito y NO está en el archivo.

Es la revisión del cierre del editor aplicada de una pasada a TODOS los
formularios con hoja vinculada: repara los que se quedaron con respuestas
perdidas antes del arreglo del 22/09/2026.

Uso:  python reparar_estado_hojas.py [--aplicar]
"""
import os
import sys

sys.path.insert(0, '/home/sistemas/almacen-maquita/servicio')

import encuestas_bd as ebd
import encuestas_hoja as hoja_mod
import encuestas_hoja_confirmacion as confirmacion
import encuestas_hoja_libro as libro
import nucleo_archivos as nucleo
from api_encuestas import leer_definicion

aplicar = '--aplicar' in sys.argv
filas = ebd.bd.consultar("SELECT * FROM encuestas WHERE hoja_ruta IS NOT NULL "
                         "AND hoja_ruta <> '' ORDER BY actualizada_en DESC")
print('formularios con hoja vinculada:', len(filas))
for fila in filas:
    estado = libro.leer_estado(fila['id'])
    if not estado or not estado['hasta']:
        continue
    try:
        fisica = nucleo.ruta_fisica(int(fila['propietario']), fila['hoja_ruta'])
    except Exception:
        continue
    if not os.path.isfile(fisica):
        continue
    definicion = leer_definicion(int(fila['propietario']), fila['ruta'])
    if definicion is None:
        continue
    enviadas = hoja_mod.datos_de_hoja(fila, definicion)['enviadas']
    if not enviadas:
        continue
    real = confirmacion.ultima_escrita(open(fisica, 'rb').read(), enviadas)
    if real is False or real == estado['hasta']:
        continue
    faltan = sum(1 for e in enviadas if e and e > (real or e.min.replace(tzinfo=e.tzinfo)))
    print('  %-45s hasta=%s  real=%s  (%d respuestas sin escribir)'
          % (str(fila['titulo'])[:45], estado['hasta'], real, faltan))
    if aplicar:
        libro.guardar_estado(fila['id'], real, estado['preguntas'])
        hoja_mod.refrescar_al_editar(fila, definicion)
        print('     -> devuelto a pendiente y lanzado el refresco')
