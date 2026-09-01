# -*- coding: utf-8 -*-
"""
Escribir texto de tabla en el PDF, con la letra del documento.
===============================================================
Parte de la edición de tablas del editor (ver `tablas_pdf.py`). Aquí vive todo
lo que tiene que ver con PONER el texto: decidir con qué fuente se escribe,
encogerlo o partirlo si ya no cabe en su columna, y colocarlo respetando la
alineación de la celda.

La tipografía no se reinventa: se reutiliza la maquinaria de
`cliente_pymupdf.py`, que es la que sabe encontrar la fuente incrustada del
propio PDF, las equivalentes del sistema y simular la negrita que falte.

Autoría: Equipo de Tecnología Maquita — 2026-07-27
"""

import logging

import fitz

from . import letras_base14

logger = logging.getLogger(__name__)

CUERPO_MINIMO = 5.5         # por debajo el texto deja de leerse
MARGEN_CELDA = 2.0          # aire a los lados dentro de la celda


def color_de(estilo):
    """El color del texto, de entero empaquetado a la terna que quiere fitz."""
    entero = estilo.get('color', 0) or 0
    return (((entero >> 16) & 255) / 255.0,
            ((entero >> 8) & 255) / 255.0,
            (entero & 255) / 255.0)


def _trozos_de_palabra(palabra, resolucion, disponible):
    """Corta una palabra que no cabe ENTERA, en pedazos que quepan.

    Sin guion a proposito: en una tabla lo que se escribe puede ser un codigo o
    un importe, y un guion inventado se leeria como parte del dato.

    Se corta solo lo imprescindible: una palabra que cabe vuelve tal cual.
    """
    if resolucion['font'].text_length(palabra, fontsize=resolucion['tam']) <= disponible:
        return [palabra]
    trozos, actual = [], ''
    for letra in palabra:
        prueba = actual + letra
        if actual and resolucion['font'].text_length(
                prueba, fontsize=resolucion['tam']) > disponible:
            trozos.append(actual)
            actual = letra
        else:
            actual = prueba          # siempre al menos una letra por trozo
    if actual:
        trozos.append(actual)
    return trozos


def partir(texto, resolucion, disponible):
    """Reparte el texto en renglones que quepan en el ancho.

    Una palabra mas ancha que la celda no se puede repartir por espacios: hasta
    el 19-ago-2026 salia escrita entera y se derramaba sobre las columnas
    vecinas. Ahora se trocea; y como el reparto devuelve mas renglones, la fila
    crece para acogerlos igual que con cualquier texto largo.
    """
    palabras = []
    for suelta in texto.split():
        palabras.extend(_trozos_de_palabra(suelta, resolucion, disponible))
    if not palabras:
        return ['']
    lineas, actual = [], palabras[0]
    for palabra in palabras[1:]:
        prueba = actual + ' ' + palabra
        if resolucion['font'].text_length(prueba, fontsize=resolucion['tam']) <= disponible:
            actual = prueba
        else:
            lineas.append(actual)
            actual = palabra
    lineas.append(actual)
    return lineas


def encajar(resolucion, texto, disponible):
    """Encoge el cuerpo hasta que el texto quepa. Devuelve si hubo que apretarlo.

    El ancho de un texto es **proporcional** al cuerpo, así que el tamaño que
    cabe se calcula de una vez en vez de ir bajando de 0,25 en 0,25 midiendo
    cada paso: en una tabla larga eran miles de mediciones y segundos de espera
    (optimización pedida el 28-jul-2026). Se deja una comprobación final por si
    el redondeo de la fuente deja el texto un pelo largo.
    """
    ancho = resolucion['font'].text_length(texto, fontsize=resolucion['tam'])
    if ancho <= disponible or ancho <= 0:
        return False
    objetivo = resolucion['tam'] * disponible / ancho
    # se baja al cuarto de punto inferior, que es el paso de siempre
    resolucion['tam'] = max(CUERPO_MINIMO, int(objetivo * 4) / 4.0)
    while (resolucion['tam'] > CUERPO_MINIMO
           and resolucion['font'].text_length(texto, fontsize=resolucion['tam']) > disponible):
        resolucion['tam'] -= 0.25
    return True


