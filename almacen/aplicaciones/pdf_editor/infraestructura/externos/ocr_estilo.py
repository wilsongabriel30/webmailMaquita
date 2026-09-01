# -*- coding: utf-8 -*-
"""
Con qué letra escribir lo que el OCR ha leído.
==============================================

«Revisa digitalización, que no cambie estilo, fuentes, etc.» — el usuario,
31-jul-2026. Medido antes de tocar nada, sobre un acta con título y cuerpo:

| En el papel | Cómo quedaba al digitalizar |
|---|---|
| Negrita, 16 pt | Helvetica fina, 9,9 pt |
| Normal, 11 pt | Helvetica fina, 8,8 pt |
| Negrita, 13 pt | Helvetica fina, 9,7 pt |

Todo acababa del mismo tamaño y sin negritas: el documento perdía su jerarquía y los
títulos dejaban de parecerlo.

Un escaneo es una foto: no trae dentro ningún dato de tipografía, y este Tesseract
tampoco puede decirlo (haría falta su motor antiguo, y los idiomas instalados no lo
traen). Se deduce, pues, mirando la tinta:

* **El tamaño.** La altura que ocupa la tinta depende de qué letras haya en el renglón:
  `ACTA` (solo mayúsculas) ocupa 0,69 del cuerpo y `Fundacion Maquita` (con letras que
  suben y bajan) 0,90. Antes se aplicaba un 0,92 fijo a todo, y de ahí el achatamiento.
  Ahora se mide esa fracción con la fuente que se va a usar y se despeja el tamaño.
* **La negrita**, por renglón: la letra gruesa dibuja trazos más anchos con la misma
  altura. Se cuentan las **rachas** de tinta de cada fila de píxeles —cada racha es un
  trazo cortado en horizontal— y se compara con el trazo fino de esa misma página (no
  con la media, que ya viene engordada si media hoja está en negrita).

Lo que aquí **no** se hace, tras haberlo probado y medido: adivinar si la hoja es serif
o de palo seco. Los rangos de las dos clases se solapan (serif 0,35-0,67; palo seco
0,58-0,74 sobre 10 familias) y el solape cae encima de Carlito, la que sustituye a
Calibri. Se escribe en palo seco, que es lo que corresponde a Arial y Calibri; para
documentos con serif, lo honesto sería un selector en la ventana de digitalizar.

Autoría: Equipo de Tecnología Maquita — 2026-07-31
"""

import logging
import statistics

import fitz

logger = logging.getLogger(__name__)

# La letra con la que se rehace el documento. Se INCRUSTA a propósito: si se usara una
# de las 14 estándar (Helvetica y compañía), el archivo no la llevaría dentro y cada
# lector pondría la suya —y al editar el texto saldría con otra distinta, que es lo que
# el usuario veía el 31-jul-2026—. Liberation Sans es la equivalente libre de Arial y
# está instalada en el servidor.
FAMILIA_FINA = 'Liberation Sans'
FAMILIA_GRUESA = 'Liberation Sans:style=Bold'

_CACHE_ARCHIVOS = {}


def archivo_de(familia):
    """La ruta del archivo de esa familia, preguntada una sola vez."""
    if familia not in _CACHE_ARCHIVOS:
        try:
            import subprocess
            _CACHE_ARCHIVOS[familia] = subprocess.run(
                ['fc-match', '-f', '%{file}', familia],
                capture_output=True, text=True, timeout=5).stdout.strip()
        except Exception:
            _CACHE_ARCHIVOS[familia] = ''
    return _CACHE_ARCHIVOS[familia]


# Nombres con los que el documento se refiere a ellas por dentro.
FINA_SANS, GRUESA_SANS = 'LibSans', 'LibSansNegrita'

# Cuánto más gordo que el trazo fino de la página para darlo por negrita.
DE_MAS_PARA_SER_NEGRITA = 1.15

# Alto al que se reduce cada renglón antes de mirarlo. Con 28 píxeles la medida no
# cambia y el trabajo se hace en una fracción del tiempo: a 300 ppp, un renglón de una
# hoja A4 son ~80.000 píxeles, y recorrerlos uno a uno en Python se notaba (8,2 s por
# hoja en la primera versión, contra 3,8 s ahora).
ALTO_DE_ANALISIS = 28
ANCHO_MAXIMO = 480
# Se miran las filas de dos en dos: de un renglón salen miles de rachas igualmente y la
# medida no se mueve, pero el trabajo se parte por la mitad.
PASO_DE_FILAS = 2

_CACHE_FRACCION = {}


# Letras que suben por encima de la equis y letras que bajan por debajo de la línea.
# De ellas depende cuánto ocupa la tinta de un renglón, y por tanto el tamaño que hay
# que ponerle.
_MAYUSCULAS = set('ABCDEFGHIJKLMNÑOPQRSTUVWXYZ0123456789')
_ASCENDENTES = set('bdfhklt')          # suben MÁS que una mayúscula
_LETRAS_QUE_BAJAN = set('gjpqy')
_TILDES = set('áéíóúüÁÉÍÓÚÜñÑ')


