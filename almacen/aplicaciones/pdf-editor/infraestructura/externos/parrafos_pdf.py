# -*- coding: utf-8 -*-
"""
Edición de texto POR PÁRRAFO, como en un procesador de textos.
===============================================================
«necesito que me dejes cambiar texto por párrafo no por palabra, igualito que
si fuera un word» — el usuario, 27-jul-2026.

Hasta ahora el doble clic abría **una palabra**. Aquí se abre el **párrafo
entero**: el usuario lo reescribe como quiera —más largo, más corto, con otras
palabras— y al guardar el párrafo se vuelve a componer solo, repartiendo el
texto en renglones dentro del mismo ancho, con la misma letra y el mismo
interlineado que tenía.

Lo que se respeta: el tipo de letra (la incrustada del propio PDF cuando se
puede), el cuerpo, la negrita, la cursiva, el color, la sangría de la primera
línea, la alineación y la separación entre renglones.

El límite honesto, y por qué existe: un PDF **no tiene flujo**. Si el texto
nuevo necesita más renglones de los que caben en el hueco que hay hasta lo
siguiente de la página, no se puede "empujar" el resto sin descuadrarlo todo.
En ese caso se aprieta un poco el interlineado y, si aun así no entra, se avisa
y se deja el párrafo como estaba en vez de pisar lo que hay debajo.

Autoría: Equipo de Tecnología Maquita — 2026-07-27
"""

import logging

import fitz

from . import letras_base14

from . import guardado_pdf
from . import tablas_escritura as escritura

logger = logging.getLogger(__name__)

# Cuánto se puede apretar el interlineado antes de que el párrafo se vea mal
APRETADO_MAXIMO = 0.82
# Aire que se le respeta a lo que venga debajo
RESPIRO_ABAJO = 1.5


def _cliente():
    from .cliente_pymupdf import ClientePyMuPDF
    return ClientePyMuPDF()


def _texto_legible(texto):
    """Espacios y guiones normales para editar.

    Al reescribir, el motor guarda los espacios como espacio duro (U+00A0) y el
    guion como guion blando (U+00AD): el documento se ve igual, pero si ese
    texto vuelve al cuadro de edición el usuario acaba guardando esos caracteres
    otra vez. Se normaliza al leer. (28-jul-2026.)
    """
    return (texto or '').replace('\u00a0', ' ').replace('\u00ad', '-')


def _bloques_con_texto(pagina):
    for bloque in pagina.get_text('dict')['blocks']:
        lineas = [l for l in bloque.get('lines', [])
                  if any(s['text'].strip() for s in l['spans'])]
        if lineas:
            yield bloque, lineas


def _lineas_de(lineas):
    salida = []
    for linea in lineas:
        spans = [s for s in linea['spans'] if s['text'].strip()]
        if not spans:
            continue
        salida.append({
            'texto': ''.join(s['text'] for s in spans).rstrip(),
            'rect': fitz.Rect(linea['bbox']),
            'base': max(s['origin'][1] for s in spans),
            'span': spans[0],
        })
    return salida


def parrafo_en(contenido_pdf, numero_pagina, x, y):
    """El párrafo que hay en ese punto de la página, listo para editarlo.

    Devuelve None si ahí no hay texto. Las coordenadas van en puntos PDF con el
    origen arriba, que es como trabaja el visor.
    """
    documento = guardado_pdf.abrir_para_leer(contenido_pdf)
    try:
        indice = int(numero_pagina) - 1
        if indice < 0 or indice >= documento.page_count:
            return None
        pagina = documento[indice]
        punto = fitz.Point(float(x), float(y))

        # ¿Ese punto está dentro de una tabla? Entonces no es cosa del cuadro de
        # párrafo: se edita la celda en su sitio, con la letra del documento.
        celda = _celda_en(contenido_pdf, numero_pagina, punto)
        if celda is not None:
            return celda

        elegido = None
        for bloque, lineas in _bloques_con_texto(pagina):
            caja = fitz.Rect(bloque['bbox'])
            if punto in caja:
                elegido = (bloque, lineas, caja)
                break
        if elegido is None:
            # Un poco de tolerancia: el clic rara vez cae dentro del rectángulo
            # exacto, sobre todo en renglones finos
            mejor, distancia_mejor = None, 6.0
            for bloque, lineas in _bloques_con_texto(pagina):
                caja = fitz.Rect(bloque['bbox'])
                distancia = max(caja.x0 - punto.x, punto.x - caja.x1,
                                caja.y0 - punto.y, punto.y - caja.y1, 0.0)
                if distancia < distancia_mejor:
                    mejor, distancia_mejor = (bloque, lineas, caja), distancia
            elegido = mejor
        if elegido is None:
            return None

        bloque, lineas_crudas, caja = elegido
        lineas = _lineas_de(lineas_crudas)
        if not lineas:
            return None

        return {
            'bbox': [round(v, 2) for v in caja],
            'texto': _texto_corrido(lineas, caja),
            'lineas': len(lineas),
            'tam': round(max(l['span'].get('size', 10.0) for l in lineas), 1),
            'sitio_abajo': round(_sitio_libre_abajo(pagina, caja), 1),
        }
    finally:
        documento.close()


