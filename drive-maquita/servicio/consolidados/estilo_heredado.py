# -*- coding: utf-8 -*-
"""Que lo que escribe el consolidador no quede «sin formato».

El bloque consolidado crece cuando una matriz gana filas; las filas nuevas
caían en celdas que nunca tuvieron estilo y salían con la letra por defecto
(tamaño 10, sin alineación ni formato de número), distintas del resto de la
columna. Si la celda no tiene estilo, toma el de la celda de encima.
"""
from copy import copy


def heredar(pagina, fila, columna):
    if fila < 2:
        return
    celda = pagina.cell(row=fila, column=columna)
    if celda.has_style:
        return
    arriba = pagina.cell(row=fila - 1, column=columna)
    if arriba.has_style:
        celda._style = copy(arriba._style)
