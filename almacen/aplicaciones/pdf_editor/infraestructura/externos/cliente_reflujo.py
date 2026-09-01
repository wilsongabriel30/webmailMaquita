# -*- coding: utf-8 -*-
"""
Cambiar texto dentro del PDF y recomponer el renglón.
=====================================================

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

from . import letras_base14
from ...dominio.entidades.pagina import Pagina
from ...dominio.excepciones import DocumentoInvalido, PaginaNoEncontrada, RenderError


logger = logging.getLogger(__name__)


# Respuestas de fc-match y fuentes ya cargadas: valen para todo el proceso, las
# fuentes del sistema no cambian mientras el servidor está en pie.
_CACHE_FC_MATCH = {}
_CACHE_FUENTES = {}


class MezclaReflujo(object):
    """Cambiar texto dentro del PDF y recomponer el renglón."""

    def _parrafo_alrededor(self, page, rect):
        """¿El recuadro editado está dentro de un bloque de texto de varios
        renglones? Solo entonces tiene sentido recomponer el párrafo."""
        try:
            centro = ((rect.x0 + rect.x1) / 2.0, (rect.y0 + rect.y1) / 2.0)
            for bloque in page.get_text('dict')['blocks']:
                caja = fitz.Rect(bloque['bbox'])
                # Basta un renglon: en muchos PDF cada renglon del parrafo es
                # su propio bloque, y parrafos_pdf sabe recomponerlo igual
                # (lo que sobre baja y lo de debajo se empuja).
                if (bloque.get('lines')
                        and caja.x0 <= centro[0] <= caja.x1
                        and caja.y0 <= centro[1] <= caja.y1):
                    return caja
        except Exception:
            pass
        return None

    def _recomponer_parrafos(self, datos, aplazadas, usadas):
        """Aplica las ediciones que no cabían en su renglón recomponiendo el
        párrafo entero. Devuelve (bytes, cuántas se aplicaron).

        La palabra nueva entra en el texto del párrafo en el sitio de la vieja
        y `parrafos_pdf.reemplazar` reacomoda los renglones: lo que sobra baja
        al renglón siguiente y lo de debajo del párrafo se empuja — lo mismo
        que hace un procesador de textos al escribir en medio de un párrafo.
        """
        from . import parrafos_pdf
        aplicadas = 0
        for item in aplazadas:
            rect, viejo = item['rect'], item['texto_dentro']
            try:
                info = parrafos_pdf.parrafo_en(datos, item['pagina'],
                                               (rect.x0 + rect.x1) / 2.0,
                                               (rect.y0 + rect.y1) / 2.0)
                caja = info.get('bbox') if isinstance(info, dict) else None
                texto_parrafo = (info.get('texto') or '') if isinstance(info, dict) else ''
                if not caja or viejo not in texto_parrafo:
                    usadas.append('[no cabía en el renglón y no se encontró su '
                                  'párrafo: sin aplicar]')
                    continue
                nuevo_parrafo = self._sustituir_en_parrafo(
                    datos, item, texto_parrafo, viejo)
                datos, aviso = parrafos_pdf.reemplazar(
                    datos, item['pagina'], list(caja), nuevo_parrafo)
                etiqueta = '%s [párrafo recompuesto]' % item['res']['etiqueta'] \
                    if item.get('res') else '[párrafo recompuesto]'
                if aviso:
                    etiqueta += ' ' + aviso
                usadas.append(etiqueta)
                aplicadas += 1
            except Exception as excepcion:
                logger.warning('No se pudo recomponer el párrafo de "%s": %s',
                               viejo[:30], excepcion)
                usadas.append('[no se pudo recomponer el párrafo: sin aplicar]')
        return datos, aplicadas

    def _sustituir_en_parrafo(self, datos, item, texto_parrafo, viejo):
        """El texto del párrafo con la palabra editada ya sustituida.

        Si la palabra aparece varias veces, se elige la ocurrencia por su
        posición: se cuenta cuántas veces aparece ANTES del recuadro editado.
        """
        nuevo = item['texto']
        if texto_parrafo.count(viejo) == 1:
            return texto_parrafo.replace(viejo, nuevo, 1)
        rect = item['rect']
        ocurrencia = 0
        try:
            d = fitz.open(stream=datos, filetype='pdf')
            try:
                page = d[item['pagina'] - 1]
                antes = []
                for w in page.get_text('words'):
                    cy = (w[1] + w[3]) / 2.0
                    if cy < rect.y0 - 0.5 or (rect.y0 - 0.5 <= cy <= rect.y1 + 0.5
                                              and w[2] <= rect.x0 + 0.5):
                        antes.append(w[4])
                ocurrencia = (' '.join(antes)).count(viejo)
            finally:
                d.close()
        except Exception:
            ocurrencia = 0
        partes = texto_parrafo.split(viejo)
        if ocurrencia >= len(partes) - 1:
            ocurrencia = len(partes) - 2
        return (viejo.join(partes[:ocurrencia + 1]) + nuevo
                + viejo.join(partes[ocurrencia + 1:]))

    def _reparto_del_reflujo(self, rect, cola, delta, limite, justificado):
        """Cuánto se corre cada palabra de la cola. None si el renglón no cabe.

        En un párrafo justificado el renglón termina en el margen: correrlo entero se
        saldría. Lo que hace un procesador de textos es repartir la diferencia entre los
        espacios del renglón, y eso es lo que se hace aquí —sin tocar más del 40 % de
        cada espacio, que es donde deja de disimularse—; lo que no se pueda absorber se
        corre, y si aun así no cabe, el renglón se queda como estaba.

        En un párrafo con el margen derecho suelto no hay nada que repartir: la cola se
        corre entera y los espacios se conservan exactamente.
        """
        huecos = [cola[0][0].x0 - rect.x1]
        for i in range(len(cola) - 1):
            huecos.append(cola[i + 1][0].x0 - cola[i][0].x1)
        absorbido = [0.0] * len(huecos)
        if justificado:
            margen = [max(0.0, h) * 0.4 for h in huecos]
            capacidad = sum(margen)
            if capacidad > 0:
                objetivo = min(abs(delta), capacidad)
                signo = -1.0 if delta > 0 else 1.0
                absorbido = [signo * objetivo * (m / capacidad) for m in margen]
        dx, acumulado = [], delta
        for i in range(len(cola)):
            acumulado += absorbido[i]
            dx.append(acumulado)
        if cola[-1][0].x1 + dx[-1] > limite:
            return None
        return dx


    def _dx_en(self, dx, cola, x):
        """Desplazamiento que le toca a lo que hay en la posición x."""
        valor = dx[0]
        for i, (r, _p) in enumerate(cola):
            if r.x0 <= x + 0.1:
                valor = dx[i]
        return valor


    def _trozos_a_correr(self, doc, page, cola, dx):
        """El texto de la cola, ya colocado en su sitio nuevo, carácter a carácter.

        Se recoloca CADA LETRA en la posición que tenía más lo que le toque correrse. Así
        se conserva el espaciado real del documento —incluido el de los PDF que justifican
        separando las letras— y el renglón corrido queda idéntico salvo por el
        desplazamiento.

        Devuelve None si alguna parte no se puede reescribir con una letra que se vea
        igual: en ese caso es preferible no correr el renglón.
        """
        union = cola[0][0]
        for r, _p in cola[1:]:
            union = union | r
        try:
            datos = page.get_text('rawdict')
        except Exception:
            return None
        trozos = []
        for bloque in datos.get('blocks', []):
            for linea in bloque.get('lines', []):
                for span in linea.get('spans', []):
                    chars = [c for c in span.get('chars', [])
                             if union.y0 <= c['origin'][1] <= union.y1 + 0.5
                             and union.x0 - 0.5 <= c['origin'][0] <= union.x1 + 0.5]
                    visibles = [c for c in chars if c['c'].strip()]
                    if not visibles:
                        continue
                    estilo = self._estilo_de_span(span)
                    texto = ''.join(c['c'] for c in visibles)
                    res = self._resolver_escritura(doc, page, estilo, texto, texto,
                                                   0.0, ajustar_tam=False)
                    if res is None or not self._se_escriben_igual(res, chars):
                        logger.warning("No se re-fluye el renglón: '%s' no se puede "
                                       "reescribir con la misma letra" % texto[:40])
                        return None
                    puestos = [(c['c'], c['origin'][0] + self._dx_en(dx, cola, c['origin'][0]),
                                c['origin'][1]) for c in visibles]
                    trozos.append({'letras': puestos, 'res': res, 'estilo': estilo,
                                   'texto': texto, 'rect': union, 'dx': 0.0,
                                   'es_cola': True})
        return trozos or None


    def _cola_del_renglon(self, page, rect):
        """Palabras del MISMO renglón que quedan a la derecha del recuadro editado.

        Son las que hay que correr cuando la palabra nueva no mide lo mismo que la
        vieja. Devuelve (cola, límite): la cola en orden de izquierda a derecha y hasta
        dónde puede crecer el renglón sin invadir lo que tenga a su derecha (otra
        columna, una tabla) o salirse de la página.

        Se apoya en la numeración de bloque/línea/palabra de PyMuPDF, no en las
        coordenadas: en un texto justificado los huecos entre palabras varían y agrupar
        "por proximidad" acabaría metiendo palabras del renglón de al lado.
        """
        try:
            palabras = page.get_text('words')
        except Exception:
            return None, [], 0.0
        dentro = [w for w in palabras
                  if rect.x0 <= (w[0] + w[2]) / 2.0 <= rect.x1
                  and rect.y0 <= (w[1] + w[3]) / 2.0 <= rect.y1]
        if not dentro:
            return None, [], 0.0
        lineas = {(w[5], w[6]) for w in dentro}
        if len(lineas) != 1:
            return None, [], 0.0        # el recuadro pisa dos renglones: no se re-fluye
        clave = lineas.pop()
        ultima = max(w[7] for w in dentro)
        cola = [(fitz.Rect(w[0], w[1], w[2], w[3]), w[4])
                for w in palabras if (w[5], w[6]) == clave and w[7] > ultima]
        cola.sort(key=lambda c: c[0].x0)
        limite = page.rect.x1 - 5
        fin = cola[-1][0].x1 if cola else rect.x1
        for w in palabras:
            if (w[5], w[6]) == clave:
                continue
            if w[3] <= rect.y0 or w[1] >= rect.y1:      # no comparte banda vertical
                continue
            if w[0] >= fin:
                limite = min(limite, w[0] - 2)
        return clave, cola, limite, self._renglon_justificado(palabras, clave)


    def _renglon_justificado(self, palabras, clave) -> bool:
        """¿Ese renglón termina alineado con el margen derecho de su párrafo?

        Se mira si al menos dos renglones del mismo bloque acaban en el mismo sitio y el
        nuestro es uno de ellos. En un párrafo justificado eso pasa siempre; en uno con
        el margen suelto, casi nunca. De ello depende si la diferencia de ancho se
        reparte entre los espacios (justificado) o se corre el renglón entero.
        """
        derechas = {}
        for w in palabras:
            if w[5] != clave[0]:
                continue
            k = (w[5], w[6])
            derechas[k] = max(derechas.get(k, 0.0), w[2])
        if len(derechas) < 2 or clave not in derechas:
            return False
        tope = max(derechas.values())
        en_el_margen = [k for k, v in derechas.items() if v >= tope - 0.6]
        return len(en_el_margen) >= 2 and clave in en_el_margen


    def reemplazar_texto_desde_bytes(self, datos_bytes: bytes, ediciones: list) -> bytes:
        """Sustituye fragmentos de texto conservando la tipografía original.

        Cada edición: {pagina (1-based), x, y, ancho, alto, texto}
        en coordenadas de canvas (y=0 arriba, unidades = puntos PDF a zoom 1),
        que es justo lo que guarda el editor.
        """
        try:
            doc = fitz.open(stream=datos_bytes, filetype='pdf')
            aplicadas, con_fuente_original = 0, 0
            usadas = []           # traza de qué fuente se usó en cada fragmento

            # Ediciones que no caben en su renglón y van a recomponer su párrafo
            aplazadas = []
            # Se agrupan por página: apply_redactions() se ejecuta una vez por página
            por_pagina = {}
            for ed in ediciones:
                por_pagina.setdefault(int(ed.get('pagina', 1)), []).append(ed)

            for num_pagina, lista in por_pagina.items():
                idx = num_pagina - 1
                if idx < 0 or idx >= len(doc):
                    continue
                page = doc[idx]
                pendientes = []

                # Cuántas ediciones caen en cada renglón: si hay más de una, los
                # desplazamientos se pisarían entre sí y ese renglón no se re-fluye
                renglones_tocados = {}
                # Foto de las palabras de la página ANTES de tocar nada: con ella se
                # recorta cada redacción para que no invada los renglones vecinos
                try:
                    palabras_pagina = page.get_text('words')
                except Exception:
                    palabras_pagina = []

                for ed in lista:
                    x = float(ed.get('x', 0)); y = float(ed.get('y', 0))
                    w = float(ed.get('ancho', 0)); h = float(ed.get('alto', 0))
                    if w <= 0 or h <= 0:
                        continue
                    rect_pedido = fitz.Rect(x, y, x + w, y + h)
                    # Se ajusta a las palabras que de verdad están dentro: así la
                    # redacción no muerde los renglones de arriba y de abajo
                    rect, texto_dentro = self._rect_de_las_palabras(page, rect_pedido)
                    if rect is None:
                        logger.warning('Edición ignorada: no hay texto dentro del recuadro indicado')
                        continue
                    texto = ed.get('texto', '')
                    estilo = self._estilo_del_rect(page, rect, ed.get('tam', 11), y + h * 0.8)
                    # La fuente y el cuerpo se deciden AQUÍ, con el texto original aún en
                    # la página: hace falta saber cuánto va a medir el texto nuevo para
                    # poder correr el resto del renglón.
                    res = self._resolver_escritura(doc, page, estilo, texto,
                                                   texto_dentro, rect.width)
                    clave, cola, limite, justificado = self._cola_del_renglon(page, rect)
                    caja_parrafo = self._parrafo_alrededor(page, rect)
                    if caja_parrafo is not None:
                        # El renglón no debe crecer más allá de su párrafo: si
                        # no cabe ahí, lo suyo es recomponer el párrafo, no
                        # invadir el margen. Dos puntos de cortesía por los
                        # redondeos del justificado.
                        limite = min(limite, caja_parrafo.x1 + 2.0)
                    if clave is not None:
                        renglones_tocados[clave] = renglones_tocados.get(clave, 0) + 1
                    item_nuevo = {'rect': rect, 'texto': texto, 'estilo': estilo,
                                  'res': res, 'dx': 0.0, 'cola': True,
                                  'clave': clave, 'palabras_cola': cola,
                                  'limite': limite, 'justificado': justificado,
                                  'texto_dentro': texto_dentro,
                                  'caja_parrafo': caja_parrafo,
                                  'pagina': num_pagina}
                    pendientes.append(item_nuevo)
                    # Borrado real del texto original (sin pintar nada encima:
                    # así se conserva el fondo que hubiera, sea blanco o de color).
                    # La anotación se guarda: si luego resulta que el renglón no
                    # cabe y hay que recomponer el párrafo, se retira sin aplicar.
                    item_nuevo['anotacion'] = page.add_redact_annot(
                        self._rect_de_redaccion(page, rect, palabras_pagina, clave))

                # ---- Re-flujo del renglón -------------------------------------
                # Sustituir una palabra por otra más larga la hacía crecer hacia la
                # derecha y quedarse encima de la siguiente; más corta, dejaba un hueco.
                # Aquí se corren las palabras que van detrás, en el mismo renglón, la
                # diferencia exacta de ancho.
                #
                # El texto de la cola se REESCRIBE, así que solo se corre si se puede
                # volver a escribir con una letra que se vea igual: cambiarle la
                # tipografía a un texto que el usuario no ha tocado sería peor que el
                # solape que se quiere evitar.
                for item in list(pendientes):
                    if not item.pop('cola', False):
                        continue
                    res, rect, cola = item['res'], item['rect'], item['palabras_cola']
                    if res is None:
                        continue                        # línea que se deja vacía
                    if not cola:
                        # Última palabra del renglón: no hay nada que correr,
                        # pero el texto nuevo tampoco puede salirse del párrafo.
                        fin = rect.x0 + self._ancho_escrito(res, item['texto'])
                        if (item.get('caja_parrafo') is not None
                                and fin > item['limite']):
                            try:
                                page.delete_annot(item['anotacion'])
                            except Exception:
                                pass
                            pendientes.remove(item)
                            aplazadas.append(item)
                        continue
                    if renglones_tocados.get(item['clave'], 0) > 1:
                        logger.warning('Renglón con varias ediciones: no se re-fluye')
                        continue
                    delta = self._ancho_escrito(res, item['texto']) - rect.width
                    if abs(delta) < 0.5:
                        continue                        # cabe igual: no se toca nada
                    dx = self._reparto_del_reflujo(rect, cola, delta, item['limite'],
                                                   item['justificado'])
                    if dx is None:
                        if item.get('caja_parrafo') is not None:
                            # El renglón no cabe, pero está dentro de un párrafo:
                            # se retira esta edición del camino normal y se
                            # recompone el párrafo entero al final, que es lo que
                            # haría un procesador de textos. (20-ago-2026.)
                            try:
                                page.delete_annot(item['anotacion'])
                            except Exception:
                                pass
                            pendientes.remove(item)
                            aplazadas.append(item)
                            continue
                        logger.warning('El renglón no cabe re-fluido (límite %.1f): '
                                       'se deja sin correr' % item['limite'])
                        item['desbordado'] = True
                        continue
                    trozos = self._trozos_a_correr(doc, page, cola, dx)
                    if not trozos:
                        continue
                    for t in trozos:
                        pendientes.append(t)
                    for rect_p, _palabra in cola:
                        page.add_redact_annot(self._rect_de_redaccion(
                            page, rect_p, palabras_pagina, item['clave']))
                    item['reflujo'] = round(delta, 2)

                if not pendientes:
                    continue
                # Sin tocar imágenes ni dibujos: solo desaparece el texto
                page.apply_redactions(images=fitz.PDF_REDACT_IMAGE_NONE,
                                      graphics=fitz.PDF_REDACT_LINE_ART_NONE)
                # IMPRESCINDIBLE: tras aplicar redacciones la página queda obsoleta en
                # memoria y todo lo que se escriba sobre ella se pierde al guardar
                page = doc.reload_page(page)

                # La escritura ya no decide nada: la fuente y el cuerpo se resolvieron
                # antes de redactar (hacía falta para poder re-fluir el renglón). Aquí
                # solo se pinta cada fragmento en su sitio, corrido `dx` si es una
                # palabra de la cola.
                #
                # NO se encoge el texto: el usuario pidió que el tamaño se mantenga
                # igual al original. Si lo que escribe es más largo que la palabra que
                # sustituye, ahora el renglón se recoloca en vez de solaparse.
                for item in pendientes:
                    estilo, res, texto = item['estilo'], item['res'], item['texto']
                    if not item.get('es_cola'):
                        aplicadas += 1
                    if res is None:
                        continue      # línea que el usuario dejó vacía: solo se borra
                    color_int = estilo['color']
                    color = ((color_int >> 16) & 255) / 255.0, ((color_int >> 8) & 255) / 255.0, (color_int & 255) / 255.0
                    punto = fitz.Point(item['rect'].x0 + item['dx'], estilo['base'])
                    try:
                        tw = fitz.TextWriter(page.rect, color=color)
                        if item.get('letras'):
                            # Texto recolocado: cada letra en su sitio exacto
                            for letra, lx, ly in item['letras']:
                                sitio = fitz.Point(lx, ly)
                                # Con la estándar del documento se escribe sin
                                # incrustar nada y la letra queda idéntica.
                                if letras_base14.escribir(page, sitio, letra,
                                                          res, color):
                                    continue
                                tw.append(sitio, letra,
                                          font=res['font'], fontsize=res['tam'])
                            tw.write_text(page)
                            continue
                        if letras_base14.escribir(page, punto, texto, res, color):
                            continue
                        tw.append(punto, texto, font=res['font'], fontsize=res['tam'])
                        if res['simula_negrita']:
                            # La familia no trae variante gruesa: se engorda escribiendo
                            # el mismo texto con un desplazamiento mínimo, el recurso
                            # clásico de "negrita falsa".
                            desp = self._desplazamiento_negrita(res['tam'])
                            tw.append(fitz.Point(punto.x + desp, punto.y), texto,
                                      font=res['font'], fontsize=res['tam'])
                        tw.write_text(page)
                    except Exception as e:
                        logger.warning(f"No se pudo escribir '{texto}' con {res['etiqueta']}: {e}")
                        continue
                    if item.get('es_cola'):
                        continue      # palabra corrida: no es una edición del usuario
                    if res['tipo'] == 'original':
                        con_fuente_original += 1
                    etiqueta = res['etiqueta']
                    if item.get('reflujo'):
                        etiqueta += ' [renglón corrido %+.2f pt]' % item['reflujo']
                    elif item.get('desbordado'):
                        etiqueta += ' [no cabe re-fluido: sin correr]'
                    usadas.append(etiqueta)

            buf = io.BytesIO()
            # garbage=2 (compactar), NO 4. El nivel 4 recolecta toda la basura del
            # documento y deduplica objetos y streams: eso es lo que se quiere al
            # COMPRIMIR un PDF, no al cambiar una palabra. Medido sobre un documento de
            # 130 páginas: garbage=4 tarda 7,5 s y garbage=2 tarda 0,31 s —24 veces
            # menos— con el mismo tamaño de archivo. Ese guardado era prácticamente
            # toda la espera que notaba el usuario al aplicar una corrección.
            #
            # Lo que se pierde: encadenando 10 ediciones el archivo acaba en 1,35 MB en
            # vez de 1,10 MB, porque no se recogen los restos de las anteriores. Es
            # asumible, y quien necesite el archivo mínimo tiene "Comprimir un PDF".
            # Lo que NO se pierde: el texto sustituido sigue sin poder recuperarse del
            # archivo (comprobado buscándolo también dentro de los streams comprimidos).
            # De eso se encarga apply_redactions, no el nivel de garbage.
            doc.save(buf, garbage=2, deflate=True)
            doc.close()
            datos_finales = buf.getvalue()
            if aplazadas:
                datos_finales, recompuestas = self._recomponer_parrafos(
                    datos_finales, aplazadas, usadas)
                aplicadas += recompuestas
            logger.warning(f"Texto reemplazado: {aplicadas} fragmento(s), "
                           f"{con_fuente_original} con la fuente original del documento. "
                           f"Detalle: {usadas}")
            # Registro propio: el logger de la app no siempre acaba en el archivo y
            # sin esta traza no hay forma de saber POR QUÉ una edición salió con otra
            # letra en el documento de un usuario concreto.
            try:
                import datetime
                with open('/home/sistemas/Maquita/logs/pdf_reemplazos.log', 'a') as f:
                    f.write('%s | %d fragmento(s) | original=%d | %s\n' % (
                        datetime.datetime.now().isoformat(timespec='seconds'),
                        aplicadas, con_fuente_original, usadas))
            except Exception:
                pass
            self.ultimo_detalle_fuentes = usadas
            return datos_finales
        except Exception as e:
            logger.error(f"Error reemplazando texto: {e}")
            raise DocumentoInvalido(f"Error al reemplazar texto: {e}")
