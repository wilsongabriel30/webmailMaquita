# -*- coding: utf-8 -*-
"""
La tipografía: con qué letra estaba escrito algo y con cuál se reescribe.
=========================================================================

Parte de `ClientePyMuPDF`. Se separó el 29-jul-2026, cuando aquella
clase había llegado a 1.764 líneas y 50 métodos en un solo archivo.

No se usa suelta: `ClientePyMuPDF` hereda de ella, así que desde fuera
se sigue llamando igual que siempre.

Autoría: Equipo de Tecnología Maquita
"""

import io
import logging
import os
import re
from typing import List, Dict, Any, Optional, Tuple

try:
    import fitz  # PyMuPDF
except ImportError:
    fitz = None

from ...dominio.entidades.pagina import Pagina
from ...dominio.excepciones import DocumentoInvalido, PaginaNoEncontrada, RenderError


logger = logging.getLogger(__name__)


# Respuestas de fc-match y fuentes ya cargadas: valen para todo el proceso, las
# fuentes del sistema no cambian mientras el servidor está en pie.
_CACHE_FC_MATCH = {}
_CACHE_FUENTES = {}



# Sufijos de estilo que el nombre PostScript de un span NUNCA trae y el BaseFont del
# documento sí. Hay que quitarlos antes de comparar (ver `_nombre_comparable`).
_SUFIJOS_DE_ESTILO = ('regular', 'book', 'roman', 'normal', 'medium', 'oblique',
                      'bolditalic', 'boldoblique', 'bold', 'italic', 'light')


def _nombre_comparable(nombre: str) -> str:
    """El nombre de una fuente, listo para comparar span contra BaseFont.

    El texto de la pagina dice `LiberationSans` y el documento llama a esa misma
    fuente `Liberation Sans Regular`: comparados tal cual no coincidian NUNCA, asi
    que la fuente incrustada se descartaba y el texto reescrito salia con la
    equivalente del sistema — la letra cambiaba a la vista («al editar una tabla
    cambia el estilo y formato del texto», 31-jul-2026). Se quitan el prefijo de
    subconjunto (`ABCDEF+`), los espacios, los guiones y el sufijo de estilo.
    """
    limpio = (nombre or '').split('+')[-1].lower().replace(' ', '').replace('-', '')
    limpio = limpio.replace('_', '').replace(',', '')
    for sufijo in _SUFIJOS_DE_ESTILO:
        if limpio.endswith(sufijo) and len(limpio) > len(sufijo):
            return limpio[:-len(sufijo)]
    return limpio

# Coletillas que los PDF le cuelgan al nombre de la fuente y que fontconfig no
# entiende: `TimesNewRomanPSMT`, `ArialMT`, `MinionPro`… Se quitan antes de preguntar.
_COLETILLAS_POSTSCRIPT = ('psmt', 'psm', 'mt', 'ps', 'ms', 'std', 'pro', 'w1', 'w0')


def _fuentes_del_documento(doc):
    """Todas las fuentes del documento, miradas una sola vez.

    Recorrer las páginas de una proforma de 130 hojas cuesta, y esto se pregunta
    por cada renglón que se reescribe: se recuerda en el propio documento.
    """
    recordado = getattr(doc, '_faro_fuentes_doc', None)
    if recordado is not None:
        return recordado
    todas, vistas = [], set()
    try:
        for numero in range(doc.page_count):
            for f in doc[numero].get_fonts(full=True):
                if f[0] in vistas:
                    continue
                vistas.add(f[0])
                todas.append(f)
    except Exception:
        logger.debug('no se pudieron listar las fuentes del documento', exc_info=True)
    try:
        doc._faro_fuentes_doc = todas
    except Exception:
        pass
    return todas


def _estilo_del_nombre(nombre: str):
    """¿Ese nombre de fuente es de una negrita? ¿Y de una cursiva?

    Sirve para no confundir a las hermanas de una misma familia: `LiberationSans`
    y `LiberationSans-Bold` son la misma familia —y para comparar familias hay que
    quitarles el apellido, que es lo que hace `_nombre_comparable`—, pero NO son
    la misma letra.
    """
    limpio = (nombre or '').split('+')[-1].lower()
    return (bool(re.search(r'bold|black|heavy|semib|demi', limpio)),
            bool(re.search(r'italic|oblique', limpio)))


