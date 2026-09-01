# -*- coding: utf-8 -*-
"""
OCR que devuelve un PDF de TEXTO REAL (para poder convertirlo a Word).
======================================================================
Un escaneo pasado por el OCR de siempre —tesseract con salida `pdf`, o
`ocrmypdf`— produce un *sandwich*: la foto de la página con el texto
reconocido INVISIBLE debajo. Se midió (27-jul-2026) que `pdf2docx` descarta ese
texto por estar tapado por una imagen a página completa: el Word salía con
**0 caracteres**, una foto que no se puede editar.

Aquí se rehace la página: se escribe el texto reconocido en su sitio, con letra
de verdad y sin la imagen encima. Así `pdf2docx` lo trata como cualquier
documento normal — texto editable y tablas detectadas. Medido sobre un acta
escaneada de 6 páginas: 0 → 4.395 caracteres y 5 tablas.

**Las rayas del papel sí se conservan** (17-08-2026): se buscan en la propia
imagen antes de tirarla y se vuelven a trazar en la hoja nueva (`ocr_rayas`).
Sin ellas, una tabla escaneada dejaba de ser una tabla —ni `pdf2docx` la
reconstruía ni el editor la detectaba—, que es lo que el usuario avisó: «el
digitalizar y OCR no reconoce tablas».

A cambio, el escaneo pierde su parte gráfica (sellos, firmas manuscritas,
membretes): son imágenes, no texto, y no hay OCR que las vuelva editables. El
editor avisa de esto al usuario antes de abrir el Word.

**Las páginas se reparten entre varios procesos**, que es lo que el usuario
espera sentado. Medido sobre esas 6 páginas en la VM 101 (24 núcleos):
**18,1 s en serie → 4,6 s con 8 procesos, sin perder ni un carácter**. Se
mantienen los 300 dpi a propósito: a 200 dpi se perdía un 3 % del texto y a
150 dpi un 6 %, y en un acta o una proforma perder texto es peor que esperar
un segundo más.

Este módulo se ejecuta SIEMPRE en un proceso aparte (`conversor_cli.py`):
tesseract es CPU pura y dentro del worker eventlet de gunicorn congelaría el
event loop y tumbaría al worker.

Autoría: Equipo de Tecnología Maquita — 2026-07-27
"""

import csv
import logging
import os
import shutil
import subprocess
import tempfile
from concurrent.futures import ProcessPoolExecutor

import fitz

try:
    from . import ocr_estilo
except ImportError:          # el CLI lo importa suelto, sin el paquete
    import ocr_estilo

try:
    from . import ocr_rayas
except ImportError:
    import ocr_rayas

try:
    from . import ocr_color
except ImportError:
    import ocr_color

logger = logging.getLogger(__name__)

DPI = 300
# La marca que llevan los documentos salidos de aquí. La lee `tablas_deteccion` para
# no inventarles tablas.
MARCA_OCR = 'faro-ocr-texto'
CONFIANZA_MINIMA = 30       # por debajo, tesseract está adivinando
IDIOMAS_VALIDOS = ('spa', 'eng', 'spa+eng')


def _procesos():
    """Cuántas páginas a la vez. Se dejan núcleos libres para el resto de FARO."""
    return max(1, min(8, (os.cpu_count() or 2) - 2))