def _texto_corrido(lineas, caja):
    """El párrafo como se lee, no como está impreso.

    En un PDF cada renglón es una línea suelta: el salto está donde acabó la
    línea al imprimir, no donde el autor quiso cortar. Si eso se le da tal cual
    al cuadro de edición, el usuario ve saltos y huecos que en su documento no
    existen —y al guardar cada renglón se recompone por separado, así que esos
    cortes se quedan grabados en el PDF (reporte del usuario, 28-jul-2026).

    Aquí los renglones se unen con un espacio, y solo se conserva el salto
    cuando de verdad lo hay: un renglón que acaba **claramente antes** del
    margen derecho y va seguido de algo que empieza como frase nueva (mayúscula,
    viñeta o número). Eso distingue el final de un párrafo o de un punto de una
    lista del simple final de línea.
    """
    if not lineas:
        return ''
    derecha = max(l['rect'].x1 for l in lineas)
    ancho = max(1.0, derecha - min(l['rect'].x0 for l in lineas))
    partes = [lineas[0]['texto'].rstrip()]
    for anterior, actual in zip(lineas, lineas[1:]):
        texto = actual['texto'].strip()
        if not texto:
            continue
        previo = partes[-1]
        # ¿El renglón anterior se quedó corto? (no llegó al margen del párrafo)
        corto = (derecha - anterior['rect'].x1) > ancho * 0.12
        empieza_frase = texto[:1].isupper() or texto[:1] in '•-–·*' or (
            texto[:2].rstrip('.').isdigit() and texto[:1].isdigit())
        if corto and empieza_frase:
            partes.append(texto)                     # salto de verdad
        elif previo.endswith('-') and texto[:1].islower():
            partes[-1] = previo[:-1] + texto         # palabra cortada con guion
        else:
            partes[-1] = previo + ' ' + texto        # mismo párrafo, sigue
    return _texto_legible('\n'.join(partes))


def _celda_en(contenido_pdf, numero_pagina, punto):
    """La celda de tabla que hay en ese punto, si la hay.

    Se apoya en el reconocimiento de tablas, que además está recordado por
    contenido: si el editor acaba de pintar los controles, esto no cuesta nada.
    """
    try:
        from . import tablas_pdf
        tablas = tablas_pdf.detectar(contenido_pdf, numero_pagina)
    except Exception:
        return None
    for tabla in tablas or []:
        # SOLO tablas con rayas de verdad. El reconocimiento por texto agrupa
        # cualquier párrafo en columnas y daría por «celda» un texto corriente:
        # el doble clic dejaría de abrir el párrafo en media página.
        if tabla.get('estrategia') != 'lines':
            continue
        columnas, filas = tabla.get('columnas') or [], tabla.get('filas_y') or []
        if len(columnas) < 3 or len(filas) < 2:
            continue
        if not (columnas[0] <= punto.x <= columnas[-1]
                and filas[0] <= punto.y <= filas[-1]):
            continue
        columna = next((i for i in range(len(columnas) - 1)
                        if columnas[i] <= punto.x <= columnas[i + 1]), None)
        fila = next((i for i in range(len(filas) - 1)
                     if filas[i] <= punto.y <= filas[i + 1]), None)
        if columna is None or fila is None:
            continue
        return {'en_tabla': True, 'tabla': tabla.get('indice', 0),
                'fila': fila, 'columna': columna}
    return None


