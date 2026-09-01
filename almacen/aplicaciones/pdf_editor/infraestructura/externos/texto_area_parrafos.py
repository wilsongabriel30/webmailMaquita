# -*- coding: utf-8 -*-
"""
Un recuadro de texto corrido sale por PÁRRAFOS; uno con columnas, tal cual.

El 31-jul-2026 se pidió que el recuadro saliera «tal cual está escrito», para
que una tabla conserve sus columnas. Pero un párrafo de seis renglones salía
también como seis renglones sueltos, y al pegarlo había que juntarlos a mano
(pedido del 21-ago-2026). Aquí se decide cuál de las dos cosas es el recuadro:

- **Texto corrido**: en casi ningún renglón hay un hueco de columna (un espacio
  de más de tres letras entre dos palabras). Se recompone por párrafos: los
  renglones se unen con un espacio, el guion de corte se resuelve y un párrafo
  nuevo empieza con un salto vertical grande, una sangría, una viñeta o tras un
  renglón corto acabado en punto.
- **Columnas**: se deja a `texto_area._componer`, que coloca cada palabra en su
  sitio.
"""
from . import texto_parrafos

HUECO_DE_COLUMNA = 3.0     # letras de separación que ya son «otra columna»
PROPORCION_CORRIDA = 0.8   # renglones sin huecos para considerarlo texto corrido


def _tiene_hueco(fila, ancho_letra):
    fila = sorted(fila, key=lambda p: p[0])
    return any(b[0] - a[2] > ancho_letra * HUECO_DE_COLUMNA
               for a, b in zip(fila, fila[1:]))


def es_texto_corrido(renglones, ancho_letra):
    """`renglones` son [centro, [palabras]] como los arma `texto_area`."""
    if len(renglones) < 2:
        return False
    sin_hueco = sum(1 for _c, fila in renglones if not _tiene_hueco(fila, ancho_letra))
    return sin_hueco >= len(renglones) * PROPORCION_CORRIDA


def como_parrafos(renglones, ancho_letra):
    """Los renglones recompuestos en párrafos, con la misma regla que la hoja entera."""
    lineas = []
    for _centro, fila in renglones:
        fila = sorted(fila, key=lambda p: p[0])
        lineas.append({
            'texto': ' '.join(p[4] for p in fila),
            'x0': min(p[0] for p in fila), 'x1': max(p[2] for p in fila),
            'y0': min(p[1] for p in fila), 'y1': max(p[3] for p in fila),
            'cuerpo': max(p[3] - p[1] for p in fila) or ancho_letra * 2,
        })
    ancho = texto_parrafos._ancho_de_columna(lineas)
    saltos = sorted(b['y0'] - a['y1'] for a, b in zip(lineas, lineas[1:]))
    interlineado = saltos[len(saltos) // 2] + lineas[0]['cuerpo'] if saltos else None
    parrafos, actual, anterior = [], '', None
    for linea in lineas:
        if anterior is not None and texto_parrafos._es_parrafo_nuevo(
                anterior, linea, ancho, interlineado):
            parrafos.append(actual)
            actual = ''
        actual = texto_parrafos._unir(actual, linea['texto'])
        anterior = linea
    if actual:
        parrafos.append(actual)
    return texto_parrafos._juntar(parrafos)
