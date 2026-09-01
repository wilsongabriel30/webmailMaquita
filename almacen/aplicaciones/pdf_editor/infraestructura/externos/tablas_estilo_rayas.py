# -*- coding: utf-8 -*-
"""
De qué color y grosor es CADA raya de la tabla.
==============================================
«verifica que los colores de fondo y bordes también se mantengan» — el usuario,
18-ago-2026.

Para editar una tabla el editor borra la zona y la vuelve a dibujar. Hasta hoy,
al redibujar se tomaba **un solo estilo para toda la rejilla**: el grosor más
fino y el color más repetido. En una tabla con recuadro exterior grueso, rayas
interiores finas y un separador de color bajo el encabezado —es decir, en
cualquier tabla con formato— eso significaba que después de agregar una columna
salían **todas las rayas iguales**, con el color y el grosor del recuadro de
fuera. La tabla cambiaba de aspecto por completo.

Aquí se anota, raya por raya y por su posición, con qué color y con qué grosor
estaba dibujada. Al redibujar, cada una se pinta como estaba.

Como el borrado se lleva las rayas, esto **hay que leerlo antes** de borrar; se
recuerda en el propio documento, igual que hace `_rayas_dibujadas` y por el
mismo motivo: algunas operaciones vuelven a pedir la página y PyMuPDF devuelve
otro objeto.

Autoría: Equipo de Tecnología Maquita — 2026-08-18
"""

import collections
import logging

import fitz

from .tablas_base import TOLERANCIA_RAYA

logger = logging.getLogger(__name__)

# Por debajo de esto una línea es una raya, no un rectángulo.
GORDA = 1.2


def _anotar(donde, sitio, color, grosor, desde=None, hasta=None):
    """Anota la raya de ese sitio: su color, su grosor y **por dónde pasa**.

    Lo de «por dónde pasa» importa tanto como lo demás: en una cotización de
    verdad las rayas no van de lado a lado. La rejilla de los artículos llega
    hasta media hoja, la de los totales solo ocupa las dos últimas columnas, y
    entre medias hay huecos. Redibujarlas enteras cambiaba el dibujo de la tabla
    —aparecían líneas donde no las había y desaparecían las dobles—: «al
    aumentar el tamaño de la tabla arrastrando se pierde la línea» (18-ago-2026).
    """
    sitio = round(sitio, 1)
    anterior = donde.get(sitio)
    if anterior is None:
        donde[sitio] = (color, grosor, [])
    elif grosor > anterior[1]:
        donde[sitio] = (color, grosor, anterior[2])
    if desde is not None and hasta is not None and hasta - desde > 0.5:
        donde[sitio][2].append((round(min(desde, hasta), 1),
                                round(max(desde, hasta), 1)))


def _de_este_dibujo(dibujo):
    """Color y grosor de un trazo, con valores razonables si no los declara."""
    color = tuple(dibujo.get('color') or (0, 0, 0))
    grosor = float(dibujo.get('width') or 0.75)
    return color, max(0.1, min(4.0, grosor))


def _anotar_barras(dibujo, horizontales, verticales, votos):
    """Las rayas que en realidad son rectángulos de relleno muy finos."""
    relleno = dibujo.get('fill')
    if not relleno:
        return
    color = tuple(relleno)
    for trazo in dibujo.get('items') or []:
        if trazo[0] != 're':
            continue
        caja = fitz.Rect(trazo[1])
        if caja.height <= GORDA and caja.width > 12:
            grosor = max(0.3, min(4.0, caja.height or 0.75))
            _anotar(horizontales, (caja.y0 + caja.y1) / 2, color, grosor,
                    caja.x0, caja.x1)
            votos[(color, grosor)] += 1
        elif caja.width <= GORDA and caja.height > 8:
            grosor = max(0.3, min(4.0, caja.width or 0.75))
            _anotar(verticales, (caja.x0 + caja.x1) / 2, color, grosor,
                    caja.y0, caja.y1)
            votos[(color, grosor)] += 1


