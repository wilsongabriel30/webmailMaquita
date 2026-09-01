# -*- coding: utf-8 -*-
"""
Cuentas de la tabla: bordes, anchos y altos.
============================================

Aquí no se toca el PDF: son solo números. Se separó de `tablas_pdf` porque
no depende de nada y así puede probarse y leerse sin arrastrar PyMuPDF.

Se separó de `tablas_pdf.py` el 29-jul-2026: aquel archivo había
llegado a 1.322 líneas y 48 funciones, y su tamaño ya costó un fallo
(una función duplicada que nadie vio). Cada módulo tiene ahora una
sola responsabilidad.

Autoría: Equipo de Tecnología Maquita
"""

import collections
import copy
import hashlib
import logging
import threading

import fitz

from . import cache_tablas
from . import guardado_pdf
from . import tablas_escritura as escritura


from .tablas_base import (ALTO_FILA_POR_DEFECTO, MINIMO_FILA,
                          RESPIRO)

logger = logging.getLogger(__name__)


def _indice_en(valor, bordes):
    for i in range(len(bordes) - 1):
        if bordes[i] <= valor <= bordes[i + 1]:
            return i
    return None


def _alineacion(rect, izquierda, derecha):
    """izquierda · centro · derecha, según dónde se apoya el renglón."""
    hueco_izquierdo = rect.x0 - izquierda
    hueco_derecho = derecha - rect.x1
    if abs(hueco_izquierdo - hueco_derecho) <= max(2.0, (derecha - izquierda) * 0.06):
        return 'centro'
    return 'derecha' if hueco_derecho < hueco_izquierdo else 'izquierda'


def _acumular(inicio, anchos):
    bordes, x = [inicio], inicio
    for ancho in anchos:
        x += ancho
        bordes.append(x)
    return bordes


def _mapa_de_columnas(accion, posicion, total_viejo):
    """A qué columna nueva va cada columna vieja (None = desaparece)."""
    mapa = {}
    for vieja in range(total_viejo):
        if accion == 'insertar':
            mapa[vieja] = vieja if vieja < posicion else vieja + 1
        elif vieja != posicion:
            mapa[vieja] = vieja if vieja < posicion else vieja - 1
    return mapa


def _aire_de_cada_fila(renglones, filas):
    """Espacio SIN TEXTO al final de cada fila: es de donde se puede recortar."""
    aire = []
    for i in range(len(filas) - 1):
        dentro = [r for r in renglones if r['fila'] == i]
        fondo = max((r['rect'].y1 for r in dentro), default=filas[i])
        aire.append(max(0.0, filas[i + 1] - fondo - RESPIRO))
    return aire


# ── GEOMETRÍA ────────────────────────────────────────────────────────────
def columnas_tras_insertar(bordes, posicion):
    """Bordes nuevos al meter una columna en `posicion` (0 = antes de la 1ª).

    La tabla NO cambia de ancho: las columnas se aprietan para hacerle sitio a
    la nueva, que nace con el ancho medio. Así se respetan los márgenes.
    """
    anchos = [bordes[i + 1] - bordes[i] for i in range(len(bordes) - 1)]
    total = sum(anchos)
    nuevo = total / (len(anchos) + 1)
    factor = (total - nuevo) / total
    anchos = [a * factor for a in anchos]
    anchos.insert(max(0, min(posicion, len(anchos))), nuevo)
    return _acumular(bordes[0], anchos)


def columnas_tras_eliminar(bordes, posicion):
    """Bordes nuevos al quitar la columna `posicion`; el hueco se reparte."""
    anchos = [bordes[i + 1] - bordes[i] for i in range(len(bordes) - 1)]
    if len(anchos) <= 1:
        raise ValueError('No se puede quitar la única columna de la tabla.')
    posicion = max(0, min(posicion, len(anchos) - 1))
    total = sum(anchos)
    sobra = anchos.pop(posicion)
    resto = total - sobra
    if resto > 0:
        anchos = [a + sobra * (a / resto) for a in anchos]
    return _acumular(bordes[0], anchos)


