# -*- coding: utf-8 -*-
"""
Las rayas de la tabla: cuáles hay y cómo se redibujan.
======================================================

Es la parte que más cuidado pide: solo se dibujan las rayas que el documento
tenía de verdad, porque el reconocimiento inventa filas donde solo hay
renglones de texto y trazarlas dejaba el texto tachado.

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


from . import tablas_escritura as escritura
from . import tablas_estilo_rayas
from .tablas_base import TOLERANCIA_RAYA

logger = logging.getLogger(__name__)


def _rayas_dibujadas(pagina):
    """Dónde hay rayas DE VERDAD en la página: (horizontales, verticales).

    Se mira una sola vez y se recuerda en la propia página: en cuanto se borra
    una zona para redibujarla, sus rayas ya no están, y preguntar otra vez daría
    una respuesta falsa.
    """
    # El recuerdo se guarda en el DOCUMENTO, no en la página. Motivo: algunas
    # operaciones vuelven a pedir la página con `documento[n-1]` y PyMuPDF
    # devuelve un objeto distinto; si el recuerdo colgara de la página, se
    # perdería justo antes de redibujar y la tabla se quedaría sin una sola raya
    # (defecto encontrado en la auditoría del 29-jul-2026: arrastrar el alto de
    # una fila dejaba la tabla desnuda).
    documento = pagina.parent
    numero = pagina.number
    memoria = getattr(documento, '_faro_rayas_por_pagina', None)
    if memoria is None:
        memoria = {}
        documento._faro_rayas_por_pagina = memoria
    recordado = memoria.get(numero)
    if recordado is not None:
        return recordado

    horizontales, verticales = set(), set()
    try:
        for dibujo in pagina.get_drawings():
            con_trazo = 's' in (dibujo.get('type') or '')
            for trazo in dibujo.get('items') or []:
                if trazo[0] == 'l':
                    inicio, fin = trazo[1], trazo[2]
                    if abs(fin.y - inicio.y) < 1.2 and abs(fin.x - inicio.x) > 12:
                        horizontales.add(round((inicio.y + fin.y) / 2, 1))
                    elif abs(fin.x - inicio.x) < 1.2 and abs(fin.y - inicio.y) > 8:
                        verticales.add(round((inicio.x + fin.x) / 2, 1))
                elif trazo[0] == 're':
                    caja = fitz.Rect(trazo[1])
                    if caja.height < 1.2 and caja.width > 12:
                        horizontales.add(round((caja.y0 + caja.y1) / 2, 1))
                    elif caja.width < 1.2 and caja.height > 8:
                        verticales.add(round((caja.x0 + caja.x1) / 2, 1))
                    elif caja.width > 12 and caja.height > 8 and con_trazo:
                        # Un recuadro CON BORDE: sus cuatro lados son rayas. Si
                        # es de puro relleno —las celdas con fondo de color de
                        # una cotización— no pinta ninguna línea, y tomar sus
                        # lados por rayas hacía que se trazaran encima del texto
                        # (caso real: «W11PRO BLACK 3YB» y «Windows 11 Home»
                        # salían tachados).
                        horizontales.update((round(caja.y0, 1), round(caja.y1, 1)))
                        verticales.update((round(caja.x0, 1), round(caja.x1, 1)))
    except Exception:
        logger.debug('no se pudo mirar dónde hay rayas', exc_info=True)

    memoria[numero] = (horizontales, verticales)
    return horizontales, verticales


def _hay_raya_en(valor, sitios):
    return any(abs(valor - sitio) <= TOLERANCIA_RAYA for sitio in sitios)


def _estirar(valor, viejos, nuevos):
    """Dónde cae ahora un punto que antes estaba en `valor`.

    La tabla cambia de medidas —una columna se ensancha, una fila se hace más
    alta— y los tramos de las rayas tienen que acompañarla. Se busca entre qué
    dos bordes caía el punto y se le da el mismo sitio proporcional entre los
    bordes nuevos. Fuera de la tabla, se acompaña al borde más cercano.
    """
    if not viejos or not nuevos or len(viejos) != len(nuevos):
        return valor
    if valor <= viejos[0]:
        return nuevos[0] + (valor - viejos[0])
    if valor >= viejos[-1]:
        return nuevos[-1] + (valor - viejos[-1])
    for indice in range(len(viejos) - 1):
        principio, final = viejos[indice], viejos[indice + 1]
        if principio <= valor <= final:
            ancho = final - principio
            if ancho <= 0:
                return nuevos[indice]
            parte = (valor - principio) / ancho
            return nuevos[indice] + parte * (nuevos[indice + 1] - nuevos[indice])
    return valor


def _piezas_de(estilos, cuales, sitio, bordes_viejos, bordes_nuevos, defecto):
    """Qué trazos hay que dar para esa raya: [(estilo, tramos), ...].

    Cada trozo con **su** color y **su** grosor: a la altura de una fila puede
    haber una línea negra a la izquierda y un sombreado claro a la derecha, y
    pintarlo todo de un color hacía desaparecer la línea.
    """
    piezas = tablas_estilo_rayas.piezas_en(estilos, cuales, sitio)
    if not piezas:
        return [(defecto, [(bordes_nuevos[0], bordes_nuevos[-1])])]
    salida = []
    for color, grosor, tramos in piezas:
        estirados = []
        for desde, hasta in tramos:
            nuevo_desde = _estirar(desde, bordes_viejos, bordes_nuevos)
            nuevo_hasta = _estirar(hasta, bordes_viejos, bordes_nuevos)
            if nuevo_hasta - nuevo_desde > 0.5:
                estirados.append((nuevo_desde, nuevo_hasta))
        if estirados:
            salida.append(((color, grosor), estirados))
    return salida or [(defecto, [(bordes_nuevos[0], bordes_nuevos[-1])])]


def _tramos_de(estilos, cuales, sitio, bordes_viejos, bordes_nuevos):
    """Por dónde hay que trazar esa raya, con la geometría de ahora.

    Se reproducen los tramos que tenía —una tabla de verdad no lleva las rayas
    de lado a lado: la rejilla de los artículos acaba a media hoja y la de los
    totales solo ocupa las últimas columnas—, estirados a las medidas nuevas. Si
    la raya no existía antes (la de una columna recién agregada), se traza
    entera, que es lo único que se puede hacer.
    """
    tramos = tablas_estilo_rayas.tramos_en(estilos, cuales, sitio)
    if not tramos:
        return [(bordes_nuevos[0], bordes_nuevos[-1])]
    salida = []
    for desde, hasta in tramos:
        nuevo_desde = _estirar(desde, bordes_viejos, bordes_nuevos)
        nuevo_hasta = _estirar(hasta, bordes_viejos, bordes_nuevos)
        if nuevo_hasta - nuevo_desde > 0.5:
            salida.append((nuevo_desde, nuevo_hasta))
    return salida or [(bordes_nuevos[0], bordes_nuevos[-1])]


def _trazar_rejilla(pagina, columnas, filas, grosor, color_raya,
                    columnas_previas=None, filas_previas=None):
    """Dibuja la rejilla, pero solo las rayas que el documento ya tenía.

    El reconocimiento de tablas deduce filas del propio texto cuando no hay
    rayas que separar (en la cotización de Alliance Tech se inventaba una por
    renglón). Si se trazaran, el texto quedaría tachado. Aquí se comprueba raya
    por raya.

    `columnas_previas` y `filas_previas` son las coordenadas ANTES de la
    operación: cuando una raya se ha movido —arrastrar el ancho o el alto— hay
    que preguntar por el sitio donde estaba, no por el nuevo. Si no se dan, se
    entiende que la geometría no ha cambiado.
    """
    horizontales, verticales = _rayas_dibujadas(pagina)
    antes_columnas = (columnas_previas
                      if columnas_previas and len(columnas_previas) == len(columnas)
                      else columnas)
    antes_filas = (filas_previas
                   if filas_previas and len(filas_previas) == len(filas)
                   else filas)

    # Cada raya se redibuja con EL SUYO: el color y el grosor con los que estaba
    # dibujada en el sitio de donde viene. Antes se pintaban todas con un único
    # estilo y una tabla con recuadro grueso, rayas finas dentro y un separador
    # de color salía después con todo igual — «se cambia totalmente el estilo».
    # (18-ago-2026.)
    estilos = tablas_estilo_rayas.leer(pagina)
    # Para una raya NUEVA —la de una columna recién agregada— se usa el estilo
    # más repetido de la tabla, que es el de las rayas de dentro; el que llega
    # por parámetro queda de última red.
    defecto = estilos.get('defecto') or (color_raya, grosor)
    por_estilo = {}

    def apuntar(estilo, desde, hasta):
        por_estilo.setdefault(estilo, []).append((desde, hasta))

    for indice, x in enumerate(columnas):
        if not _hay_raya_en(antes_columnas[indice], verticales):
            continue
        for estilo, tramos in _piezas_de(estilos, 'verticales',
                                         antes_columnas[indice],
                                         antes_filas, filas, defecto):
            for desde, hasta in tramos:
                apuntar(estilo, fitz.Point(x, desde), fitz.Point(x, hasta))
    for indice, y in enumerate(filas):
        if not _hay_raya_en(antes_filas[indice], horizontales):
            continue
        for estilo, tramos in _piezas_de(estilos, 'horizontales',
                                         antes_filas[indice],
                                         antes_columnas, columnas, defecto):
            for desde, hasta in tramos:
                apuntar(estilo, fitz.Point(desde, y), fitz.Point(hasta, y))

    # Cada raya, en su propio trazo. Agrupar varias en uno solo (que es lo que
    # se hacía) las volvía invisibles para el reconocimiento de tablas: al
    # mirar el documento otra vez, PyMuPDF veía un único dibujo grande en vez de
    # las rayas, no encontraba la rejilla y deducía las columnas del texto. La
    # tabla aguantaba una operación, y a la segunda se deshacía —los fondos
    # desaparecían y quedaba solo el recuadro de fuera—. (18-ago-2026.)
    # De lo más claro a lo más oscuro: donde dos trozos se pisan —una línea
    # negra y un sombreado clarito a la misma altura— tiene que quedar encima el
    # oscuro, o la línea se vería apagada.
    def _claridad(par):
        color = par[0][0] or (0, 0, 0)
        return -sum(color)

    for (color_suyo, grosor_suyo), segmentos in sorted(por_estilo.items(),
                                                       key=_claridad):
        for desde, hasta in segmentos:
            pagina.draw_line(desde, hasta, color=color_suyo, width=grosor_suyo)


def _estilo_de_las_rayas(pagina, recuadro):
    """Grosor y color de las líneas de la tabla, para redibujarlas igual.

    Se aprovecha para anotar de paso si la tabla tiene rayas dibujadas: esto se
    llama siempre al empezar la operación, que es cuando todavía se puede saber.
    """
    _rayas_dibujadas(pagina)      # se anota ahora, que la tabla está entera
    # Y con ellas, el color y el grosor de CADA una: después de borrar la zona
    # ya no habría a quién preguntárselo.
    tablas_estilo_rayas.leer(pagina)
    grosores, colores = [], []
    try:
        for dibujo in pagina.get_drawings():
            if not fitz.Rect(dibujo['rect']).intersects(recuadro):
                continue
            if dibujo.get('width'):
                grosores.append(dibujo['width'])
            if dibujo.get('color'):
                colores.append(tuple(dibujo['color']))
    except Exception:
        pass
    grosor = min(grosores) if grosores else 0.75
    color = max(set(colores), key=colores.count) if colores else (0, 0, 0)
    return max(0.3, min(2.0, grosor)), color


def _zona_a_borrar(pagina, columnas, filas):
    """El recuadro que se borra: la tabla vieja **y** donde va a estar la nueva."""
    return fitz.Rect(columnas[0], filas[0], columnas[-1], filas[-1])


def _borrar_zona(pagina):
    """Aplica las marcas de borrado de la tabla, con el mismo criterio siempre.

    Las IMÁGENES se quitan enteras (`PDF_REDACT_IMAGE_REMOVE`) en vez de
    blanquearles los píxeles que caen dentro, que era lo que hacía PyMuPDF por
    su cuenta: así una imagen que solo asoma por la tabla no queda cortada por
    la mitad. Quien llama las ha leído antes con `tablas_imagenes.leer` y las
    vuelve a colocar acto seguido, así que no se pierde ninguna.
    """
    try:
        pagina.apply_redactions(images=fitz.PDF_REDACT_IMAGE_REMOVE,
                                graphics=fitz.PDF_REDACT_LINE_ART_REMOVE_IF_TOUCHED)
    except (TypeError, AttributeError):
        # PyMuPDF anterior: sin control del dibujo vectorial ni de las imágenes
        try:
            pagina.apply_redactions(graphics=fitz.PDF_REDACT_LINE_ART_REMOVE_IF_TOUCHED)
        except (TypeError, AttributeError):
            pagina.apply_redactions()


# ── EL MOTOR: borrar y volver a dibujar ──────────────────────────────────
def _redibujar(pagina, documento, cliente, renglones, columnas, filas, grosor,
               color_raya, desplazamientos=None, extra=None, previas=None,
               fondos=None, mapa_columnas=None, mapa_filas=None, imagenes=None):
    """Borra la zona de la tabla y la vuelve a dibujar con la geometría nueva.

    `renglones` ya trae en cada uno su columna de destino (`destino`) y su
    resolución de escritura, decidida ANTES de borrar. `extra` son textos
    nuevos a escribir: (columna, base, texto, alineacion, resolucion, estilo).

    `fondos` son los colores de relleno que el llamador leyó ANTES de borrar
    (`tablas_fondos.leer`), con los mapas de a qué fila y columna nuevas va
    cada vieja. Sin ellos, el borrado deja la tabla en blanco: la cabecera de
    color se pierde y su letra blanca se vuelve invisible.

    `imagenes` es lo mismo para los logotipos, firmas y fotos que hubiera dentro
    (`tablas_imagenes.leer`): sin ellas el borrado se las llevaba y lo único que
    se hacía era avisar de que se perdían.
    """
    zona = fitz.Rect(columnas[0], filas[0], columnas[-1], filas[-1])
    anterior = pagina.rect  # solo para dejar claro que no se toca el resto
    del anterior

    anotacion = pagina.add_redact_annot(_zona_a_borrar(pagina, columnas, filas))
    anotacion.update()
    _borrar_zona(pagina)

    # El color primero: va por debajo de las rayas y del texto.
    if fondos is not None:
        fondos.pintar(pagina, columnas, filas, mapa_columnas, mapa_filas)
    # Las imágenes, sobre el color y bajo las rayas y las letras.
    if imagenes is not None:
        imagenes.pintar(pagina, columnas, filas, mapa_columnas, mapa_filas)

    _trazar_rejilla(pagina, columnas, filas, grosor, color_raya,
                    *(previas or (None, None)))

    apretados = 0
    for renglon in renglones:
        if renglon.get('destino') is None or not renglon.get('resolucion'):
            continue
        dy = (desplazamientos or {}).get(renglon.get('fila'), 0.0)
        if escritura.escribir_renglon(pagina, cliente, renglon, columnas, dy):
            apretados += 1

    for pieza in (extra or []):
        if escritura.escribir(pagina, cliente, pieza['resolucion'], pieza['estilo'],
                              pieza['texto'], columnas[pieza['columna']],
                              columnas[pieza['columna'] + 1], pieza['base'],
                              pieza.get('alineacion', 'centro')):
            apretados += 1
    del zona
    return apretados



def _preparar(documento, pagina, cliente, renglones, mapa, columnas_nuevas):
    """Decide con qué letra se reescribe cada renglón. ANTES de borrar nada."""
    for renglon in renglones:
        renglon['destino'] = mapa.get(renglon['columna']) if mapa is not None \
            else renglon['columna']
        if renglon['destino'] is None:
            continue
        renglon['resolucion'] = cliente._resolver_escritura(
            documento, pagina, renglon['estilo'], renglon['texto'],
            renglon['texto'], renglon['rect'].width, ajustar_tam=False)
    del columnas_nuevas



def _avisos(apretados, imagenes=None):
    """El aviso que se le devuelve al usuario tras redibujar la tabla.

    `imagenes` es el juego devuelto por `tablas_imagenes.leer` DESPUÉS de
    pintarlo. Desde el 17-08-2026 las imágenes se conservan, así que ya no se
    avisa de que se pierden: solo se dice algo en el caso raro de que alguna no
    se haya podido volver a colocar.
    """
    avisos = []
    if apretados:
        avisos.append('%d renglón(es) se ajustaron para caber' % apretados)
    perdidas = getattr(imagenes, 'perdidas', 0)
    if perdidas:
        avisos.append('%d imagen(es) de la tabla no se pudieron conservar'
                      % perdidas)
    return '; '.join(avisos)