def leer(pagina):
    """El estilo de cada raya de la página: por su posición.

    Devuelve `{'horizontales': {y: (color, grosor)}, 'verticales': {x: ...},
    'defecto': (color, grosor)}`. Se recuerda por página.
    """
    documento = pagina.parent
    numero = pagina.number
    memoria = getattr(documento, '_faro_estilo_rayas', None)
    if memoria is None:
        memoria = {}
        documento._faro_estilo_rayas = memoria
    if numero in memoria:
        return memoria[numero]

    horizontales, verticales = {}, {}
    votos = collections.Counter()
    try:
        for dibujo in pagina.get_drawings():
            if not dibujo.get('color'):
                # Sin trazo, pero puede ser una raya igual: Word y LibreOffice
                # dibujan los bordes de sus tablas como **rectángulos rellenos
                # de un punto de alto**, no como líneas. Es el caso más común en
                # los documentos de la fundación, así que también se anota, con
                # el color del relleno y con su propio grueso.
                _anotar_barras(dibujo, horizontales, verticales, votos)
                continue
            color, grosor = _de_este_dibujo(dibujo)
            for trazo in dibujo.get('items') or []:
                if trazo[0] == 'l':
                    inicio, fin = trazo[1], trazo[2]
                    if abs(fin.y - inicio.y) < GORDA and abs(fin.x - inicio.x) > 12:
                        _anotar(horizontales, (inicio.y + fin.y) / 2, color, grosor,
                                inicio.x, fin.x)
                        votos[(color, grosor)] += 1
                    elif abs(fin.x - inicio.x) < GORDA and abs(fin.y - inicio.y) > 8:
                        _anotar(verticales, (inicio.x + fin.x) / 2, color, grosor,
                                inicio.y, fin.y)
                        votos[(color, grosor)] += 1
                elif trazo[0] == 're':
                    caja = fitz.Rect(trazo[1])
                    if caja.height < GORDA and caja.width > 12:
                        _anotar(horizontales, (caja.y0 + caja.y1) / 2, color, grosor,
                                caja.x0, caja.x1)
                        votos[(color, grosor)] += 1
                    elif caja.width < GORDA and caja.height > 8:
                        _anotar(verticales, (caja.x0 + caja.x1) / 2, color, grosor,
                                caja.y0, caja.y1)
                        votos[(color, grosor)] += 1
                    elif caja.width > 12 and caja.height > 8:
                        # Un recuadro con borde: sus cuatro lados son rayas, y
                        # llevan el estilo del recuadro (suele ser el grueso de
                        # fuera).
                        _anotar(horizontales, caja.y0, color, grosor,
                                caja.x0, caja.x1)
                        _anotar(horizontales, caja.y1, color, grosor,
                                caja.x0, caja.x1)
                        _anotar(verticales, caja.x0, color, grosor,
                                caja.y0, caja.y1)
                        _anotar(verticales, caja.x1, color, grosor,
                                caja.y0, caja.y1)
                        votos[(color, grosor)] += 1
    except Exception:
        logger.debug('no se pudo mirar el estilo de las rayas', exc_info=True)

    # El estilo de por defecto —para una raya NUEVA, la de una columna que se
    # acaba de agregar— es el más repetido, que es el de las rayas de dentro.
    defecto = votos.most_common(1)[0][0] if votos else ((0, 0, 0), 0.75)
    defecto = (defecto[0], defecto[1], [])
    memoria[numero] = {'horizontales': horizontales, 'verticales': verticales,
                       'defecto': defecto}
    return memoria[numero]