def apretar_al_ancho(resolucion, texto, lineas, disponible):
    """Encoge el cuerpo hasta que la linea mas ancha quepa en la celda.

    `partir` reparte por espacios: una palabra sola mas ancha que la celda no
    tiene por donde partirse y salia escrita tal cual, derramandose sobre las
    columnas vecinas y SIN aviso —«Electrodomesticos» en la columna de importes
    de la cotizacion (39 pt) se salia 7,9 pt por cada lado (19-ago-2026)—.

    Se calcula el cuerpo de una vez por proporcion, igual que en `encajar`, y se
    vuelve a repartir: al encoger caben mas palabras por linea. Devuelve las
    lineas nuevas y si hubo que apretar.
    """
    def mas_ancha(candidatas):
        if not candidatas:
            return 0.0
        return max(resolucion['font'].text_length(l, fontsize=resolucion['tam'])
                   for l in candidatas)

    ancho = mas_ancha(lineas)
    if ancho <= disponible or ancho <= 0:
        return lineas, False
    objetivo = resolucion['tam'] * disponible / ancho
    resolucion['tam'] = max(CUERPO_MINIMO, int(objetivo * 4) / 4.0)
    lineas = partir(texto, resolucion, disponible)
    while (resolucion['tam'] > CUERPO_MINIMO
           and mas_ancha(lineas) > disponible):
        resolucion['tam'] -= 0.25
        lineas = partir(texto, resolucion, disponible)
    return lineas, True


def x_segun_alineacion(alineacion, izquierda, derecha, ancho, sangria=None):
    """Dónde empieza el texto dentro de la celda.

    La sangria es a que distancia del borde izquierdo estaba el texto que habia. Se
    respeta cuando el texto va alineado a la izquierda: si no, un renglón que estaba
    a 14 pt del borde volvía pegado al borde (a 2 pt) y saltaba a la vista — «se me
    cambia el formato de la escritura», 30-jul-2026.
    """
    if alineacion == 'centro':
        return izquierda + (derecha - izquierda - ancho) / 2
    if alineacion == 'derecha':
        return derecha - MARGEN_CELDA - ancho
    if sangria is not None and sangria > MARGEN_CELDA:
        # Sin pasarse: si el texto nuevo es más largo, la sangría se recorta para que
        # no se salga de la celda.
        return izquierda + min(sangria, max(MARGEN_CELDA, derecha - izquierda - ancho - MARGEN_CELDA))
    return izquierda + MARGEN_CELDA


def escribir(pagina, cliente, resolucion, estilo, texto, izquierda, derecha, base,
             alineacion, alto_disponible=None, sangria=None):
    """Escribe un texto entre dos x, empezando en una línea base.

    El orden importa y se aprendió corrigiendo un defecto (27-jul-2026): primero
    se REPARTE el texto en las líneas que hagan falta **con su letra de siempre**
    —que es lo que hace cualquier procesador de textos— y solo se encoge si esas
    líneas no caben en el alto de la celda. Al revés, un texto largo bajaba a
    5,5 pt y quedaba ilegible.

    Devuelve True si hubo que apretarlo (encogerlo o partirlo).
    """
    resolucion = dict(resolucion)
    disponible = max(1.0, derecha - izquierda - 2 * MARGEN_CELDA)

    lineas = partir(texto, resolucion, disponible)
    apretado = len(lineas) > 1
    if alto_disponible:
        # ¿Caben esas líneas de alto? Si no, se encoge poco a poco y se vuelve
        # a repartir, hasta que quepan o hasta el mínimo legible.
        # Solo importa lo que se sale por debajo de la primera línea: esa ya
        # está colocada. Con una sola línea no hay nada que comprobar — si no,
        # los textos cortos de una celda baja se encogían sin motivo.
        # Se baja de medio punto en medio punto en vez de un cuarto: la mitad
        # de repartos para el mismo resultado a la vista.
        while (len(lineas) > 1
               and (len(lineas) - 1) * resolucion['tam'] * 1.12 > alto_disponible
               and resolucion['tam'] > CUERPO_MINIMO):
            resolucion['tam'] = max(CUERPO_MINIMO, resolucion['tam'] - 0.5)
            lineas = partir(texto, resolucion, disponible)
            apretado = True
    else:
        # Sin alto de referencia (una sola línea recolocada): el criterio de
        # siempre, encajar en el ancho.
        if encajar(resolucion, texto, disponible):
            apretado = True
            lineas = partir(texto, resolucion, disponible)

    # Ultima red: aunque el reparto y el alto ya esten resueltos, una palabra
    # sola puede seguir siendo mas ancha que la celda. Si no cabe, se encoge; y
    # como `apretado` pasa a True, el usuario recibe el aviso en vez de ver el
    # texto pisando la columna de al lado. (19-ago-2026.)
    lineas, encogido_ancho = apretar_al_ancho(resolucion, texto, lineas, disponible)
    if encogido_ancho:
        apretado = True

    interlineado = resolucion['tam'] * 1.12
    try:
        escritor = fitz.TextWriter(pagina.rect, color=color_de(estilo))
        for numero, linea in enumerate(lineas):
            ancho = resolucion['font'].text_length(linea, fontsize=resolucion['tam'])
            x = x_segun_alineacion(alineacion, izquierda, derecha, ancho, sangria)
            punto = fitz.Point(x, base + numero * interlineado)
            # Si la letra del documento es una de las catorce estándar, se
            # escribe con ESA MISMA y sin incrustar nada: el texto editado queda
            # con el mismo nombre de fuente que el resto de la página.
            if letras_base14.escribir(pagina, punto, linea, resolucion,
                                      color_de(estilo)):
                continue
            escritor.append(punto, linea, font=resolucion['font'],
                            fontsize=resolucion['tam'])
            if resolucion['simula_negrita']:
                desplazamiento = cliente._desplazamiento_negrita(resolucion['tam'])
                escritor.append(fitz.Point(punto.x + desplazamiento, punto.y), linea,
                                font=resolucion['font'], fontsize=resolucion['tam'])
        escritor.write_text(pagina)
    except Exception as excepcion:
        logger.warning('no se pudo escribir "%s": %s', texto[:30], excepcion)
    return apretado


