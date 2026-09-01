# -*- coding: utf-8 -*-
"""
Encabezado y pie de página: hasta seis textos, como en Word.
=============================================================

Hasta el 17-08-2026 esto era una sola línea arriba y otra abajo, las dos
pegadas al margen izquierdo, y el pie venía escrito de antemano con «Página
{pagina} de {total}». Eso chocaba con la herramienta de **numerar páginas**,
que ya pone ese número donde uno quiera: quien numeraba primero y luego ponía
un encabezado se encontraba el número dos veces. Lo dijo el usuario:

    «en la parte de encabezado se genera redundancia ya que tengo ya un
    enumerar pie; debería permitir más opciones como escribir tanto en el pie
    como en el encabezado».

Ahora hay **tres sitios en el encabezado y tres en el pie** —izquierda, centro
y derecha—, que es lo que hace falta de verdad: el nombre del documento a la
izquierda y la numeración a la derecha, por ejemplo. Y el pie ya no viene con
nada escrito: el número de página lo pone quien lo escriba.

Las dos herramientas se quedan y ya no se pisan: **numerar páginas** sigue
siendo el atajo de un clic, y esto es lo que se usa cuando se quiere algo más.

Comodines que se pueden escribir en cualquiera de los seis sitios:

    {pagina} o {n}   el número de esta página
    {total}          cuántas páginas tiene el documento
    {fecha}          la fecha de hoy (dd/mm/aaaa)
    {archivo}        el nombre del documento, sin la extensión

Se separó de `cliente_operaciones.py` para no engordarlo: allí solo queda la
llamada.

Autoría: Equipo de Tecnología Maquita — 2026-08-17
"""

import datetime
import io
import logging
import os

import fitz

logger = logging.getLogger(__name__)

SITIOS = ('izquierda', 'centro', 'derecha')

# Cuánto se separa el texto del borde de la hoja: (arriba y abajo, a los lados)
MARGENES = {
    'estrecho': (20.0, 36.0),
    'normal': (28.0, 50.0),
    'ancho': (40.0, 72.0),
}

# El hueco mínimo que se deja entre dos textos de la misma banda
SEPARACION = 8.0
# Por debajo de este cuerpo no se encoge un texto para hacerlo caber
TAMANO_MINIMO = 5.0

# La letra de siempre: va incluida en todo lector de PDF y no pesa nada, pero
# solo sabe escribir el alfabeto occidental básico. Las tildes y la eñe sí las
# tiene; el guion largo, las comillas curvas, el euro o los puntos suspensivos
# —lo que trae cualquier texto pegado de Word— los cambiaba por un punto.
FUENTE_BASE = 'helv'
# Por eso, cuando el texto lleva alguno de esos, se usa una letra completa. Se
# incrusta en el documento, así que solo se recurre a ella si hace falta: pesa
# unos 33 KB (ya recortada a las letras usadas) frente a 1 KB de la de siempre.
RUTAS_FUENTE_COMPLETA = (
    '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
    '/usr/share/fonts/dejavu/DejaVuSans.ttf',
    '/usr/share/fonts/TTF/DejaVuSans.ttf',
)
NOMBRE_FUENTE_COMPLETA = 'faro-encpie'


def _texto_de(banda, sitio):
    """El texto de un sitio, ya limpio (o cadena vacía)."""
    if not banda:
        return ''
    return (banda.get(sitio) or '').strip()


def _sustituir(texto, pagina, total, nombre_archivo):
    """Cambia los comodines por lo que valen en esta página."""
    hoy = datetime.date.today().strftime('%d/%m/%Y')
    limpio = (nombre_archivo or '').rsplit('/', 1)[-1]
    if '.' in limpio:
        limpio = limpio.rsplit('.', 1)[0]
    return (texto.replace('{pagina}', str(pagina))
                 .replace('{n}', str(pagina))
                 .replace('{total}', str(total))
                 .replace('{fecha}', hoy)
                 .replace('{archivo}', limpio))


def _ruta_fuente_completa():
    """La primera letra completa que haya instalada, o None."""
    for ruta in RUTAS_FUENTE_COMPLETA:
        if os.path.exists(ruta):
            return ruta
    return None