def _muestra_del_texto(texto):
    """Una cadenita que ocupa lo mismo, en alto, que ese texto.

    Ocho casos posibles en vez de uno por renglón: así la memoria del cálculo sirve de
    verdad y no hay que rasterizar cada línea del documento.
    """
    # Las letras DE VERDAD del renglón, sin repetir. Se probó con muestras genéricas
    # (una `H` por cualquier mayúscula, una `l` por cualquier ascendente) para tener
    # menos casos que medir, pero un renglón sin mayúsculas salía un 20 % pequeño.
    # Medir cuesta poco desde que lo hace Pillow, así que se mide lo que hay.
    return ''.join(sorted(set(texto.replace(' ', ''))))[:40]


def _alto_de_tinta(pix):
    """Primera y última fila de píxeles con tinta, midiendo con Pillow (en C)."""
    try:
        from PIL import Image, ImageOps
        imagen = Image.frombytes('L', [pix.width, pix.height], pix.samples)
        caja = ImageOps.invert(imagen).getbbox()      # invertida: la tinta es lo claro
        return (caja[1], caja[3] - 1) if caja else None
    except Exception:
        return None


def fraccion_de_tinta(texto, fuente):
    """Qué parte del cuerpo de la letra ocupa la tinta de ESE texto.

    Depende de las letras que haya: solo mayúsculas ocupan ~0,69; con tildes y letras
    que bajan (g, p, q) se llega a ~0,96. Se recuerda por fuente y juego de letras, que
    es de lo único que depende.
    """
    if not texto.strip():
        return 0.9
    muestra = _muestra_del_texto(texto)
    clave = (fuente, muestra)
    if clave in _CACHE_FRACCION:
        return _CACHE_FRACCION[clave]

    doc = fitz.open()
    try:
        pagina = doc.new_page(width=400, height=400)
        familia = FAMILIA_GRUESA if fuente == GRUESA_SANS else FAMILIA_FINA
        pagina.insert_text((20, 300), muestra, fontname=fuente,
                           fontfile=archivo_de(familia), fontsize=100)
        limites = _alto_de_tinta(pagina.get_pixmap(colorspace=fitz.csGRAY))
        fraccion = ((limites[1] - limites[0] + 1) / 100.0) if limites else 0.9
    except Exception:
        fraccion = 0.9
    finally:
        doc.close()

    fraccion = min(1.4, max(0.45, fraccion))
    _CACHE_FRACCION[clave] = fraccion
    return fraccion


def tamano_de_letra(texto, fuente, alto_caja):
    """El cuerpo en puntos que deja la tinta a la altura que midió el OCR."""
    return max(4.0, min(96.0, alto_caja / fraccion_de_tinta(texto, fuente)))


def medir_renglon(imagen, renglon):
    """Cómo es el trazo de ese renglón: {'grosor'}, o None si no se puede medir.

    De aquí sale la negrita de cada renglón.
    """
    try:
        from PIL import Image
        recorte = imagen.crop((renglon['x'], renglon['y'],
                               renglon['x'] + renglon['ancho'],
                               renglon['y'] + renglon['alto']))
        if recorte.height < 4 or recorte.width < 4:
            return None
        escala = ALTO_DE_ANALISIS / float(recorte.height)
        ancho = max(4, min(ANCHO_MAXIMO, int(recorte.width * escala)))
        recorte = recorte.resize((ancho, ALTO_DE_ANALISIS), Image.BILINEAR)
        datos = recorte.tobytes()
    except Exception:
        return None

    rachas = []
    for y in range(0, ALTO_DE_ANALISIS, PASO_DE_FILAS):
        fila = datos[y * ancho:(y + 1) * ancho]
        seguidos = 0
        for valor in fila:
            if valor < 128:
                seguidos += 1
            elif seguidos:
                rachas.append(seguidos)
                seguidos = 0
        if seguidos:
            rachas.append(seguidos)

    if len(rachas) < 8:
        return None
    media = statistics.mean(rachas)
    if media <= 0:
        return None
    return {'grosor': media / float(ALTO_DE_ANALISIS)}


def umbral_de_negrita(medidas):
    """A partir de qué grosor se considera negrita en esta hoja.

    La referencia NO es la media: en una hoja con la mitad de los renglones en negrita
    ya vendría engordada y no se detectaría ninguno. Se toma el trazo fino (el 30 % más
    delgado), que es el texto corriente.
    """
    grosores = sorted(m['grosor'] for m in medidas if m and m['grosor'] > 0)
    if not grosores:
        return None
    return grosores[int(len(grosores) * 0.3)] * DE_MAS_PARA_SER_NEGRITA