def _familias_buscables(nombre: str):
    """Los nombres con los que preguntarle al sistema por esa fuente, del más completo
    al más corto.

    Los PDF guardan el nombre pegado, al estilo PostScript (`DejaVuSans`,
    `TimesNewRomanPSMT`), y así no casa con nada: ni con la tabla de equivalencias ni
    con fontconfig, y el texto acababa reescrito con otra letra (31-jul-2026).

    Se devuelven VARIAS formas porque esos apellidos son ambiguos: `Roman` es el
    «Regular» de las serifs, pero también el apellido de **Times New Roman**. Quitarlo
    a ciegas dejaba «Times New», que no existe, y se perdía la fuente de verdad. Así
    que se va recortando por el final —mientras lo último sea coletilla o estilo— y se
    prueba cada forma por el camino: de `Times New Roman PS Bold MT` salen, en orden,
    `…PS Bold`, `…PS`, `Times New Roman` (que es la buena) y `Times New`.
    """
    limpio = (nombre or '').split('+')[-1].replace('_', ' ').replace('-', ' ')
    # Separar por mayúsculas: DejaVuSans -> DejaVu Sans (respetando siglas seguidas).
    limpio = re.sub(r'(?<=[a-z0-9])(?=[A-Z])', ' ', limpio)
    limpio = re.sub(r'(?<=[A-Z])(?=[A-Z][a-z])', ' ', limpio)
    palabras = [p for p in limpio.split() if p]
    candidatos = []
    while palabras:
        nombre_actual = ' '.join(palabras)
        if nombre_actual not in candidatos:
            candidatos.append(nombre_actual)
        ultima = palabras[-1].lower()
        if ultima in _COLETILLAS_POSTSCRIPT or ultima in _SUFIJOS_DE_ESTILO:
            palabras.pop()
        else:
            break
    return candidatos


# Las 14 fuentes estándar del PDF, por su nombre, con el código que usa PyMuPDF. Un
# documento escrito con ellas —lo que deja la digitalización, por ejemplo— no las lleva
# incrustadas: las trae todo lector. Si el PDF ya usa una, se escribe con esa misma.
_ESTANDAR_POR_NOMBRE = {
    'helvetica': 'helv', 'helveticabold': 'hebo', 'helveticaoblique': 'hobl',
    'helveticaboldoblique': 'hebi', 'arial': 'helv',
    'timesroman': 'tiro', 'timesbold': 'tibo', 'timesitalic': 'tiit',
    'timesbolditalic': 'tibi', 'times': 'tiro',
    'courier': 'cour', 'courierbold': 'cobo', 'courieroblique': 'coit',
    'courierboldoblique': 'cobi',
    'symbol': 'symb', 'zapfdingbats': 'zadb',
}


def _estandar_del_documento(nombre: str):
    """El código de la estándar con la que ya está escrito, o None si no es una.

    Se compara el nombre entero (`Helvetica-Bold` → `helveticabold`), sin el prefijo de
    subconjunto ni guiones: así el estilo viaja con la familia y una negrita sigue
    saliendo negrita.
    """
    if not nombre:
        return None
    limpio = (nombre.split('+')[-1].lower()
              .replace(' ', '').replace('-', '').replace(',', '').replace('_', ''))
    return _ESTANDAR_POR_NOMBRE.get(limpio)