class _Letra(object):
    """Con qué letra se escribe y cómo se mide.

    Dos formas: la de siempre (`helv`, sin peso pero de alfabeto corto) y una
    completa incrustada, para cuando el texto trae caracteres que la otra no
    sabe escribir.
    """

    def __init__(self, ruta=None):
        self.ruta = ruta
        self.medidor = None
        if ruta:
            try:
                self.medidor = fitz.Font(fontfile=ruta)
            except Exception:
                logger.info('no se pudo abrir la letra completa %s', ruta)
                self.ruta = None

    @property
    def incrustada(self):
        return bool(self.ruta and self.medidor)

    def ancho(self, texto, tamano):
        try:
            if self.incrustada:
                return self.medidor.text_length(texto, fontsize=tamano)
            return fitz.get_text_length(texto, fontname=FUENTE_BASE, fontsize=tamano)
        except Exception:
            return len(texto) * tamano * 0.5      # aproximación, por si acaso

    def escribir(self, pagina_pdf, punto, texto, tamano, color):
        if self.incrustada:
            pagina_pdf.insert_text(punto, texto, fontname=NOMBRE_FUENTE_COMPLETA,
                                   fontfile=self.ruta, fontsize=tamano,
                                   color=color, overlay=True)
        else:
            pagina_pdf.insert_text(punto, texto, fontname=FUENTE_BASE,
                                   fontsize=tamano, color=color, overlay=True)


def _hace_falta_letra_completa(textos):
    """¿Hay algún carácter que la letra de siempre no sepa escribir?"""
    try:
        ''.join(textos).encode('latin-1')
        return False
    except (UnicodeEncodeError, AttributeError):
        return True


def _encoger_para_que_quepa(letra, textos, tamano, disponible):
    """El cuerpo de letra con el que los textos de una banda caben en el ancho.

    Se prueba con el que pidió el usuario y, si los tres juntos no entran, se va
    bajando. Vale más una línea un punto más pequeña que dos textos pisándose.
    Devuelve `(tamano, cabe)`; si ni con el mínimo entra, se avisa.
    """
    cuerpo = float(tamano)
    while cuerpo >= TAMANO_MINIMO:
        ancho = sum(letra.ancho(t, cuerpo) for t in textos if t)
        huecos = SEPARACION * max(0, len([t for t in textos if t]) - 1)
        if ancho + huecos <= disponible:
            return cuerpo, True
        cuerpo -= 0.5
    return TAMANO_MINIMO, False


def _sitios_de_la_banda(banda, pagina, total, nombre_archivo):
    """Los tres textos de una banda, ya con los comodines sustituidos."""
    return [_sustituir(_texto_de(banda, sitio), pagina, total, nombre_archivo)
            for sitio in SITIOS]


def _recortar(letra, texto, tamano, ancho):
    """El texto recortado con puntos suspensivos para que quepa en ese ancho."""
    if letra.ancho(texto, tamano) <= ancho:
        return texto
    corto = texto
    while corto and letra.ancho(corto + '…', tamano) > ancho:
        corto = corto[:-1]
    return (corto.rstrip() + '…') if corto.strip() else ''


def _repartir(textos, izquierda, derecha):
    """El trozo de ancho que le toca a cada texto cuando no caben los tres.

    Se parte la banda en tantas partes como textos haya y cada uno se queda con
    la suya, en su orden: así el de la izquierda no se mete en el del centro. Sin
    esto los tres acababan apilados en el mismo sitio y no se leía ninguno.
    """
    presentes = [i for i, t in enumerate(textos) if t]
    if not presentes:
        return {}
    parte = (derecha - izquierda - SEPARACION * (len(presentes) - 1)) / len(presentes)
    huecos = {}
    for orden, indice in enumerate(presentes):
        inicio = izquierda + orden * (parte + SEPARACION)
        huecos[indice] = (inicio, inicio + parte)
    return huecos


