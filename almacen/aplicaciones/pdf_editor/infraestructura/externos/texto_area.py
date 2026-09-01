# -*- coding: utf-8 -*-
"""
El texto de un TROZO de la hoja, tal cual está escrito.
=======================================================

Pedido del usuario (31-jul-2026): «en Extraer texto (OCR) debe permitirme escoger y
seleccionar un área de texto, no por página, y debe salir tal cual está escrito».

Dos cosas, entonces:

1. **Un recuadro, no la hoja entera.** Se recibe el rectángulo que el usuario dibujó
   (en puntos del PDF) y solo se mira ahí. Si dentro hay texto de verdad, se lee; si
   es un escaneo, se recorta esa zona y se reconoce solo ella —que además es mucho más
   rápido que la hoja completa.

2. **Tal cual está escrito.** El `get_text()` de siempre devuelve las palabras
   seguidas y se pierde la pinta del documento: una tabla de precios sale como una
   lista y las columnas dejan de estar debajo unas de otras. Aquí las palabras se
   vuelven a colocar donde estaban: se agrupan por renglón y se separan con los
   espacios que hagan falta según su posición real. El resultado se lee igual que en
   la hoja siempre que se mire con letra de ancho fijo (que es lo que usa el recuadro
   del editor).

Las dos fuentes —texto incrustado y OCR— acaban en la MISMA función de colocación
(`_componer`), así que un escaneo y un PDF digital se ven igual de ordenados.

Autoría: Equipo de Tecnología Maquita — 2026-07-31
"""

import logging
import statistics

import fitz

from . import texto_area_parrafos

logger = logging.getLogger(__name__)

DPI_OCR = 300
# Un recuadro pequeño se renderiza con MÁS resolución que la hoja entera: como es un
# trozo, subir a 600 dpi sigue costando poca memoria, y a tesseract le cambia la vida
# —con letra pequeña, a 300 dpi se come cifras («6,00» → «600»). Se sube solo hasta
# que el recorte tenga unos 2.400 píxeles de lado, sin pasar del tope.
DPI_MAXIMO = 600
LADO_DESEADO = 2400
# Hasta aquí se considera que el recuadro no tiene texto de verdad y hay que
# reconocerlo. Es bajo a propósito: un sello o una numeración suelta no son «texto».
MINIMO_TEXTO = 8


def _componer(palabras):
    """Las palabras, colocadas como estaban en la hoja.

    `palabras` son tuplas (x0, y0, x1, y1, texto) en las unidades que sean, mientras
    todas usen las mismas. Devuelve el texto con sus renglones y sus sangrías.
    """
    if not palabras:
        return ''

    palabras = sorted(palabras, key=lambda p: (round(p[1], 1), p[0]))
    altos = [p[3] - p[1] for p in palabras if p[3] > p[1]]
    alto_medio = statistics.median(altos) if altos else 10.0

    # Renglones: dos palabras van juntas si sus centros verticales se llevan menos de
    # medio renglón. Es más fiable que comparar el borde de arriba, porque las letras
    # altas (tildes, mayúsculas) mueven ese borde y no el centro.
    renglones = []
    for palabra in palabras:
        centro = (palabra[1] + palabra[3]) / 2
        if renglones and abs(centro - renglones[-1][0]) <= alto_medio * 0.5:
            renglones[-1][1].append(palabra)
        else:
            renglones.append([centro, [palabra]])

    # El ancho de UNA letra, para saber cuántos espacios separan dos palabras. Se saca
    # de las propias palabras (ancho / número de letras): así vale igual para una
    # letra grande de titular que para la pequeña de un pie de página.
    anchos = [(p[2] - p[0]) / len(p[4]) for _c, fila in renglones for p in fila
              if p[4] and p[2] > p[0]]
    ancho_letra = statistics.median(anchos) if anchos else alto_medio * 0.5
    if ancho_letra <= 0:
        ancho_letra = 1.0

    # Texto corrido (sin huecos de columna): por párrafos, no renglón a renglón.
    if texto_area_parrafos.es_texto_corrido(renglones, ancho_letra):
        return texto_area_parrafos.como_parrafos(renglones, ancho_letra)

    izquierda = min(p[0] for p in palabras)

    # El interlineado que USA ESTE bloque: la distancia corriente entre dos renglones
    # seguidos. Se compara contra ella y no contra el alto de la letra, porque un
    # documento con las filas separadas (una tabla, un acta a doble espacio) no tiene
    # renglones en blanco: tiene el interlineado ancho, y son cosas distintas.
    saltos = [renglones[i][0] - renglones[i - 1][0] for i in range(1, len(renglones))]
    interlineado = statistics.median(saltos) if saltos else alto_medio * 1.2

    lineas = []
    centro_anterior = None
    for centro, fila in renglones:
        # Un renglón en blanco de verdad: hueco de más de vez y media el interlineado.
        # Se ponen tantos como quepan (con tope de 3, para que un salto de página no
        # deje media pantalla vacía).
        if centro_anterior is not None and interlineado > 0:
            hueco = centro - centro_anterior
            if hueco > interlineado * 1.6:
                for _ in range(min(3, int(round(hueco / interlineado)) - 1)):
                    lineas.append('')
        centro_anterior = centro

        fila.sort(key=lambda p: p[0])
        linea = ''
        for palabra in fila:
            columna = int(round((palabra[0] - izquierda) / ancho_letra))
            if columna > len(linea):
                linea += ' ' * (columna - len(linea))
            elif linea:
                linea += ' '       # nunca pegar dos palabras
            linea += palabra[4]
        lineas.append(linea.rstrip())

    return '\n'.join(lineas).strip('\n')


