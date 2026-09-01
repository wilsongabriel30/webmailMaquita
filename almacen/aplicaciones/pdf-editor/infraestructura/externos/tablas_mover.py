# -*- coding: utf-8 -*-
"""
Mover una tabla entera por la página, como en Word.
====================================================
«yo quiero copiar la misma estructura de este, aquí, o sea **mover tablas**…
quiero que esta tabla funcione como un tipo Word, pero sin abrir OnlyOffice»
— el usuario, 29-jul-2026.

Ya se podía mover una fila o una columna dentro de la tabla. Lo que faltaba era
coger **la tabla entera** y llevarla a otro sitio de la hoja: se agarra por su
asa y se arrastra.

Cómo se hace: se lee lo que hay dentro (texto y tipografía), se borra el sitio
de donde sale y se vuelve a dibujar todo corrido. Las rayas se respetan como en
el resto del módulo —solo se dibujan las que el documento tenía—.

Dos decisiones que conviene conocer:

  · **La tabla no se sale de la hoja**: el arrastre se recorta al papel.
  · **El sitio de destino no se borra.** Si allí hubiera texto, la tabla se pone
    encima y se avisa, en vez de hacerle sitio a la fuerza. Borrarle un párrafo
    a alguien por arrastrar mal es peor que un solape que se ve y se deshace con
    Ctrl+Z.

Autoría: Equipo de Tecnología Maquita — 2026-07-29
"""

import logging

import fitz

from . import guardado_pdf, tablas_fondos, tablas_imagenes, tablas_pdf

logger = logging.getLogger(__name__)

# Aire que se le deja al papel: la tabla no se pega al borde de la hoja.
MARGEN_HOJA = 12.0
# Un movimiento por debajo de esto no merece rehacer el documento.
MINIMO_MOVIMIENTO = 0.5


def _recortar_al_papel(pagina, columnas, filas, dx, dy):
    """El desplazamiento que de verdad cabe en la hoja."""
    ancho, alto = pagina.rect.width, pagina.rect.height
    dx = max(dx, MARGEN_HOJA - columnas[0])
    dx = min(dx, ancho - MARGEN_HOJA - columnas[-1])
    dy = max(dy, MARGEN_HOJA - filas[0])
    dy = min(dy, alto - MARGEN_HOJA - filas[-1])
    return dx, dy


def _texto_ajeno_en(pagina, destino, origen):
    """Lo que ya hay escrito en el destino y no es de la propia tabla.

    Devuelve el primer texto que estorba, o None si el sitio está libre. Sirve
    para AVISAR, no para impedir: el usuario ve dónde suelta y tiene Ctrl+Z.
    """
    for renglon in tablas_pdf._renglones_dentro(pagina, destino):
        centro = fitz.Point((renglon['rect'].x0 + renglon['rect'].x1) / 2,
                            (renglon['rect'].y0 + renglon['rect'].y1) / 2)
        if centro in origen:
            continue                       # es de la tabla, se mueve con ella
        return renglon['texto']
    return None


def mover_tabla(contenido_pdf, numero_pagina, indice_tabla, dx, dy):
    """Lleva la tabla entera a otro sitio de la página. Devuelve (pdf, aviso)."""
    dx, dy = float(dx), float(dy)

    cliente = tablas_pdf._cliente()
    documento, pagina, tabla = tablas_pdf._abrir(contenido_pdf, numero_pagina,
                                                 indice_tabla)
    try:
        columnas = tablas_pdf._bordes_de_columna(tabla)
        filas = tablas_pdf._bordes_de_fila(tabla)
        origen = fitz.Rect(columnas[0], filas[0], columnas[-1], filas[-1])

        dx, dy = _recortar_al_papel(pagina, columnas, filas, dx, dy)
        if abs(dx) < MINIMO_MOVIMIENTO and abs(dy) < MINIMO_MOVIMIENTO:
            raise ValueError('La tabla ya está en el borde de la hoja: por ahí '
                             'no se puede mover más.')

        destino = fitz.Rect(origen.x0 + dx, origen.y0 + dy,
                            origen.x1 + dx, origen.y1 + dy)

        # El estilo y las rayas se miran AHORA, con la tabla todavía entera.
        grosor, color_raya = tablas_pdf._estilo_de_las_rayas(pagina, origen)
        renglones = tablas_pdf._leer_tabla(pagina, columnas, filas, cliente)
        estorba = _texto_ajeno_en(pagina, destino, origen)

        nuevas_columnas = [x + dx for x in columnas]
        nuevas_filas = [y + dy for y in filas]

        # Cada renglón se queda en su misma celda: solo cambia de sitio la celda.
        for renglon in renglones:
            renglon['destino'] = renglon['columna']
        tablas_pdf._preparar(documento, pagina, cliente, renglones, None,
                             nuevas_columnas)

        # Los colores de fondo viajan con la tabla: se leen antes de borrar y
        # se pintan en el destino, con la misma rejilla corrida.
        fondos = tablas_fondos.leer(pagina, columnas, filas)
        # Y las imágenes de dentro: viajan con la tabla igual que el color.
        imagenes = tablas_imagenes.leer(pagina, columnas, filas)

        # Se borra SOLO el sitio de donde sale. El de destino no se toca: si
        # allí hubiera algo, la tabla se pone encima, se ve y se deshace, que es
        # mucho mejor que borrarle un párrafo a alguien sin avisar.
        anotacion = pagina.add_redact_annot(origen)
        anotacion.update()
        tablas_pdf._borrar_zona(pagina)

        fondos.pintar(pagina, nuevas_columnas, nuevas_filas)
        imagenes.pintar(pagina, nuevas_columnas, nuevas_filas)
        tablas_pdf._trazar_rejilla(pagina, nuevas_columnas, nuevas_filas,
                                   grosor, color_raya, columnas, filas)

        apretados = 0
        from . import tablas_escritura as escritura
        for renglon in renglones:
            if not renglon.get('resolucion'):
                continue
            # Cada renglón EMPIEZA exactamente donde empezaba, corrido lo que se
            # haya movido la tabla: así la tabla llega igual de cuadrada que
            # salió, en vez de recolocarse según su alineación. Como tope se le
            # da el borde de su celda —no el ancho justo del texto—, o al
            # reescribirlo se partiría en dos renglones.
            caja = renglon['rect']
            columna = renglon['columna']
            tope = nuevas_columnas[min(columna + 1, len(nuevas_columnas) - 1)] - 1.5
            if escritura.escribir(pagina, cliente, renglon['resolucion'],
                                  renglon['estilo'], renglon['texto'],
                                  caja.x0 + dx, max(caja.x1 + dx, tope),
                                  renglon['base'] + dy, 'izquierda'):
                apretados += 1

        aviso = tablas_pdf._avisos(apretados, imagenes)
        if estorba:
            recorte = estorba[:40] + ('…' if len(estorba) > 40 else '')
            aviso = ((aviso + '; ') if aviso else '') + (
                'la tabla quedó encima de «%s» (Ctrl+Z lo deshace)' % recorte)
        return guardado_pdf.guardar(documento), aviso
    finally:
        guardado_pdf.cerrar(documento)
