# -*- coding: utf-8 -*-
"""
Las RAYAS del escaneo: encontrarlas en la imagen para no perder las tablas.
===========================================================================

Cuando se digitaliza un documento, `ocr_pagina_texto` rehace la página
escribiendo el texto reconocido con letra de verdad y **sin la imagen encima**,
que es lo que permite editarla. Pero al quitar la imagen se iban también las
rayas, y una tabla sin rayas deja de ser una tabla: `pdf2docx` no la reconstruye
y el editor no la detecta —de hecho `tablas_deteccion` tiene escrito que a los
documentos salidos del OCR no hay que deducirles tablas, porque «no tienen ni
una raya» y sus columnas serían un espejismo (31-07-2026)—.

Resultado: el usuario avisó el 17-08-2026 de que «el digitalizar y OCR no
reconoce tablas». Y no era un fallo de reconocimiento: es que las rayas se
quedaban por el camino.

Aquí se buscan en la propia imagen escaneada, antes de tirarla. No se inventa
nada: se dibujan **las rayas que están en el papel**, con lo cual la tabla que
salga es la que el documento tenía de verdad.

Cómo se encuentran: sobre la imagen en gris, una raya es una **racha larga de
píxeles oscuros seguidos** en una fila (horizontal) o en una columna (vertical).
Se buscan con sumas acumuladas —una pasada por la imagen, no píxel a píxel, que
a 300 puntos por pulgada serían nueve millones— y se admite algún hueco, porque
el escaneo rompe las líneas. Después, las filas contiguas que forman una misma
raya gruesa se juntan en una sola.

Lo que se descarta a propósito:

  · lo que toca el borde de la hoja — el marco negro que deja el escáner;
  · las rachas cortas — el texto no forma rayas largas, pero un subrayado sí, y
    ese se conserva: no molesta, porque para que haya tabla hacen falta al menos
    tres bordes de columna.

Autoría: Equipo de Tecnología Maquita — 2026-08-17
"""

import logging

logger = logging.getLogger(__name__)

# Por debajo de este gris, el píxel cuenta como tinta (0 negro, 255 blanco)
UMBRAL_TINTA = 150
# Qué parte de la racha puede venir rota por el escaneo y seguir siendo una raya
CONTINUIDAD = 0.90
# Largo mínimo de una raya, en pulgadas. Las horizontales de una tabla cruzan
# varias columnas; las verticales pueden ser solo el alto de una fila.
LARGO_MINIMO_HORIZONTAL = 0.45
LARGO_MINIMO_VERTICAL = 0.20
# Grosor máximo: por encima de esto no es una raya, es una franja de color o una
# foto oscura, y dibujarla taparía el texto
GROSOR_MAXIMO = 0.06
# Lo que se deja de margen: una raya pegada al borde es el marco del escáner
MARGEN_BORDE = 0.10
# Una vertical corta solo cuenta si CRUZA rayas horizontales: si no, lo más
# probable es que sea el palo de una letra («l», «I», «1», «D»), que a 200 o 300
# puntos por pulgada mide casi lo mismo que la vertical de una fila de tabla.
CRUCES_MINIMOS = 2
# …salvo que sea larga de verdad, y entonces vale por sí sola: hay tablas que
# separan columnas con una línea y no dibujan ninguna horizontal.
LARGO_QUE_SE_VALE_SOLO = 1.0


def _rachas_largas(oscuro, largo, continuidad=CONTINUIDAD):
    """Por cada fila, dónde hay una racha de tinta de al menos `largo` píxeles.

    Se resuelve con sumas acumuladas: la tinta que hay en cualquier ventana de
    `largo` píxeles es la resta de dos columnas de la suma acumulada. Una pasada
    por la imagen en vez de recorrerla píxel a píxel.
    """
    import numpy as np

    if largo < 2 or oscuro.shape[1] <= largo:
        return None
    acumulado = np.cumsum(oscuro, axis=1, dtype=np.int32)
    ventanas = acumulado[:, largo:] - acumulado[:, :-largo]
    return ventanas >= int(largo * continuidad)


def _agrupar(indices, separacion=2):
    """Junta los índices seguidos: una raya gruesa ocupa varias filas."""
    grupos, actual = [], []
    for indice in sorted(indices):
        if actual and indice - actual[-1] > separacion:
            grupos.append(actual)
            actual = []
        actual.append(indice)
    if actual:
        grupos.append(actual)
    return grupos


def _rayas_en_un_sentido(oscuro, largo_minimo, grosor_maximo, margen):
    """Las rayas horizontales de una imagen: (centro, desde, hasta, grosor).

    Todo en píxeles. Para las verticales se llama con la imagen girada y se
    cambian las coordenadas al volver.
    """
    import numpy as np

    alto, ancho = oscuro.shape
    largo = max(8, int(largo_minimo))
    hay = _rachas_largas(oscuro, largo)
    if hay is None:
        return []

    filas_con_raya = np.nonzero(hay.any(axis=1))[0]
    rayas = []
    for grupo in _agrupar(list(filas_con_raya)):
        grosor = len(grupo)
        if grosor > grosor_maximo:
            continue                      # una franja o una foto, no una raya
        centro = (grupo[0] + grupo[-1]) / 2.0
        if centro < margen or centro > alto - margen:
            continue                      # el marco que deja el escáner
        # Hasta dónde llega: el trozo que ocupan las ventanas encontradas
        columnas = np.nonzero(hay[grupo].any(axis=0))[0]
        if not len(columnas):
            continue
        desde, hasta = int(columnas[0]), int(columnas[-1]) + largo
        if hasta - desde < largo:
            continue
        rayas.append((centro, desde, min(hasta, ancho), grosor))
    return rayas