def filas_tras_insertar(filas, posicion, renglones, sitio_abajo):
    """Bordes de fila nuevos al meter una fila, y cuánto se desplaza cada una.

    La tabla crece hacia abajo si hay sitio; si no lo hay —el caso real de la
    proforma, con 1,6 pt hasta el párrafo siguiente— se hace hueco recortando
    el **aire** que sobra al final de las filas, nunca el texto. Si ni así cabe,
    se dice claramente en vez de pisar lo que hay debajo.
    """
    altos = [filas[i + 1] - filas[i] for i in range(len(filas) - 1)]
    if not altos:
        raise ValueError('La tabla no tiene filas.')
    posicion = max(0, min(posicion, len(altos)))

    # Alto deseado: el de la fila de datos más baja (sin contar la de los
    # encabezados), que es lo que hace que "parezca" una fila más de las mismas.
    candidatas = sorted(altos[1:] or altos)
    deseado = max(MINIMO_FILA, min(30.0, candidatas[0] if candidatas
                                   else ALTO_FILA_POR_DEFECTO))

    aire = _aire_de_cada_fila(renglones, filas)
    disponible = max(0.0, sitio_abajo) + sum(aire)
    if disponible + 0.01 < MINIMO_FILA:
        raise ValueError(
            'No hay sitio para otra fila en esta página: la tabla llega hasta el '
            'contenido de abajo y las filas no tienen espacio de sobra. Puedes '
            'quitar una fila que no uses, o agregar el ítem en otra página.')

    # Si no cabe la fila "de tamaño natural", se hace una más baja antes que
    # rendirse: sigue siendo legible y es lo que el usuario espera que pase.
    alto_nuevo = min(deseado, disponible)

    del_espacio_libre = min(alto_nuevo, max(0.0, sitio_abajo))
    falta = alto_nuevo - del_espacio_libre

    recortes = [0.0] * len(altos)
    if falta > 0.01:
        total_aire = sum(aire)
        # Se recorta en proporción al aire que tiene cada fila: las holgadas
        # ceden más y ninguna queda con el texto pegado a la raya.
        for i, sobra in enumerate(aire):
            recortes[i] = falta * (sobra / total_aire) if total_aire else 0.0

    nuevos_altos = [altos[i] - recortes[i] for i in range(len(altos))]
    nuevos_altos.insert(posicion, alto_nuevo)
    bordes = _acumular(filas[0], nuevos_altos)

    # Cuánto baja (o sube) el texto de cada fila vieja
    desplazamientos = {}
    for vieja in range(len(altos)):
        nueva = vieja if vieja < posicion else vieja + 1
        desplazamientos[vieja] = bordes[nueva] - filas[vieja]
    return bordes, desplazamientos, posicion


def filas_tras_eliminar(filas, posicion):
    """Bordes de fila al quitar una: las de abajo suben y la tabla se acorta."""
    altos = [filas[i + 1] - filas[i] for i in range(len(filas) - 1)]
    if len(altos) <= 1:
        raise ValueError('No se puede quitar la única fila de la tabla.')
    posicion = max(0, min(posicion, len(altos) - 1))
    quitado = altos.pop(posicion)
    bordes = _acumular(filas[0], altos)
    desplazamientos = {}
    for vieja in range(len(altos) + 1):
        if vieja == posicion:
            continue
        nueva = vieja if vieja < posicion else vieja - 1
        desplazamientos[vieja] = bordes[nueva] - filas[vieja]
    return bordes, desplazamientos, quitado


# ── OPERACIÓN: MOVER DE SITIO ────────────────────────────────────────────
def _permutar(medidas, desde, hasta):
    """Lista de medidas con el elemento `desde` llevado a `hasta`."""
    if not (0 <= desde < len(medidas)) or not (0 <= hasta < len(medidas)):
        raise ValueError('Esa posición no existe en la tabla.')
    if desde == hasta:
        raise ValueError('Ya está en ese sitio.')
    copia = list(medidas)
    copia.insert(hasta, copia.pop(desde))
    return copia


def _mapa_permutacion(total, desde, hasta):
    """A qué posición nueva va cada posición vieja tras mover una."""
    orden = list(range(total))
    orden.insert(hasta, orden.pop(desde))
    return {viejo: nuevo for nuevo, viejo in enumerate(orden)}


def _filas_previas(filas, nuevas_filas, posicion, accion):
    """Las coordenadas de antes, alineadas una a una con las de ahora.

    Al meter una fila, su raya no tiene pasado: se le presta la del borde donde
    nace, para que se dibuje si ese borde existía. Al quitar una, sobra la suya.
    Si las listas no casan de ninguna forma, se devuelve None y se dibuja como
    siempre.
    """
    if len(nuevas_filas) == len(filas):
        return list(filas)
    if len(nuevas_filas) == len(filas) + 1:
        sitio = max(0, min(int(posicion) + 1, len(filas)))
        prestada = filas[min(sitio, len(filas) - 1)]
        return list(filas[:sitio]) + [prestada] + list(filas[sitio:])
    if len(nuevas_filas) == len(filas) - 1:
        sitio = max(0, min(int(posicion) + 1, len(filas) - 1))
        return list(filas[:sitio]) + list(filas[sitio + 1:])
    return None