def _escribir_banda(letra, pagina_pdf, textos, y, tamano, izquierda, derecha, color):
    """Escribe los textos de una banda. Devuelve (se_encogio, se_recorto)."""
    if not any(textos):
        return False, False
    cuerpo, cabe = _encoger_para_que_quepa(letra, textos, tamano, derecha - izquierda)
    # Si ni con el cuerpo más pequeño caben los tres, cada uno se queda con su
    # parte de la banda y se recorta a ella: vale más leer «Direccion de Tecno…»
    # que tener los tres encima unos de otros.
    huecos = {} if cabe else _repartir(textos, izquierda, derecha)
    recortado = False
    for indice, texto in enumerate(textos):
        if not texto:
            continue
        if huecos:
            desde, hasta = huecos[indice]
            escrito = _recortar(letra, texto, cuerpo, hasta - desde)
            recortado = recortado or escrito != texto
            ancho = letra.ancho(escrito, cuerpo)
            # Dentro de su parte, cada uno se apoya donde le toca por su sitio
            x = (desde if indice == 0
                 else (desde + hasta) / 2 - ancho / 2 if indice == 1
                 else hasta - ancho)
        else:
            escrito = texto
            ancho = letra.ancho(escrito, cuerpo)
            x = (izquierda if indice == 0
                 else (izquierda + derecha) / 2 - ancho / 2 if indice == 1
                 else derecha - ancho)
        x = max(izquierda, min(x, derecha - ancho))   # nunca fuera de la hoja
        if not escrito:
            continue
        try:
            letra.escribir(pagina_pdf, fitz.Point(x, y), escrito, cuerpo, color)
        except Exception:
            logger.debug('no se pudo escribir un texto de la banda', exc_info=True)
    return (not cabe), recortado


def aplicar(datos_bytes, encabezado=None, pie=None, tamano=10, margen='normal',
            color=(0.3, 0.3, 0.3), nombre_archivo=''):
    """Pone el encabezado y el pie en todas las páginas. Devuelve (pdf, aviso).

    `encabezado` y `pie` son diccionarios con las claves `izquierda`, `centro` y
    `derecha`; cualquiera puede faltar o venir vacía. Por comodidad también se
    acepta una cadena suelta, que se entiende como el texto de la izquierda —así
    sigue funcionando quien llamara a esto como se llamaba antes—.
    """
    if isinstance(encabezado, str):
        encabezado = {'izquierda': encabezado}
    if isinstance(pie, str):
        pie = {'izquierda': pie}
    if not any(_texto_de(encabezado, s) for s in SITIOS) and \
            not any(_texto_de(pie, s) for s in SITIOS):
        raise ValueError('Escribe al menos un texto en el encabezado o en el pie.')

    try:
        tamano = max(TAMANO_MINIMO, min(72.0, float(tamano)))
    except (TypeError, ValueError):
        tamano = 10.0
    arriba, lateral = MARGENES.get(margen, MARGENES['normal'])

    # Con qué letra se escribe: se mira UNA vez, sobre todo lo que se va a
    # escribir. Si todo cabe en el alfabeto corto se usa la de siempre, que no
    # añade peso al documento; si no, la completa.
    escritos = [_texto_de(banda, sitio) for banda in (encabezado, pie)
                for sitio in SITIOS]
    letra = _Letra(_ruta_fuente_completa() if _hace_falta_letra_completa(escritos)
                   else None)

    documento = fitz.open(stream=datos_bytes, filetype='pdf')
    try:
        total = documento.page_count
        encogidas, recortadas = 0, 0
        for indice, hoja in enumerate(documento):
            caja = hoja.rect
            izquierda = caja.x0 + lateral
            derecha = caja.x1 - lateral
            if derecha - izquierda < 20:              # una hoja diminuta
                izquierda, derecha = caja.x0 + 5, caja.x1 - 5
            numero = indice + 1

            for banda, y in ((encabezado, caja.y0 + arriba),
                             (pie, caja.y1 - arriba)):
                encogio, recorto = _escribir_banda(
                    letra, hoja,
                    _sitios_de_la_banda(banda, numero, total, nombre_archivo),
                    y, tamano, izquierda, derecha, color)
                encogidas += 1 if encogio else 0
                recortadas += 1 if recorto else 0

        if letra.incrustada:
            # La letra completa se recorta a las letras que de verdad se usaron:
            # de unos 400 KB a unos 33 KB por documento.
            try:
                documento.subset_fonts()
            except Exception:
                logger.debug('no se pudo recortar la letra incrustada', exc_info=True)
        salida = io.BytesIO()
        documento.save(salida, garbage=4, deflate=True)
    finally:
        documento.close()

    avisos = []
    if encogidas:
        avisos.append('en %d banda(s) el texto se encogió para que cupiera a lo ancho'
                      % encogidas)
    if recortadas:
        avisos.append('en %d banda(s) hubo que recortar algún texto: no cabía entero'
                      % recortadas)
    return salida.getvalue(), '; '.join(avisos)