def reescribir_fiel(pagina, cliente, renglon, columnas, desplazamiento=0.0):
    """Reescribe un renglón SIN tocarle la letra: solo cambia su altura.

    Al cambiar el alto de una fila las columnas no se mueven, así que un texto
    que cabía sigue cabiendo. Volver a repartirlo y encajarlo con los márgenes
    de celda era lo que le cambiaba la letra: un renglón que llegaba hasta el
    borde «ya no cabía» con el margen añadido y se le encogía el cuerpo — «el
    tipo de letra se me cambia», vídeo del 20-ago-2026, documento digitalizado.

    Si aun así el texto no cupiera en la celda (no debería: mide lo mismo que
    antes), se cae al camino de siempre, que reparte y avisa.
    """
    destino = renglon['destino']
    izquierda, derecha = columnas[destino], columnas[destino + 1]
    resolucion = renglon['resolucion']
    texto = renglon['texto']
    # El renglon YA estaba en esta celda con esta letra y este ancho: volver a
    # escribirlo identico no puede empeorar nada, aunque roce el borde (en un
    # documento digitalizado las cajas del OCR rozan o cruzan las rayas
    # detectadas y eso es su aspecto original). Solo si falta con que
    # escribirlo se cae al camino de siempre.
    if not resolucion or not resolucion.get('font') or renglon.get('rect') is None:
        return escribir_renglon(pagina, cliente, renglon, columnas,
                                desplazamiento)
    x = renglon['rect'].x0
    punto = fitz.Point(x, renglon['base'] + desplazamiento)
    try:
        color = color_de(renglon['estilo'])
        if not letras_base14.escribir(pagina, punto, texto, resolucion, color):
            escritor = fitz.TextWriter(pagina.rect, color=color)
            escritor.append(punto, texto, font=resolucion['font'],
                            fontsize=resolucion['tam'])
            if resolucion['simula_negrita']:
                paso = cliente._desplazamiento_negrita(resolucion['tam'])
                escritor.append(fitz.Point(punto.x + paso, punto.y), texto,
                                font=resolucion['font'],
                                fontsize=resolucion['tam'])
            escritor.write_text(pagina)
    except Exception as excepcion:
        logger.warning('no se pudo reescribir fiel "%s": %s',
                       texto[:30], excepcion)
    return False


def escribir_renglon(pagina, cliente, renglon, columnas, desplazamiento=0.0):
    """Un renglón de la tabla, en su columna nueva y con su altura corregida."""
    destino = renglon['destino']
    return escribir(pagina, cliente, renglon['resolucion'], renglon['estilo'],
                    renglon['texto'], columnas[destino], columnas[destino + 1],
                    renglon['base'] + desplazamiento, renglon['alineacion'])