def _cruza(vertical, horizontales, holgura=3.0):
    """Cuántas rayas horizontales atraviesa esta vertical."""
    _x, desde, hasta, _grosor = vertical
    cruces = 0
    for y, h_desde, h_hasta, _g in horizontales:
        if desde - holgura <= y <= hasta + holgura and h_desde - holgura <= _x <= h_hasta + holgura:
            cruces += 1
    return cruces


def _verticales_de_verdad(verticales, horizontales, largo_suficiente):
    """Deja fuera los palos de las letras, que no sostienen ninguna tabla."""
    salida = []
    for vertical in verticales:
        largo = vertical[2] - vertical[1]
        if largo >= largo_suficiente:
            salida.append(vertical)
        elif _cruza(vertical, horizontales) >= CRUCES_MINIMOS:
            salida.append(vertical)
    return salida


def buscar(ruta_imagen, dpi, ancho_pt, alto_pt):
    """Las rayas del papel, en puntos PDF.

    Devuelve `{'horizontales': [...], 'verticales': [...]}`, cada una como
    `(coordenada, desde, hasta, grosor)`. Si algo falla devuelve las dos listas
    vacías: un documento sin rayas es lo que había hasta ahora, no una avería.
    """
    vacio = {'horizontales': [], 'verticales': []}
    try:
        import numpy as np
        from PIL import Image
    except ImportError:
        logger.info('sin numpy/Pillow no se pueden buscar las rayas del escaneo')
        return vacio

    try:
        with Image.open(ruta_imagen) as abierta:
            gris = np.asarray(abierta.convert('L'))
    except Exception:
        logger.warning('no se pudo abrir la imagen para buscar rayas', exc_info=True)
        return vacio

    if gris.ndim != 2 or min(gris.shape) < 20:
        return vacio

    oscuro = gris < UMBRAL_TINTA
    escala = 72.0 / float(dpi or 72)
    margen = MARGEN_BORDE * dpi
    grosor_maximo = max(2, int(GROSOR_MAXIMO * dpi))

    def a_puntos(rayas, girado):
        salida = []
        for centro, desde, hasta, grosor in rayas:
            salida.append((
                round(centro * escala, 2),
                round(desde * escala, 2),
                round(hasta * escala, 2),
                round(max(0.4, min(2.5, grosor * escala)), 2),
            ))
        del girado
        return salida

    try:
        horizontales = _rayas_en_un_sentido(
            oscuro, LARGO_MINIMO_HORIZONTAL * dpi, grosor_maximo, margen)
        # Las verticales son las horizontales de la imagen girada un cuarto de
        # vuelta: se reaprovecha el mismo trabajo en vez de escribirlo dos veces.
        verticales = _rayas_en_un_sentido(
            np.ascontiguousarray(oscuro.T), LARGO_MINIMO_VERTICAL * dpi,
            grosor_maximo, margen)
    except Exception:
        logger.warning('no se pudieron buscar las rayas del escaneo', exc_info=True)
        return vacio

    en_puntos_h = a_puntos(horizontales, False)
    en_puntos_v = a_puntos(verticales, True)
    # Los palos de las letras miden casi lo mismo que la vertical de una fila:
    # se distinguen porque una raya de tabla cruza las horizontales y un palo no.
    en_puntos_v = _verticales_de_verdad(en_puntos_v, en_puntos_h,
                                        LARGO_QUE_SE_VALE_SOLO * 72.0)
    encontradas = {'horizontales': en_puntos_h, 'verticales': en_puntos_v}
    # Las rayas no pueden salirse de la hoja (la imagen y la página pueden
    # diferir en algún punto por el redondeo del renderizado).
    encontradas['horizontales'] = [r for r in encontradas['horizontales']
                                   if r[0] <= alto_pt]
    encontradas['verticales'] = [r for r in encontradas['verticales']
                                 if r[0] <= ancho_pt]
    return encontradas


def dibujar(hoja, rayas, color=(0.25, 0.25, 0.25)):
    """Traza en la hoja nueva las rayas encontradas. Devuelve cuántas puso."""
    if not rayas:
        return 0
    import fitz

    puestas = 0
    forma = hoja.new_shape()
    for y, desde, hasta, grosor in rayas.get('horizontales', []):
        forma.draw_line(fitz.Point(desde, y), fitz.Point(hasta, y))
        puestas += 1
    for x, desde, hasta, grosor in rayas.get('verticales', []):
        forma.draw_line(fitz.Point(x, desde), fitz.Point(x, hasta))
        puestas += 1
    if puestas:
        # Un grosor único y fino: el del escaneo viene inflado por la resolución
        # y lo que importa es que la raya esté, no reproducir su grosor exacto.
        forma.finish(color=color, width=0.75)
        forma.commit()
    return puestas