def _pagina(argumentos):
    """OCR de UNA página → sus renglones ya colocados.

    Está a nivel de módulo (y no anidada) porque tiene que poder viajar a otro
    proceso: las funciones anidadas no se pueden serializar.
    """
    ruta_pdf, numero, idioma, dpi = argumentos
    escala = 72.0 / dpi
    temporal = tempfile.mkdtemp(prefix='ocrtxt_')
    documento = fitz.open(ruta_pdf)
    try:
        pagina = documento[numero]
        ancho, alto = pagina.rect.width, pagina.rect.height
        ruta_png = os.path.join(temporal, 'p.png')
        pagina.get_pixmap(dpi=dpi).save(ruta_png)
        base = os.path.join(temporal, 'p')
        subprocess.run(['tesseract', ruta_png, base, '-l', idioma, 'tsv'],
                       check=True, capture_output=True, timeout=300)

        # Las palabras se agrupan por renglón y se escriben de corrido: así
        # pdf2docx ve líneas de texto y no un confeti de palabras sueltas.
        lineas = {}
        with open(base + '.tsv', encoding='utf-8', errors='replace') as fh:
            for fila in csv.DictReader(fh, delimiter='\t', quoting=csv.QUOTE_NONE):
                try:
                    if int(fila['level']) != 5 or float(fila['conf']) < CONFIANZA_MINIMA:
                        continue
                except (ValueError, KeyError, TypeError):
                    continue
                texto = (fila.get('text') or '').strip()
                if not texto:
                    continue
                clave = (fila['block_num'], fila['par_num'], fila['line_num'])
                lineas.setdefault(clave, []).append((
                    float(fila['left']) * escala,
                    float(fila['top']) * escala,
                    float(fila['height']) * escala,
                    texto,
                    float(fila['width']) * escala))

        # Cada renglón, con su caja en píxeles (para poder mirar el papel) y en puntos.
        crudos = []
        for palabras in lineas.values():
            palabras.sort()
            # El alto de referencia es la MEDIANA de las palabras, no la más alta: una
            # sola palabra con la caja inflada —una raya de la tabla pegada, una mota
            # del escaneo— estiraba el renglón entero y lo sacaba de su fila.
            altos = sorted(p[2] for p in palabras)
            alto_linea = altos[len(altos) // 2]
            izquierda = min(p[0] for p in palabras)
            derecha = max(p[0] + p[4] for p in palabras)
            arriba = min(p[1] for p in palabras)
            crudos.append({
                'x_pt': izquierda,
                'base_pt': arriba + max(altos),      # la línea base, con el alto real
                'alto_pt': alto_linea,
                'altos_palabras': [(p[3], p[2]) for p in palabras],
                'texto': ' '.join(p[3] for p in palabras),
                # en píxeles de la imagen, que es donde se mira el estilo
                'x': int(izquierda / escala),
                'y': int(arriba / escala),
                'ancho': max(1, int((derecha - izquierda) / escala)),
                'alto': max(1, int(alto_linea / escala)),
            })

        # Con qué letra estaba escrito el papel. Si algo falla, se sigue con la de
        # siempre: más vale un documento en palo seco que ningún documento.
        fina = ocr_estilo.FINA_SANS
        gruesa = ocr_estilo.GRUESA_SANS
        try:
            from PIL import Image
            with Image.open(ruta_png) as abierta:
                # De la misma pasada salen la negrita (en gris) y el COLOR del
                # trazo (en color): un título azul o un importe en rojo del
                # papel deben salir del OCR con su color, no en negro.
                en_color = abierta.convert('RGB')
                imagen = abierta.convert('L')
                medidas = [ocr_estilo.medir_renglon(imagen, r) for r in crudos]
                for renglon in crudos:
                    renglon['color'] = ocr_color.color_de_renglon(en_color, renglon)
            # Primero, qué renglones van en negrita.
            umbral = ocr_estilo.umbral_de_negrita(medidas)
            for renglon, medida in zip(crudos, medidas):
                renglon['negrita'] = bool(umbral and medida and medida['grosor'] > umbral)

            # La clase de letra NO se adivina (ver ocr_estilo.py: se probó y no acierta).
            # Se escribe en palo seco, que es lo de siempre y lo que corresponde a
            # Arial y Calibri.
        except Exception as fallo:
            logger.warning('No se pudo mirar el estilo del papel (%s): se usa la letra '
                           'de siempre', fallo)

        # El tamaño ya NO se estima con un factor fijo: la tinta ocupa una parte u otra
        # del cuerpo según las letras que haya («ACTA» 0,69, «Fundacion» 0,90), y con
        # el 0,92 de antes los títulos quedaban del tamaño del cuerpo. Cada PALABRA da
        # su estimación y el renglón se queda con la mediana.
        for renglon in crudos:
            fuente = gruesa if renglon.get('negrita') else fina
            estimados = sorted(
                ocr_estilo.tamano_de_letra(palabra, fuente, alto_palabra)
                for palabra, alto_palabra in renglon['altos_palabras'] if palabra.strip())
            renglon['fuente'] = fuente
            renglon['cuerpo'] = (estimados[len(estimados) // 2] if estimados else
                                 ocr_estilo.tamano_de_letra(renglon['texto'], fuente,
                                                            renglon['alto_pt']))

        # Y los renglones del cuerpo se igualan entre sí: en un documento escrito a
        # máquina el texto corriente mide lo mismo de arriba abajo, y que uno salga a
        # 9,6 y el de al lado a 10,4 descuadra la tabla aunque cada medida sea «casi»
        # correcta. Los títulos, que quedan lejos de esa medida, conservan la suya.
        corrientes = sorted(r['cuerpo'] for r in crudos if not r.get('negrita'))
        if corrientes:
            habitual = corrientes[len(corrientes) // 2]
            for renglon in crudos:
                if abs(renglon['cuerpo'] - habitual) <= habitual * 0.12:
                    renglon['cuerpo'] = habitual

        # Las rayas del papel, mientras la imagen sigue en disco: son las que
        # sostienen las tablas de la hoja nueva.
        rayas = ocr_rayas.buscar(ruta_png, dpi, ancho, alto)

        renglones = [(r['x_pt'], r['base_pt'], r['cuerpo'], r['texto'], r['fuente'],
                      r.get('color'))
                     for r in crudos]
        return numero, ancho, alto, renglones, rayas
    finally:
        documento.close()
        shutil.rmtree(temporal, ignore_errors=True)


def rehacer_con_texto(contenido_pdf, idioma='spa', dpi=DPI):
    """PDF de texto real reconstruido desde el OCR del escaneo.

    Si no se reconoce ni una línea devuelve None: quien llama decide (el editor
    sigue con el PDF original — más vale un Word pobre que ningún Word).
    """
    idioma = {'es': 'spa', 'en': 'eng'}.get(idioma, idioma) or 'spa'
    if idioma not in IDIOMAS_VALIDOS:
        idioma = 'spa'

    fd, ruta_pdf = tempfile.mkstemp(suffix='.pdf')
    os.close(fd)
    salida = None
    try:
        with open(ruta_pdf, 'wb') as fh:
            fh.write(contenido_pdf)
        with fitz.open(ruta_pdf) as documento:
            total = documento.page_count

        trabajos = [(ruta_pdf, numero, idioma, dpi) for numero in range(total)]
        procesos = min(_procesos(), max(1, total))
        if procesos > 1:
            with ProcessPoolExecutor(max_workers=procesos) as pool:
                paginas = list(pool.map(_pagina, trabajos))
        else:
            paginas = [_pagina(trabajo) for trabajo in trabajos]

        salida = fitz.open()
        renglones_totales = 0
        # Los archivos de la letra, una vez: se incrustan en cada hoja para que el
        # documento no dependa de la que tenga el lector (ver ocr_estilo).
        archivos = {
            ocr_estilo.FINA_SANS: ocr_estilo.archivo_de(ocr_estilo.FAMILIA_FINA),
            ocr_estilo.GRUESA_SANS: ocr_estilo.archivo_de(ocr_estilo.FAMILIA_GRUESA),
        }
        rayas_totales = 0
        for _numero, ancho, alto, renglones, rayas in sorted(paginas,
                                                             key=lambda p: p[0]):
            hoja = salida.new_page(width=ancho, height=alto)
            for nombre, archivo in archivos.items():
                if archivo:
                    hoja.insert_font(fontname=nombre, fontfile=archivo)
            # Primero las rayas, que van por debajo del texto
            rayas_totales += ocr_rayas.dibujar(hoja, rayas)
            for x, y, cuerpo, texto, fuente, color in renglones:
                try:
                    hoja.insert_text((x, y), texto, fontname=fuente,
                                     fontfile=archivos.get(fuente) or None,
                                     fontsize=cuerpo, color=color or (0, 0, 0))
                    renglones_totales += 1
                except Exception:
                    pass       # un renglón suelto no puede tumbar el documento

        # Se deja constancia de que esto lo fabricó el OCR. Sirve para que, al
        # buscarle tablas, se le hagan caso SOLO a las rayas que se acaban de
        # trazar —las que había en el papel— y no se le deduzcan columnas por
        # cómo quedó alineado el texto, que serían un espejismo
        # (ver tablas_deteccion._tablas_de).
        salida.set_metadata({'keywords': MARCA_OCR, 'producer': 'FARO Maquita'})

        if not renglones_totales:
            logger.warning('OCR: no se reconoció ni una línea en %d página(s)', total)
            return None
        logger.info('OCR: %d página(s), %d renglones, %d rayas, %d proceso(s) [%s]',
                    total, renglones_totales, rayas_totales, procesos, idioma)
        return salida.tobytes()
    finally:
        if salida is not None:
            salida.close()
        try:
            os.remove(ruta_pdf)
        except OSError:
            pass
