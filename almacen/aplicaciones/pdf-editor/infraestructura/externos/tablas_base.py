# -*- coding: utf-8 -*-
"""
Lo básico de las tablas: medidas de referencia y lectura de bordes.
=================================================================

Lo que necesitan TODOS los módulos de tablas. Está aparte para que ninguno
tenga que importar a otro que a su vez lo importe a él: esta capa no depende
de ninguna de las demás.

Se separó de `tablas_pdf.py` el 29-jul-2026, al partir aquel archivo de 1.322
líneas en módulos con una sola responsabilidad.

Autoría: Equipo de Tecnología Maquita
"""

import collections
import threading

import fitz


# Aire mínimo que se le deja al texto por debajo, al comprimir una fila
RESPIRO = 0.5

# Distancia de seguridad que NO se invade al crecer hacia abajo
SEGURIDAD_ABAJO = 2.0

# Alto por defecto de una fila nueva, si no hay de dónde deducirlo
ALTO_FILA_POR_DEFECTO = 14.0

# Por debajo de esto una fila ya no da para escribir nada
MINIMO_FILA = 9.0

# Reconocer las tablas de una página cuesta cerca de un segundo, y el editor lo
# vuelve a pedir después de cada edición y al cambiar el zoom. La respuesta
# depende SOLO del contenido del PDF, así que se recuerda por huella: si el
# documento no cambió, se responde al instante. (Pedido del 28-jul-2026.)
_CACHE_DETECTAR = collections.OrderedDict()

_CACHE_DETECTAR_MAXIMO = 24

# Reconocimientos en marcha: si el servidor ya empezó a mirar ese mismo PDF
# (porque se adelantó al terminar la edición), la petición del editor espera a
# que acabe en vez de calcular lo mismo por segunda vez.
_EN_CURSO = {}

_CANDADO = threading.Lock()

ESPERA_MAXIMA = 20.0

# Cuánto puede desviarse una raya del sitio donde el reconocimiento la coloca
# para seguir considerándose la misma. El grosor de las rayas y el redondeo de
# las coordenadas dan diferencias de décimas.
TOLERANCIA_RAYA = 2.0


def _cliente():
    from .cliente_pymupdf import ClientePyMuPDF
    return ClientePyMuPDF()



class _TablaConocida(object):
    """La geometría de una tabla que ya se reconoció antes.

    Guarda solo lo que usan las operaciones —las rayas— para no repetir el
    reconocimiento, que es lo más caro de todo (1,7 s de los 2,4 que tardaba
    guardar una celda). Pedido del usuario: «ayúdame con el tiempo de guardado»
    (28-jul-2026).
    """
    __slots__ = ('columnas', 'filas_y', 'bbox')

    def __init__(self, datos):
        self.columnas = list(datos['columnas'])
        self.filas_y = list(datos['filas_y'])
        self.bbox = list(datos['bbox'])



def _fusionar_pegados(cuenta, minimo):
    """Bordes a menos de `minimo` puntos, fusionados en uno.

    Una «columna» de 4 pt no puede contener texto: es la raya gruesa de un
    escaneo digitalizado vista como dos rayas. Editar la primera celda de una
    cotización escribía el texto letra a letra, en vertical, dentro de esa
    astilla (vídeo del 20-ago-2026). De cada par pegado se conserva el borde
    que comparten más celdas, que es la raya de verdad; el otro es el eco.
    """
    fusionados = []
    for borde in sorted(cuenta):
        if fusionados and borde - fusionados[-1] < minimo:
            if cuenta[borde] > cuenta[fusionados[-1]]:
                fusionados[-1] = borde
        else:
            fusionados.append(borde)
    return fusionados


def _bordes_de_columna(tabla):
    """Las x de las rayas verticales, de izquierda a derecha y sin repetidas."""
    if isinstance(tabla, _TablaConocida):
        return list(tabla.columnas)
    cuenta = {}
    for fila in tabla.rows:
        for celda in (fila.cells or []):
            if celda:
                for x in (round(celda[0], 1), round(celda[2], 1)):
                    cuenta[x] = cuenta.get(x, 0) + 1
    return _fusionar_pegados(cuenta, 5.0)



def _bordes_de_fila(tabla):
    """Las y de las rayas horizontales."""
    if isinstance(tabla, _TablaConocida):
        return list(tabla.filas_y)
    cuenta = {}
    for fila in tabla.rows:
        for celda in (fila.cells or []):
            if celda:
                for y in (round(celda[1], 1), round(celda[3], 1)):
                    cuenta[y] = cuenta.get(y, 0) + 1
    return _fusionar_pegados(cuenta, 4.0)