def _sitio_libre_abajo(pagina, caja):
    """Cuánto puede crecer el párrafo hacia abajo sin pisar nada."""
    limite = pagina.rect.height - 30.0
    try:
        for bloque, _lineas in _bloques_con_texto(pagina):
            otra = fitz.Rect(bloque['bbox'])
            if otra == caja or otra.y0 < caja.y1 - 0.5:
                continue
            if otra.x1 > caja.x0 and otra.x0 < caja.x1:
                limite = min(limite, otra.y0)
        for imagen in pagina.get_image_info():
            otra = fitz.Rect(imagen['bbox'])
            if otra.y0 >= caja.y1 - 0.5 and otra.x1 > caja.x0 and otra.x0 < caja.x1:
                limite = min(limite, otra.y0)
    except Exception:
        pass
    return max(0.0, limite - caja.y1 - RESPIRO_ABAJO)


def reemplazar(contenido_pdf, numero_pagina, bbox, texto_nuevo):
    """Sustituye el párrafo por el texto nuevo, recomponiéndolo. (pdf, aviso)."""
    cliente = _cliente()
    documento = guardado_pdf.abrir(contenido_pdf)
    try:
        indice = int(numero_pagina) - 1
        if indice < 0 or indice >= documento.page_count:
            raise ValueError('Esa página no existe.')
        pagina = documento[indice]
        caja = fitz.Rect(*[float(v) for v in bbox])

        # El párrafo que de verdad hay ahí (el bbox viene del navegador y puede
        # llegar con algún decimal de diferencia)
        elegido = None
        for bloque, lineas in _bloques_con_texto(pagina):
            otra = fitz.Rect(bloque['bbox'])
            if abs(otra.y0 - caja.y0) < 2 and abs(otra.x0 - caja.x0) < 2:
                elegido = (otra, _lineas_de(lineas))
                break
        if elegido is None:
            raise ValueError('Ese párrafo ya no está en la página.')
        caja, lineas = elegido

        primera = lineas[0]
        estilo = cliente._estilo_de_span(primera['span'], primera['rect'], 10.0,
                                         primera['base'], False, pagina)
        # El interlineado real del párrafo, medido entre sus renglones
        if len(lineas) > 1:
            saltos = [lineas[i + 1]['base'] - lineas[i]['base']
                      for i in range(len(lineas) - 1)]
            interlineado = sorted(saltos)[len(saltos) // 2]
        else:
            interlineado = estilo['size'] * 1.15

        # La sangría de la primera línea se conserva: si el párrafo empezaba
        # más adentro, el texto nuevo también.
        sangria = primera['rect'].x0 - caja.x0
        izquierda_resto = min(l['rect'].x0 for l in lineas)
        ancho = caja.x1 - izquierda_resto
        alineacion = _alineacion(lineas, caja)

        resolucion = cliente._resolver_escritura(
            documento, pagina, estilo, texto_nuevo or ' ', primera['texto'],
            primera['rect'].width, ajustar_tam=False)
        if resolucion is None:
            raise ValueError('No se pudo preparar la letra del párrafo.')

        # Repartir el texto: se respetan los saltos que el usuario haya escrito
        renglones = []
        for trozo in (texto_nuevo or '').split('\n'):
            trozo = trozo.strip()
            if not trozo:
                renglones.append('')
                continue
            primera_libre = ancho - (sangria if not renglones else 0)
            renglones.extend(escritura.partir(trozo, resolucion, max(10.0, primera_libre)))

        # ¿Cabe de alto? Si no, se HACE SITIO empujando lo de abajo —el mismo
        # camino que las tablas: baja lo que haga falta y lo que no quepa pasa
        # de página—. Antes se negaba («no cabe, acórtalo»); el usuario pidió
        # poder editar igual que en la tabla (vídeo del 19-ago-2026). Solo si
        # el empuje falla se aprieta el interlineado, y negarse queda de último
        # recurso.
        sitio = _sitio_libre_abajo(pagina, caja) + (caja.y1 - primera['base'])
        necesario = (len(renglones) - 1) * interlineado
        aviso_empuje = ''
        if necesario > sitio:
            from .empuje_pagina import empujar
            falta = necesario - sitio + 2.0
            try:
                aviso_empuje = empujar(documento, int(numero_pagina),
                                       caja.y1 + 0.5, falta) or ''
                sitio += falta
            except Exception as excepcion:
                logger.warning('no se pudo hacer sitio bajo el párrafo: %s',
                               excepcion)
        apretado = 1.0
        while necesario > sitio and apretado > APRETADO_MAXIMO:
            apretado -= 0.02
            necesario = (len(renglones) - 1) * interlineado * apretado
        if necesario > sitio:
            raise ValueError(
                'El texto nuevo no cabe en el hueco de ese párrafo: necesitaría '
                '%d renglones y solo hay sitio para %d. Acórtalo un poco, o edítalo '
                'en varios pasos.'
                % (len(renglones), int(sitio / max(1.0, interlineado)) + 1))
        interlineado *= apretado

        # Fuera el párrafo viejo (solo su recuadro, nada más de la página)
        anotacion = pagina.add_redact_annot(caja)
        anotacion.update()
        try:
            pagina.apply_redactions(images=fitz.PDF_REDACT_IMAGE_NONE,
                                             graphics=fitz.PDF_REDACT_LINE_ART_NONE)
        except (TypeError, AttributeError):
            pagina.apply_redactions()

        color = escritura.color_de(estilo)
        try:
            escritor = fitz.TextWriter(pagina.rect, color=color)
            for numero, renglon in enumerate(renglones):
                if not renglon:
                    continue
                x0 = izquierda_resto + (sangria if numero == 0 else 0)
                medida = resolucion['font'].text_length(renglon, fontsize=resolucion['tam'])
                if alineacion == 'derecha':
                    x0 = caja.x1 - medida
                elif alineacion == 'centro':
                    x0 = izquierda_resto + (ancho - medida) / 2
                punto = fitz.Point(x0, primera['base'] + numero * interlineado)
                # Si la letra del documento es una de las catorce estándar, se
                # escribe con ESA MISMA y sin incrustar nada: el párrafo editado
                # queda con el mismo nombre de fuente que el resto de la página.
                if letras_base14.escribir(pagina, punto, renglon, resolucion, color):
                    continue
                escritor.append(punto, renglon, font=resolucion['font'],
                                fontsize=resolucion['tam'])
                if resolucion['simula_negrita']:
                    desplazamiento = cliente._desplazamiento_negrita(resolucion['tam'])
                    escritor.append(fitz.Point(punto.x + desplazamiento, punto.y),
                                    renglon, font=resolucion['font'],
                                    fontsize=resolucion['tam'])
            escritor.write_text(pagina)
        except Exception as excepcion:
            raise ValueError('No se pudo escribir el párrafo: %s' % excepcion)

        # Y el camino de vuelta: si el párrafo nuevo ocupa MENOS que el viejo,
        # lo de abajo sube a cerrar el hueco — y lo que se hubiera ido a otra
        # hoja vuelve, con las páginas vacías eliminadas. Es el gemelo del
        # empuje de arriba; sin esto el editor bajaba pero no subía («el momento
        # que le reduzco, el texto que viene debajo también debería subirse»,
        # vídeo del 19-ago-2026). Al final del todo: recomponer pinta en la
        # página y no debe pisarse con las redacciones del propio párrafo.
        aviso_recogida = ''
        visibles = [n for n, r in enumerate(renglones) if r]
        fondo_nuevo = (primera['base'] + (visibles[-1] if visibles else 0)
                       * interlineado + 2.0)
        liberado = caja.y1 - fondo_nuevo
        if not aviso_empuje and liberado > max(6.0, interlineado * 0.8):
            from .recoger_pagina import recoger
            try:
                aviso_recogida = recoger(documento, int(numero_pagina),
                                         caja.y1 + 0.5, -liberado) or ''
            except Exception as excepcion:
                logger.warning('no se pudo recomponer bajo el párrafo: %s',
                               excepcion)

        avisos = []
        if aviso_empuje:
            avisos.append(aviso_empuje)
        if aviso_recogida:
            avisos.append(aviso_recogida)
        if apretado < 1.0:
            avisos.append('se juntaron un poco los renglones para que cupiera')
        if resolucion['tipo'] != 'original':
            avisos.append('se usó una letra equivalente (%s)' % resolucion['etiqueta'])
        return guardado_pdf.guardar(documento), '; '.join(avisos)
    finally:
        guardado_pdf.cerrar(documento)


def _alineacion(lineas, caja):
    """izquierda · centro · derecha, mirando cómo se apoyan los renglones."""
    if len(lineas) < 2:
        return 'izquierda'
    izquierdas = [l['rect'].x0 for l in lineas]
    derechas = [l['rect'].x1 for l in lineas]
    dispersion_izq = max(izquierdas) - min(izquierdas)
    dispersion_der = max(derechas) - min(derechas)
    if dispersion_der < 1.5 and dispersion_izq > 3:
        return 'derecha'
    if dispersion_izq > 3 and dispersion_der > 3:
        centros = [(l['rect'].x0 + l['rect'].x1) / 2 for l in lineas]
        if max(centros) - min(centros) < 3:
            return 'centro'
    return 'izquierda'
