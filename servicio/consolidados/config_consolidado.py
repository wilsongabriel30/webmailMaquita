# -*- coding: utf-8 -*-
"""Lee la tabla de configuración que el propio consolidado lleva dentro.

En Google, los consolidados de Planificación ASC no tenían las fuentes
escritas a mano en la fórmula: la hoja lleva una tabla (columnas B a G) que
dice, fuente por fuente, de qué archivo, de qué hoja y de qué rango sale cada
bloque. La fórmula `QUERY({IMPORTRANGE(C5;D5&"!A4:I178"); ...})` no era más
que la lectura de esa tabla.

Aquí se lee esa misma tabla. Así, cuando alguien añade un proyecto nuevo en la
hoja, el consolidado lo toma sin tocar código — la misma capacidad que daba
Google.

Estructura de la tabla:
    B  PROVINCIA           informativa; se hereda hacia abajo
    C  LINK                nombre del archivo fuente; se hereda hacia abajo
    D  PROYECTO / HOJA     hoja dentro del archivo fuente
    E  filas               "4-178"
    F  rango 1 columnas    "A-I"
    G  rango 2 columnas    "DH-GA"   (opcional)
"""
import re

COL_PROVINCIA, COL_ARCHIVO, COL_HOJA, COL_FILAS, COL_RANGO1, COL_RANGO2 = 2, 3, 4, 5, 6, 7

_RE_FILAS = re.compile(r'^\s*(\d+)\s*-\s*(\d+)\s*$')
_RE_COLS = re.compile(r'^\s*([A-Za-z]+)\s*-\s*([A-Za-z]+)\s*$')


class Fuente:
    """Un bloque de origen: archivo + hoja + rango."""

    def __init__(self, fila, provincia, archivo, hoja, rango):
        self.fila = fila
        self.provincia = provincia
        self.archivo = archivo
        self.hoja = hoja
        self.rango = rango

    def __repr__(self):
        return f'<Fuente fila={self.fila} {self.archivo}!{self.hoja}!{self.rango}>'


def _texto(valor):
    return str(valor).strip() if valor is not None else ''


def leer_fuentes(hoja_config, fila_inicio, fila_fin, columna_rango,
                 vacias_para_cortar=5):
    """Devuelve la lista de Fuente de una hoja de consolidado.

    `columna_rango` es COL_RANGO1 o COL_RANGO2 (los dos bloques que el
    consolidado arma con las mismas filas pero distintas columnas).
    Las filas incompletas se omiten: en la tabla hay filas de relleno.

    La tabla se lee ENTERA con `iter_rows`, no celda a celda: en una hoja
    abierta en modo `read_only`, pedir columnas en orden no creciente hace que
    `cell()` avance al siguiente registro y devuelva valores de OTRA fila. Ese
    desfase de una fila hacía que el consolidado tomara la matriz equivocada y
    se saltara la última fuente.
    """
    ancho = max(COL_RANGO2, columna_rango)
    filas_tabla = {}
    for celdas in hoja_config.iter_rows(min_row=fila_inicio, max_row=fila_fin,
                                        min_col=1, max_col=ancho):
        if not celdas:
            continue
        # Se indexa por el número de fila REAL de la celda, nunca por el orden
        # de iteración: en `read_only` openpyxl puede empezar a devolver antes
        # de `min_row` si la hoja declara mal sus dimensiones, y todo el mapeo
        # se corre una fila (el consolidado tomaría la matriz de al lado).
        filas_tabla[celdas[0].row] = [c.value for c in celdas]

    def celda(fila, columna):
        valores = filas_tabla.get(fila) or []
        return valores[columna - 1] if len(valores) >= columna else None

    fuentes, archivo_actual, provincia_actual = [], '', ''
    vacias_seguidas = 0

    for fila in range(fila_inicio, fila_fin + 1):
        if vacias_seguidas >= vacias_para_cortar:
            break                       # se acabó la tabla; abajo solo hay hoja en blanco

        archivo = _texto(celda(fila, COL_ARCHIVO))
        provincia = _texto(celda(fila, COL_PROVINCIA))
        # La tabla solo escribe el archivo en la primera fila de cada grupo:
        # las de abajo lo heredan (en Google era la referencia fija C5, C9…).
        if archivo:
            archivo_actual = archivo
        if provincia:
            provincia_actual = provincia

        hoja = _texto(celda(fila, COL_HOJA))
        filas = _RE_FILAS.match(_texto(celda(fila, COL_FILAS)))
        cols = _RE_COLS.match(_texto(celda(fila, columna_rango)))

        if not (archivo_actual and hoja and filas and cols):
            vacias_seguidas += 1
            continue
        vacias_seguidas = 0

        rango = (f'{cols.group(1).upper()}{filas.group(1)}:'
                 f'{cols.group(2).upper()}{filas.group(2)}')
        fuentes.append(Fuente(fila, provincia_actual, archivo_actual, hoja, rango))

    return fuentes