def _resolucion(recuadro):
    """Con cuánta resolución mirar este recuadro. Cuanto más pequeño, más."""
    lado = max(recuadro.width, recuadro.height)
    if lado <= 0:
        return DPI_OCR
    return int(max(DPI_OCR, min(DPI_MAXIMO, LADO_DESEADO * 72.0 / lado)))


def _palabras_incrustadas(pagina, recuadro):
    """Las palabras que el PDF ya trae escritas dentro del recuadro."""
    return [(p[0], p[1], p[2], p[3], p[4])
            for p in pagina.get_text('words', clip=recuadro) if p[4].strip()]


def _palabras_reconocidas(pagina, recuadro, idioma):
    """Las palabras que tesseract lee dentro del recuadro de un escaneo."""
    try:
        import pytesseract
        from PIL import Image
        from .cliente_texto import _idioma_disponible

        dpi = _resolucion(recuadro)
        matriz = fitz.Matrix(dpi / 72, dpi / 72)
        pix = pagina.get_pixmap(matrix=matriz, clip=recuadro, colorspace=fitz.csGRAY)
        imagen = Image.frombytes('L', [pix.width, pix.height], pix.samples)
        pix = None

        # `preserve_interword_spaces` es lo que hace que tesseract respete los huecos
        # entre columnas en vez de dejar un solo espacio. Y `--psm 6` (un bloque de
        # texto) encaja con lo que es un recuadro elegido a mano, mejor que el `--psm
        # 1` de la hoja entera, que se pone a buscar la estructura del documento.
        datos = pytesseract.image_to_data(
            imagen, lang=_idioma_disponible(idioma),
            config='--psm 6 -c preserve_interword_spaces=1',
            output_type=pytesseract.Output.DICT)
    except ImportError:
        logger.warning('pytesseract no disponible: no se puede leer el recuadro')
        return []
    except Exception as e:
        logger.warning('El reconocimiento del recuadro falló: %s', e)
        return []

    palabras = []
    for i, texto in enumerate(datos['text']):
        texto = (texto or '').strip()
        if not texto:
            continue
        try:
            if float(datos['conf'][i]) < 30:      # por debajo, tesseract adivina
                continue
        except (ValueError, TypeError):
            continue
        x, y = datos['left'][i], datos['top'][i]
        palabras.append((x, y, x + datos['width'][i], y + datos['height'][i], texto))
    return palabras


def extraer(datos_bytes, numero_pagina, recuadro, idioma='spa'):
    """El texto del recuadro pedido, tal cual está escrito.

    `numero_pagina` empieza en 1 y `recuadro` es (x0, y0, x1, y1) en puntos del PDF,
    con el origen arriba a la izquierda (lo mismo que usa el editor).

    Devuelve (texto, método), donde método es 'texto_incrustado' u 'ocr_tesseract'.
    """
    documento = fitz.open(stream=datos_bytes, filetype='pdf')
    try:
        indice = max(0, min(len(documento) - 1, int(numero_pagina) - 1))
        pagina = documento[indice]
        rect = fitz.Rect(*recuadro) & pagina.rect      # nunca fuera de la hoja
        if rect.is_empty:
            return '', 'texto_incrustado'

        palabras = _palabras_incrustadas(pagina, rect)
        texto = _componer(palabras)
        if len(texto.strip()) >= MINIMO_TEXTO:
            return texto, 'texto_incrustado'

        # Dentro del recuadro no hay texto de verdad: es un escaneo o una imagen.
        reconocidas = _palabras_reconocidas(pagina, rect, idioma)
        if reconocidas:
            return _componer(reconocidas), 'ocr_tesseract'
        return texto, 'texto_incrustado'
    finally:
        documento.close()


def extraer_como_resultado(datos_bytes, numero_pagina, recuadro, idioma='spa'):
    """Lo mismo que `extraer`, con la forma que ya espera el editor.

    El recuadro y la hoja entera comparten respuesta a propósito: así el editor
    enseña el resultado con el mismo código, mire lo que mire.
    """
    texto, metodo = extraer(datos_bytes, numero_pagina, recuadro, idioma)
    return {
        'total_paginas': 1,
        'texto_total': texto,
        'paginas': [{'pagina': int(numero_pagina), 'texto': texto,
                     'caracteres': len(texto), 'metodo': metodo}],
        'ocr_utilizado': metodo == 'ocr_tesseract',
        'area': [round(float(v), 1) for v in recuadro],
    }