class MezclaLetras(object):
    """La tipografía: con qué letra estaba escrito algo y con cuál se reescribe."""

    def _fuente_del_sistema(self, nombre_fuente: str, negrita: bool, cursiva: bool, texto: str):
        """Fuente instalada que mejor imita a la del documento.

        Devuelve (Font, etiqueta, falta_negrita). `falta_negrita` avisa de que la
        familia elegida NO tiene variante gruesa: fc-match siempre responde algo, y
        pedirle "TeX Gyre Chorus:style=Bold" devuelve su Regular. Sin este aviso, un
        título en Script MT **Bold** se reescribía en fino y cantaba a la legua.
        """
        n = (nombre_fuente or '').split('+')[-1].lower().replace(' ', '')
        familia = None
        # Primero, la familia DE VERDAD: si el servidor tiene la misma fuente del
        # documento, se escribe con ella y la letra no cambia en absoluto. Es el caso
        # corriente con DejaVu, Liberation, Carlito, Caladea o Noto. Solo se acepta si
        # el sistema devuelve esa misma familia (fc-match siempre responde algo).
        for propia in _familias_buscables(nombre_fuente):
            if _nombre_comparable(propia) == _nombre_comparable(
                    self._familia_instalada(propia)):
                familia = propia
                break
        for claves, fam in (self._EQUIVALENTES if not familia else []):
            if any(k in n for k in claves):
                familia = fam
                break
        if not familia:
            generica = self._familia_generica(nombre_fuente)
            familia = {'serif': 'Liberation Serif', 'mono': 'Liberation Mono'}.get(generica, 'Liberation Sans')
        # OJO con el espacio: fontconfig entiende "Bold Italic", pero NO
        # "BoldItalic" — a esa forma responde con la Regular de la familia (y
        # fc-match siempre responde algo). Por eso el texto en negrita cursiva
        # perdía las dos cosas aunque la variante estuviera instalada.
        estilo = ' '.join(p for p in (('Bold' if negrita else ''),
                                      ('Italic' if cursiva else '')) if p)
        patron = familia + (':style=' + estilo if estilo else '')
        # Las fuentes instaladas no cambian mientras el servidor está en pie, y
        # preguntarle a fc-match cuesta un proceso nuevo cada vez: en una tabla
        # de 40 renglones eran 40 procesos y casi un segundo tirado. Se recuerda
        # la respuesta por patrón. (Optimización pedida el 28-jul-2026.)
        salida = _CACHE_FC_MATCH.get(patron)
        if salida is None:
            try:
                import subprocess
                salida = subprocess.run(['fc-match', '-f', '%{file}|%{family}|%{style}', patron],
                                        capture_output=True, text=True, timeout=5).stdout.strip()
            except Exception:
                salida = ''
            _CACHE_FC_MATCH[patron] = salida
        if not salida:
            return None, None, False
        partes = salida.split('|')
        if len(partes) < 3 or not os.path.exists(partes[0]):
            return None, None, False
        # fc-match devuelve la familia y el estilo con TODAS sus traducciones
        # separadas por comas ('Regular,Normal,obycejne,...,Κανονικά'). Nos
        # quedamos con el primer nombre: es el legible, y los demas traen
        # letras que no caben en una cabecera HTTP. (19-ago-2026.)
        ruta = partes[0]
        fam_real = partes[1].split(',')[0].strip()
        est_real = partes[2].split(',')[0].strip()
        # fc-match responde SIEMPRE: si ha caído en otra familia, no sirve
        if familia.split()[0].lower() not in fam_real.lower():
            return None, None, False
        # OJO: la negrita se comprueba sobre TODAS las traducciones del estilo
        # (partes[2] entera), no sobre el primer nombre. fc-match responde
        # 'Negrita,Bold,Negreta,...' y el primero es la traducción al español:
        # buscando 'bold' solo ahí, la Arial Bold de verdad pasaba por «sin
        # negrita» y se le añadía la doble pasada encima — texto engordado y,
        # al releer la tabla, renglones duplicados. (Regresión del arreglo de
        # cabeceras del 19-ago-2026, corregida el mismo día.)
        falta_negrita = negrita and 'bold' not in partes[2].lower()
        try:
            fuente = _CACHE_FUENTES.get(ruta)
            if fuente is None:
                fuente = fitz.Font(fontfile=ruta)
                _CACHE_FUENTES[ruta] = fuente
            if all(fuente.has_glyph(ord(c)) for c in texto if c.strip()):
                etiqueta = fam_real + ' ' + est_real + (' [negrita simulada]' if falta_negrita else '')
                return fuente, etiqueta, falta_negrita
        except Exception:
            pass
        return None, None, False


    def _familia_instalada(self, familia: str) -> str:
        """La familia que el sistema devuelve para ese nombre (vacío si no hay).

        Se recuerda la respuesta: preguntar a fc-match cuesta un proceso, y una tabla
        de 40 renglones lo preguntaría 40 veces.
        """
        if not familia:
            return ''
        clave = 'familia:' + familia
        salida = _CACHE_FC_MATCH.get(clave)
        if salida is None:
            try:
                import subprocess
                salida = subprocess.run(['fc-match', '-f', '%{family}', familia],
                                        capture_output=True, text=True,
                                        timeout=5).stdout.strip()
            except Exception:
                salida = ''
            _CACHE_FC_MATCH[clave] = salida
        # fc-match puede devolver varias familias separadas por coma ("DejaVu Sans,Book")
        return salida.split(',')[0].strip()


    def _familia_generica(self, nombre_fuente: str) -> str:
        n = (nombre_fuente or '').lower()
        if any(k in n for k in ('corsiva', 'calligra', 'script', 'chancery', 'cursive',
                                'handwriting', 'brush', 'italic-script')):
            return 'serif'      # entre las 14 estándar, la cursiva serif es lo menos malo
        if any(k in n for k in ('mono', 'courier', 'consol')):
            return 'mono'
        if any(k in n for k in ('times', 'serif', 'roman', 'georgia', 'garamond',
                                'cambria', 'book', 'minion', 'palatino')) and 'sans' not in n:
            return 'serif'
        return 'sans'



    def _rect_de_las_palabras(self, page, rect):
        """Recorta el recuadro a las palabras que caen DENTRO de él.

        Es la diferencia entre corregir una palabra y destrozar la página: la
        redacción de PyMuPDF borra TODO lo que el recuadro toque, aunque sea el
        rabo de una letra del renglón de al lado. El recuadro que manda el editor
        lleva margen (para tapar tildes) y en documentos con renglones juntos
        invadía las líneas vecinas: desaparecían palabras y el texto quedaba
        mezclado ("CIENCESCUELA DE IAS").

        Se toman solo las palabras cuyo CENTRO está dentro, y se devuelve la unión
        de sus recuadros reales, sin margen. Si no hay ninguna, no se toca nada.
        """
        try:
            palabras = page.get_text('words')
        except Exception:
            return None, ''
        dentro = []
        for x0, y0, x1, y1, palabra, *_ in palabras:
            cx, cy = (x0 + x1) / 2.0, (y0 + y1) / 2.0
            if rect.x0 <= cx <= rect.x1 and rect.y0 <= cy <= rect.y1:
                dentro.append((fitz.Rect(x0, y0, x1, y1), palabra))
        if not dentro:
            return None, ''
        r = dentro[0][0]
        for otra, _ in dentro[1:]:
            r = r | otra
        return r, ' '.join(p for _, p in dentro)


    def _span_representativo(self, page, rect):
        """Span con más superficie dentro del recuadro: de él se toma el estilo."""
        mejor, mejor_area = None, 0.0
        try:
            datos = page.get_text('dict', clip=rect)
        except Exception:
            return None
        for bloque in datos.get('blocks', []):
            for linea in bloque.get('lines', []):
                for span in linea.get('spans', []):
                    r = fitz.Rect(span['bbox']) & rect
                    if r.is_empty:
                        continue
                    area = r.get_area()
                    if area > mejor_area:
                        mejor_area, mejor = area, span
        return mejor


    def _fuente_incrustada(self, doc, page, nombre_span: str, texto: str,
                           negrita=None, cursiva=None):
        """El buffer de la fuente incrustada que sirve para escribir `texto`.

        Se busca por familia —comparando sin el apellido de estilo, que cada PDF
        escribe a su manera— pero se exige que la que se reutilice sea **del
        mismo grosor y la misma inclinación**. Sin eso, en un documento que trae
        `LiberationSans` y `LiberationSans-Bold` las dos casaban con la familia
        y se cogía la primera que apareciera: un texto normal salía en negrita y
        un título en negrita salía fino («me está cambiando el estilo al editar
        una tabla, me vuelve las letras negritas y el original es normal», el
        usuario, 18-ago-2026).

        Si el documento no trae la variante que hace falta, se devuelve None a
        propósito: es mejor una equivalente del sistema **con el grosor bueno**
        que la incrustada con el grosor equivocado.
        """
        if not nombre_span:
            return None
        base_span = _nombre_comparable(nombre_span)
        if negrita is None or cursiva is None:
            del_nombre = _estilo_del_nombre(nombre_span)
            negrita = del_nombre[0] if negrita is None else negrita
            cursiva = del_nombre[1] if cursiva is None else cursiva
        buscado = (bool(negrita), bool(cursiva))

        def _cuadran(fuentes):
            elegidas = []
            for f in fuentes:
                xref, basefont = f[0], f[3]
                if _nombre_comparable(basefont) != base_span:
                    continue
                if _estilo_del_nombre(basefont) != buscado:
                    continue      # misma familia, otra letra: no vale
                elegidas.append(xref)
            return elegidas

        candidatas = _cuadran(page.get_fonts(full=True))
        if not candidatas:
            # En la página no está, pero puede estar en otra: pasa siempre que
            # el texto se va a una PÁGINA NUEVA porque ya no cabía. Esa página
            # nace vacía, así que allí no hay ni una letra que reutilizar y el
            # texto salía con otra tipografía —«al pasar a otra página se
            # distorsiona, cambia el tipo de letra», el usuario, 18-ago-2026—.
            # Las fuentes son del documento entero, no de la hoja.
            candidatas = _cuadran(_fuentes_del_documento(doc))

        for xref in candidatas:
            try:
                _nombre, ext, _tipo2, buffer = doc.extract_font(xref)
            except Exception:
                continue
            if not buffer or ext not in ('ttf', 'otf', 'cff', 'pfa'):
                continue
            try:
                fuente = fitz.Font(fontbuffer=buffer)
                # Un subconjunto de Word solo trae los glifos que el documento usaba:
                # si falta alguno de los que se van a escribir, no vale.
                if all(fuente.has_glyph(ord(c)) for c in texto if c.strip()):
                    return buffer
            except Exception:
                continue
        return None



    def _filas_con_tinta(self, pix):
        """Primera y última fila de píxeles con tinta, o None si no hay ninguna."""
        umbral = 128
        filas = [y for y in range(pix.height)
                 if any(pix.pixel(x, y)[0] < umbral for x in range(pix.width))]
        return (filas[0], filas[-1]) if filas else None


    def _alto_tinta_pixmap(self, pix) -> float:
        """Altura en puntos de las filas que llevan tinta en un pixmap gris."""
        filas = self._filas_con_tinta(pix)
        if not filas:
            return 0.0
        return (filas[1] - filas[0] + 1) * 72.0 / self._PPP_MEDIDA


    def _rect_de_redaccion(self, page, rect, palabras=None, clave=None):
        """Recuadro con el que borrar ese texto sin llevarse por delante a los vecinos.

        La redacción de PyMuPDF elimina todo carácter cuyo RECUADRO toque el suyo, y el
        recuadro de una palabra no es la tinta: va del ascendente al descendente que
        declara la fuente. Con el interlineado justo, el de un renglón se solapa con el
        del siguiente aunque las letras no se toquen, y así desaparecían palabras que
        nadie había editado: en las actas de FARO, cambiar "CUSHUNCHIC" borraba "PEREZ
        MATEOS", que está justo debajo. Ocurría desde siempre; con el re-flujo, que
        reescribe todo el resto del renglón, se habría multiplicado.

        Se recorta en dos pasos, y solo se encoge: nunca se agranda.
          1. hasta donde de verdad hay tinta;
          2. hasta antes del recuadro de cualquier palabra de OTRO renglón que caiga
             encima o debajo.
        El texto que se quiere borrar sigue desapareciendo: para eso basta con que el
        recuadro lo toque, y lo sigue tocando.
        """
        y0, y1 = rect.y0, rect.y1
        try:
            m = fitz.Matrix(self._PPP_MEDIDA / 72.0, self._PPP_MEDIDA / 72.0)
            pix = page.get_pixmap(matrix=m, clip=rect, colorspace=fitz.csGRAY)
            filas = self._filas_con_tinta(pix)
            if filas:
                punto = 72.0 / self._PPP_MEDIDA
                y0 = max(y0, rect.y0 + filas[0] * punto - 0.4)
                y1 = min(y1, rect.y0 + (filas[1] + 1) * punto + 0.4)
        except Exception:
            pass
        if palabras is not None and clave is not None:
            centro = (rect.y0 + rect.y1) / 2.0
            for w in palabras:
                if (w[5], w[6]) == clave:
                    continue
                if w[2] <= rect.x0 or w[0] >= rect.x1:      # no se cruzan en horizontal
                    continue
                if (w[1] + w[3]) / 2.0 < centro:            # renglón de arriba
                    y0 = max(y0, w[3] + 0.1)
                else:                                       # renglón de abajo
                    y1 = min(y1, w[1] - 0.1)
        if y1 - y0 < 1.0:       # no queda banda libre: se borra como se pueda
            return rect
        return fitz.Rect(rect.x0, y0, rect.x1, y1)


    def _alto_tinta_original(self, page, rect) -> float:
        """Altura real de la tinta del texto que hay en el documento, tal como se ve.

        Es la referencia honesta para igualar el tamaño: no depende de lo que la fuente
        declare (ascendentes, descendentes), ni de si el trazo es grueso o fino, ni de si
        la fuente está instalada. Hay que llamarla ANTES de aplicar las redacciones,
        cuando el texto original todavía está en la página.
        """
        try:
            m = fitz.Matrix(self._PPP_MEDIDA / 72.0, self._PPP_MEDIDA / 72.0)
            pix = page.get_pixmap(matrix=m, clip=rect, colorspace=fitz.csGRAY)
            return self._alto_tinta_pixmap(pix)
        except Exception:
            return 0.0


    def _alto_tinta_fuente(self, fuente, texto, tam, simula_negrita=False) -> float:
        """Altura que tendría ESE MISMO texto escrito con la fuente sustituta.

        Se escribe en una página suelta y se mide igual que el original: comparar dos
        medidas hechas del mismo modo, sobre el mismo texto, es lo único que garantiza
        que la palabra reescrita se vea del mismo tamaño que sus vecinas.
        """
        try:
            doc = fitz.open()
            alto = tam * 4 + 20
            page = doc.new_page(width=fuente.text_length(texto, fontsize=tam) + tam * 2 + 20,
                                height=alto)
            base = fitz.Point(tam, alto / 2)
            tw = fitz.TextWriter(page.rect)
            tw.append(base, texto, font=fuente, fontsize=tam)
            if simula_negrita:
                tw.append(fitz.Point(base.x + max(0.25, tam * 0.025), base.y),
                          texto, font=fuente, fontsize=tam)
            tw.write_text(page)
            m = fitz.Matrix(self._PPP_MEDIDA / 72.0, self._PPP_MEDIDA / 72.0)
            pix = page.get_pixmap(matrix=m, colorspace=fitz.csGRAY)
            h = self._alto_tinta_pixmap(pix)
            doc.close()
            return h
        except Exception:
            return 0.0


    def _tam_equivalente(self, fuente, tam, texto_original, ancho_original,
                         alto_original=0.0, simula_negrita=False, alto_tinta=0.0):
        """Cuerpo con el que la fuente sustituta se ve del MISMO tamaño que la original.

        Dos fuentes al mismo número de puntos no se ven igual de grandes, así que hay
        que medir. Y la única medida que de verdad corresponde a lo que ve el usuario es
        **la tinta**: se compara la altura real del texto original en la página con la
        que tendría ese mismo texto escrito con la fuente sustituta. Ahí no hay
        estimaciones —ni ascendentes declarados, ni anchos— y da igual que la fuente sea
        caligráfica, que se esté simulando la negrita o que la palabra lleve o no letras
        altas: se mide dos veces lo mismo, del mismo modo.

        Las métricas declaradas quedan de respaldo, para cuando no se pudo medir la tinta
        (texto sobre fondo oscuro, fragmento vacío). En ese caso manda la altura del span,
        y el ancho solo afina cuando compara cosas comparables:

        - con la negrita simulada NO vale: el texto del documento es grueso y el nuevo es
          fino, así que el ancho original siempre salía mayor y la letra se agrandaba
          (era el caso del título en Script MT Bold: quedaba un 28 % más grande);
        - con varias palabras tampoco: el recuadro incluye los espacios reales del PDF,
          que no coinciden con el espacio de la fuente nueva.

        El tope era de ±15 % y entre dos caligráficas distintas el ajuste necesario se
        salía de él, así que la palabra quedaba más grande por bien que se midiera. Ahora
        es de ±40 %, suficiente para cualquier par realista de fuentes.
        """
        try:
            # 1) Medida directa: tinta contra tinta, el mismo texto
            if alto_tinta and alto_tinta > 0 and texto_original:
                alto_nueva = self._alto_tinta_fuente(fuente, texto_original, tam, simula_negrita)
                if alto_nueva > 0:
                    factor = max(0.6, min(1.4, alto_tinta / alto_nueva))
                    return round(tam * factor, 2)

            # 2) Respaldo: métricas declaradas por las fuentes
            factores = []
            if alto_original and alto_original > 0:
                alto_nuevo = (fuente.ascender - fuente.descender) * tam
                if alto_nuevo > 0:
                    factores.append(alto_original / alto_nuevo)
            texto = (texto_original or '').strip()
            if texto and ancho_original > 0 and not simula_negrita and ' ' not in texto:
                ancho_nuevo = fuente.text_length(texto, fontsize=tam)
                if ancho_nuevo > 0:
                    factores.append(ancho_original / ancho_nuevo)
            if not factores:
                return tam
            factor = 1.0
            for f in factores:
                factor *= f
            factor **= (1.0 / len(factores))     # media geométrica de lo que se pudo medir
            factor = max(0.6, min(1.4, factor))
            return round(tam * factor, 2)
        except Exception:
            return tam


    def _estilo_del_rect(self, page, rect, tam_defecto=11.0, base_defecto=None,
                         medir_tinta=True):
        """Fuente, cuerpo, color y línea base reales del texto que hay en un recuadro.

        `medir_tinta=False` para el texto que solo se va a correr de sitio: se reescribe
        con su misma letra y al mismo cuerpo, así que no hay nada que igualar y se ahorra
        un render.
        """
        span = self._span_representativo(page, rect)
        return self._estilo_de_span(span, rect, tam_defecto, base_defecto, medir_tinta,
                                    page)


    def _estilo_de_span(self, span, rect=None, tam_defecto=11.0, base_defecto=None,
                        medir_tinta=False, page=None):
        """Fuente, cuerpo, color y línea base a partir de un span de PyMuPDF."""
        nombre = span['font'] if span else ''
        if rect is None and span is not None:
            rect = fitz.Rect(span['bbox'])
        return {
            'size': float(span['size']) if span else float(tam_defecto),
            'color': int(span['color']) if span else 0,
            'fuente': nombre,
            # La negrita y la cursiva se detectan por los indicadores del span Y por el
            # nombre de la fuente: hay PDF (los de Word entre ellos) que no marcan el
            # indicador y lo llevan solo en el nombre ("ScriptMTBold", "Arial-BoldMT").
            'negrita': (bool(span['flags'] & 2 ** 4) if span else False) or
                       bool(re.search(r'bold|black|heavy|semib|demi', nombre, re.I)),
            'cursiva': (bool(span['flags'] & 2 ** 1) if span else False) or
                       bool(re.search(r'italic|oblique', nombre, re.I)),
            # línea base real del texto que se va a tapar
            'base': float(span['origin'][1]) if span else (
                base_defecto if base_defecto is not None
                else (rect.y1 if rect is not None else 0.0)),
            # alto del fragmento original: referencia estable para que el texto nuevo se
            # vea del mismo tamaño que el de al lado
            'alto_span': (float(span['bbox'][3]) - float(span['bbox'][1])) if span else 0.0,
            # altura REAL de la tinta del texto que se va a tapar: se mide ahora, que
            # todavía está en la página, y es la referencia con la que se iguala el
            # tamaño del texto nuevo
            'alto_tinta': (self._alto_tinta_original(page, rect)
                           if (medir_tinta and page is not None) else 0.0),
        }


    def _resolver_escritura(self, doc, page, estilo, texto, texto_medida, ancho_original,
                            ajustar_tam=True):
        """Decide CON QUÉ se va a escribir un texto, sin escribirlo todavía.

        Separar la decisión de la escritura es lo que permite re-fluir el renglón: para
        saber cuánto se desplazan las palabras siguientes hay que conocer el ancho que
        va a ocupar el texto nuevo, y ese ancho depende de la fuente y del cuerpo que se
        acaben eligiendo. Tiene que llamarse ANTES de las redacciones: la fuente
        incrustada se lee del documento y el tamaño se calcula midiendo la tinta del
        texto original, que después de redactar ya no está.

        Orden de preferencia, el de siempre:
          1. la fuente incrustada del propio PDF (fidelidad total)
          2. la estándar con la que YA está escrito, si es una de las 14 (también
             fidelidad total: es la misma letra y no hay que incrustarla)
          3. una fuente del sistema métricamente equivalente (Carlito para Calibri,
             Caladea para Cambria, Liberation para Arial/Times/Courier, Chorus para las
             caligráficas)
          4. las 14 estándar, por parecido (último recurso)

        Devuelve un diccionario con la fuente ya construida, el cuerpo definitivo, si
        hay que simular la negrita y la etiqueta para el registro; `tipo` vale
        'original', 'equivalente' o 'estandar'.

        `ajustar_tam=False` deja el cuerpo tal cual lo declara el documento: es lo que
        se quiere al recolocar una palabra que el usuario no ha tocado, donde no hay
        nada que igualar y cambiar el cuerpo solo puede empeorarlo.
        """
        if not texto.strip():
            return None
        tam = estilo['size']
        buffer = self._fuente_incrustada(doc, page, estilo['fuente'], texto,
                                         estilo.get('negrita'), estilo.get('cursiva'))
        if buffer:
            try:
                return {'tipo': 'original', 'font': fitz.Font(fontbuffer=buffer),
                        'tam': tam, 'simula_negrita': False,
                        'etiqueta': 'original:' + (estilo['fuente'] or '?')}
            except Exception as e:
                logger.warning(f"No se pudo usar la fuente incrustada ({estilo['fuente']}): {e}")
        # ¿El documento ya está escrito con una de las 14 estándar? Entonces se escribe
        # con ESA MISMA: es la misma letra, exacta, y no hay nada que incrustar. Sin
        # esto, un documento digitalizado —que queda todo en Helvetica— acababa con lo
        # editado en otra letra (31-jul-2026).
        propia_estandar = _estandar_del_documento(estilo['fuente'])
        if propia_estandar:
            try:
                # `estandar14` dice que esta letra se puede escribir SIN incrustar
                # nada, con la misma estándar que ya usa el documento. Quien
                # escriba lo aprovecha (ver `letras_base14.py`): si no, el texto
                # editado acababa llamándose `NimbusSans` —el clon que trae
                # PyMuPDF— mientras el resto de la página seguía en `Helvetica`.
                return {'tipo': 'original', 'font': fitz.Font(fontname=propia_estandar),
                        'tam': tam, 'simula_negrita': False,
                        'estandar14': propia_estandar,
                        'etiqueta': 'original:' + (estilo['fuente'] or '?')}
            except Exception as e:
                logger.warning('No se pudo usar la estándar %s: %s', propia_estandar, e)

        fsis, nombre_sis, falta_negrita = self._fuente_del_sistema(
            estilo['fuente'], estilo['negrita'], estilo['cursiva'], texto)
        if fsis:
            try:
                # Al usar una fuente equivalente (p. ej. Chorus en lugar de Corsiva) el
                # mismo cuerpo en puntos puede verse más alto o más bajo. Se ajusta para
                # que las letras midan LO MISMO que las del texto original.
                if ajustar_tam:
                    tam = self._tam_equivalente(fsis, tam, texto_medida, ancho_original,
                                                estilo.get('alto_span', 0.0), falta_negrita,
                                                estilo.get('alto_tinta', 0.0))
                return {'tipo': 'equivalente', 'font': fsis, 'tam': tam,
                        'simula_negrita': falta_negrita,
                        'etiqueta': 'equivalente:' + nombre_sis +
                                    ' (doc: ' + (estilo['fuente'] or '?') + ')'}
            except Exception as e:
                logger.warning(f"No se pudo usar la fuente del sistema {nombre_sis}: {e}")
        base14 = self._BASE14[(self._familia_generica(estilo['fuente']),
                               estilo['negrita'], estilo['cursiva'])]
        return {'tipo': 'estandar', 'font': fitz.Font(fontname=base14), 'tam': tam,
                'simula_negrita': False, 'estandar14': base14,
                'etiqueta': 'estandar:' + base14 + ' (doc: ' + (estilo['fuente'] or '?') + ')'}


    def _desplazamiento_negrita(self, tam: float) -> float:
        """Cuánto se separa la segunda pasada con la que se simula la negrita."""
        return max(0.25, tam * 0.025)


    def _ancho_escrito(self, res, texto: str) -> float:
        """Ancho real que ocupará el texto ya escrito, negrita simulada incluida."""
        ancho = res['font'].text_length(texto, fontsize=res['tam'])
        if res['simula_negrita']:
            ancho += self._desplazamiento_negrita(res['tam'])
        return ancho


    def _se_escriben_igual(self, res, chars) -> bool:
        """¿Ese texto se puede volver a escribir sin que se note el cambio de letra?

        Se pregunta del texto que el usuario NO ha tocado y que hay que recolocar para
        re-fluir el renglón: reescribirlo con otra letra sería peor que el solape que se
        quiere evitar. Con la fuente incrustada del propio PDF no hay nada que discutir;
        con una equivalente, se comprueba midiendo.

        La comprobación es sobre el AVANCE DE CADA LETRA, no sobre el ancho de la
        palabra: hay generadores que justifican separando las letras (el acta de FARO
        pone 0,44 pt entre cada par), y comparando anchos de palabra ese espaciado se
        confunde con una fuente de otras proporciones. Lo que importa es que la
        diferencia sea **la misma en todas las letras** —eso es espaciado, y como cada
        carácter se recoloca en su sitio exacto, da igual—: si varía de una letra a otra,
        la fuente sustituta tiene otras proporciones y el renglón se dejaría sin correr.
        """
        if res['tipo'] == 'original':
            return True
        if res['simula_negrita']:
            return False
        diferencias = []
        for a, b in zip(chars, chars[1:]):
            if not a['c'].strip() or not b['c'].strip():
                continue
            avance = b['origin'][0] - a['origin'][0]
            if avance <= 0:
                continue
            diferencias.append(avance - res['font'].text_length(a['c'], fontsize=res['tam']))
        if not diferencias:
            # Un solo carácter: no hay avances que comparar, se mira su ancho
            visibles = [c for c in chars if c['c'].strip()]
            if not visibles:
                return False
            ancho_doc = visibles[-1]['bbox'][2] - visibles[0]['bbox'][0]
            texto = ''.join(c['c'] for c in visibles)
            return abs(self._ancho_escrito(res, texto) - ancho_doc) <= 0.6
        return (max(diferencias) - min(diferencias)) <= 0.6