def _anotada_en(mapa, cuales, sitio):
    """Lo anotado para la raya que había en ese sitio, o None."""
    if not mapa:
        return None
    anotadas = mapa.get(cuales) or {}
    mejor, distancia_mejor = None, None
    for anotado, ficha in anotadas.items():
        distancia = abs(anotado - sitio)
        if distancia <= TOLERANCIA_RAYA and (distancia_mejor is None
                                             or distancia < distancia_mejor):
            mejor, distancia_mejor = ficha, distancia
    return mejor


def piezas_en(mapa, cuales, sitio):
    """Los trozos de raya que había ahí, **cada uno con su color y su grosor**.

    Devuelve `[(color, grosor, [(desde, hasta), ...]), ...]`.

    No se pueden mezclar: en una cotización de verdad, a la altura de la fila de
    totales hay una línea NEGRA que cubre la mitad izquierda y, dos puntos más
    abajo, una barra AZUL CLARO —un sombreado— que cubre la derecha. Como caen
    en el mismo borde de la tabla, quedarse con un solo color repintaba la línea
    negra en azul casi blanco: la línea desaparecía a la vista. Era justo lo que
    contaba el usuario: «al aumentar el tamaño de la tabla arrastrando se pierde
    la línea» (18-ago-2026).
    """
    if not mapa:
        return []
    anotadas = mapa.get(cuales) or {}
    por_estilo = {}
    for anotado, ficha in anotadas.items():
        if abs(anotado - sitio) > TOLERANCIA_RAYA:
            continue
        clave = (ficha[0], ficha[1])
        por_estilo.setdefault(clave, []).extend(ficha[2])
    salida = []
    for (color, grosor), tramos in por_estilo.items():
        fundidos = _fundir(tramos)
        if fundidos:
            salida.append((color, grosor, fundidos))
    # Primero lo que más se ve: así, si dos trozos se pisan, encima queda el
    # oscuro y no el clarito.
    salida.sort(key=lambda pieza: sum(pieza[0]), reverse=True)
    return salida


def tramos_en(mapa, cuales, sitio):
    """Por dónde pasaba la raya que había ahí: [(desde, hasta), ...].

    Se juntan los tramos de **todas** las rayas que caen ahí mismo, no solo los
    de la más cercana. En una cotización de verdad, una misma separación viene
    dibujada dos veces con un par de puntos de diferencia —el borde de abajo de
    una fila y el de arriba de la siguiente—, y cada una cubre un trozo distinto
    del ancho: la de la izquierda llega hasta la mitad y la de la derecha cubre
    la zona de los totales. Quedándose con una sola se perdía la otra mitad de
    la línea (18-ago-2026).

    Vacío si no había ninguna: una raya nueva se dibuja entera.
    """
    if not mapa:
        return []
    anotadas = mapa.get(cuales) or {}
    juntos = []
    for anotado, ficha in anotadas.items():
        if abs(anotado - sitio) <= TOLERANCIA_RAYA:
            juntos.extend(ficha[2])
    return _fundir(juntos)


def _fundir(tramos):
    """Une los trozos que se tocan o se solapan, para no dibujar dos veces."""
    if not tramos:
        return []
    ordenados = sorted(tramos)
    salida = [list(ordenados[0])]
    for desde, hasta in ordenados[1:]:
        if desde <= salida[-1][1] + 0.6:
            salida[-1][1] = max(salida[-1][1], hasta)
        else:
            salida.append([desde, hasta])
    return [(a, b) for a, b in salida]


def estilo_en(mapa, cuales, sitio, defecto=None):
    """Cómo estaba dibujada la raya que había en ese sitio.

    `cuales` es 'horizontales' o 'verticales'. Si ahí no había ninguna —una raya
    nueva— se devuelve el estilo de por defecto de la tabla.
    """
    ficha = _anotada_en(mapa, cuales, sitio)
    if ficha is not None:
        return (ficha[0], ficha[1])
    if defecto:
        return defecto[0], defecto[1]
    suyo = (mapa or {}).get('defecto')
    return (suyo[0], suyo[1]) if suyo else ((0, 0, 0), 0.75)
