# -*- coding: utf-8 -*-
"""
Empujar hacia abajo lo que hay bajo una tabla, SOLO en su página.
==================================================================
«que si yo agrego una fila el texto se desplace hacia abajo de todo el
documento no importa que se agreguen más páginas» — el usuario, 27-jul-2026.

Primero se probó reconstruyendo el documento entero (`reflujo_docx.py`): el
texto sí se desplazaba, pero la proforma real pasaba de **65 a 94 páginas** y la
tabla acababa en otra hoja. Reconstruir un PDF no es reversible, así que se
descartó y el usuario pidió esta vía:

  **mover solo lo de ESA página, y lo que se salga pasa a una página nueva.**

Lo que se sale de esa página empuja la siguiente, y así en cascada hasta el
final del documento — que es lo que pidió después el usuario: «lo que ya no
alcance al editar se modifique todo el documento».

Cómo se hace, y por qué así: no se puede "empujar" un PDF, pero sí leer lo que
hay en la banda de abajo —renglones con su tipografía, dibujos e imágenes—,
borrar esa banda y volver a dibujarlo todo más abajo. Lo que no cabe en la hoja
se dibuja en una página nueva insertada justo detrás, empezando por el margen
superior.

Lo que se conserva: el texto sigue siendo TEXTO (seleccionable y editable, no
una foto), con su letra, cuerpo, color y posición horizontal; las imágenes, con
su tamaño y su sitio; y los trazos (líneas y rectángulos) con su grosor y color.

Lo que no: rellenos complejos, degradados y recortes raros del dibujo vectorial
se redibujan de forma simple. Por eso el editor **avisa** cuando la banda que
hay que mover contiene dibujo vectorial complicado.

Autoría: Equipo de Tecnología Maquita — 2026-07-27
"""

import logging

import fitz

logger = logging.getLogger(__name__)

MARGEN_SUPERIOR_NUEVA = 56.0     # dónde empieza el contenido en la página nueva
MARGEN_INFERIOR = 36.0           # hasta dónde se puede dibujar en una hoja
# Aire entre lo último que se empuja y el pie de página. El usuario lo pidió
# «considerable»: 30 pt es algo más de un centímetro, la separación que deja
# un documento de oficina entre el cuerpo y el pie. Con 12 pt el texto llegaba
# a quedar visualmente pegado al pie en páginas muy llenas.
RESPIRO_PIE = 30.0
# Un pie va SEPARADO del cuerpo. Si entre el bloque y lo anterior no hay al
# menos este hueco en blanco, es el último párrafo, no un pie.
HUECO_MINIMO_PIE = 14.0


def _cliente():
    from .cliente_pymupdf import ClientePyMuPDF
    return ClientePyMuPDF()


def _renglones_bajo(pagina, y_desde, cliente):
    """Renglones de texto por debajo de una altura, con su tipografía.

    Se guarda además la posición de CADA LETRA: los párrafos justificados llevan
    las letras separadas a mano para cuadrar el margen, y reescribir el renglón
    de una pieza perdía ese espaciado (*"Hobby Store s i endo UNICO"*).
    """
    salida = []
    letras_por_linea = {}
    try:
        for bloque in pagina.get_text('rawdict')['blocks']:
            for linea in bloque.get('lines', []):
                caracteres = []
                for span in linea['spans']:
                    for caracter in span.get('chars', []):
                        if caracter['c'].strip():
                            caracteres.append((caracter['c'], caracter['origin'][0],
                                               caracter['origin'][1]))
                if caracteres:
                    letras_por_linea[tuple(round(v, 1) for v in linea['bbox'])] = caracteres
    except Exception:
        pass

    for bloque in pagina.get_text('dict')['blocks']:
        for linea in bloque.get('lines', []):
            spans = [s for s in linea['spans'] if s['text'].strip()]
            if not spans:
                continue
            caja = fitz.Rect(linea['bbox'])
            if caja.y0 < y_desde - 0.5:
                continue
            salida.append({
                'texto': ''.join(s['text'] for s in spans).rstrip(),
                'rect': caja,
                'base': max(s['origin'][1] for s in spans),
                'span': spans[0],
                'letras': letras_por_linea.get(tuple(round(v, 1) for v in linea['bbox'])),
                'estilo': cliente._estilo_de_span(spans[0], caja, 10.0,
                                                  max(s['origin'][1] for s in spans),
                                                  False, pagina),
            })
    return salida


def _imagenes_bajo(pagina, y_desde):
    """Imágenes por debajo de una altura, con sus bytes para volver a ponerlas."""
    salida = []
    documento = pagina.parent
    try:
        for info in pagina.get_image_info(xrefs=True):
            caja = fitz.Rect(info['bbox'])
            if caja.y0 < y_desde - 0.5 or not info.get('xref'):
                continue
            try:
                datos = documento.extract_image(info['xref'])
            except Exception:
                continue
            salida.append({'rect': caja, 'bytes': datos['image']})
    except Exception as excepcion:
        logger.warning('no se pudieron leer las imágenes de la banda: %s', excepcion)
    return salida


def _trazos_bajo(pagina, y_desde):
    """Líneas y rectángulos por debajo de una altura."""
    salida, complejos = [], 0
    try:
        for dibujo in pagina.get_drawings():
            caja = fitz.Rect(dibujo['rect'])
            if caja.y0 < y_desde - 0.5:
                continue
            piezas = []
            for elemento in dibujo['items']:
                if elemento[0] == 'l':
                    piezas.append(('l', fitz.Point(elemento[1]), fitz.Point(elemento[2])))
                elif elemento[0] == 're':
                    piezas.append(('re', fitz.Rect(elemento[1])))
                else:
                    complejos += 1
            if piezas:
                salida.append({
                    'piezas': piezas,
                    'color': dibujo.get('color') or (0, 0, 0),
                    'relleno': dibujo.get('fill'),
                    'grosor': max(0.3, dibujo.get('width') or 0.75),
                })
    except Exception as excepcion:
        logger.warning('no se pudieron leer los trazos de la banda: %s', excepcion)
    return salida, complejos


def _pintar(pagina, cliente, documento, renglones, imagenes, trazos, dy, recorte=None):
    """Dibuja la banda desplazada `dy`. `recorte` limita qué se pinta aquí.

    La letra resuelta SE RECUERDA por estilo dentro de la llamada: resolverla
    busca la fuente incrustada en el documento y eso costaba ~14 ms por
    renglón — recomponer una tesis de 130 páginas tardaba minuto y medio, casi
    todo en re-resolver la misma Times de siempre. Con la memoria, una vez por
    estilo; y como la elección depende de que la fuente tenga TODAS las letras
    del texto, un acierto solo vale si las tiene (si no, se resuelve de nuevo).
    """
    letras_vistas = {}
    for renglon in renglones:
        if recorte and not recorte(renglon['rect'].y0 + dy):
            continue
        estilo = renglon['estilo']
        clave = (estilo.get('fuente'), estilo.get('size'),
                 estilo.get('negrita'), estilo.get('cursiva'))
        resolucion = letras_vistas.get(clave)
        if resolucion is not None:
            try:
                if not all(resolucion['font'].has_glyph(ord(c))
                           for c in renglon['texto'] if c.strip()):
                    resolucion = None
            except Exception:
                resolucion = None
        if resolucion is None:
            resolucion = cliente._resolver_escritura(
                documento, pagina, estilo, renglon['texto'], renglon['texto'],
                renglon['rect'].width, ajustar_tam=False)
            if resolucion:
                letras_vistas[clave] = resolucion
        if not resolucion:
            continue
        color_entero = renglon['estilo']['color']
        color = (((color_entero >> 16) & 255) / 255.0,
                 ((color_entero >> 8) & 255) / 255.0, (color_entero & 255) / 255.0)
        try:
            escritor = fitz.TextWriter(pagina.rect, color=color)
            if renglon.get('letras'):
                # Cada letra en su sitio exacto, solo que más abajo: así el
                # espaciado de los párrafos justificados se mantiene igual.
                # Pero escribirlas de una en una costaba un minuto en un
                # documento largo: las letras que caen donde la fuente las
                # pondría sola se escriben en una tanda, y solo se corta la
                # tanda donde el espaciado real se aparta (los huecos del
                # justificado). El punto de arranque de cada tanda es el
                # registrado, así que el papel queda idéntico.
                fuente, tam = resolucion['font'], resolucion['tam']
                letras = renglon['letras']
                indice = 0
                while indice < len(letras):
                    caracter, x0, y0 = letras[indice]
                    texto = caracter
                    x_fin = x0 + fuente.text_length(caracter, tam)
                    indice += 1
                    while indice < len(letras):
                        caracter, cx, cy = letras[indice]
                        if abs(cy - y0) > 0.01 or abs(cx - x_fin) > 0.25:
                            break
                        texto += caracter
                        x_fin = cx + fuente.text_length(caracter, tam)
                        indice += 1
                    escritor.append(fitz.Point(x0, y0 + dy), texto,
                                    font=fuente, fontsize=tam)
                escritor.write_text(pagina)
                continue
            escritor.append(fitz.Point(renglon['rect'].x0, renglon['base'] + dy),
                            renglon['texto'], font=resolucion['font'],
                            fontsize=resolucion['tam'])
            if resolucion['simula_negrita']:
                paso = cliente._desplazamiento_negrita(resolucion['tam'])
                escritor.append(fitz.Point(renglon['rect'].x0 + paso, renglon['base'] + dy),
                                renglon['texto'], font=resolucion['font'],
                                fontsize=resolucion['tam'])
            escritor.write_text(pagina)
        except Exception as excepcion:
            logger.warning('no se pudo recolocar "%s": %s', renglon['texto'][:24], excepcion)

    for imagen in imagenes:
        destino = fitz.Rect(imagen['rect'].x0, imagen['rect'].y0 + dy,
                            imagen['rect'].x1, imagen['rect'].y1 + dy)
        if recorte and not recorte(destino.y0):
            continue
        try:
            # `keep_proportion=False`, y no es un detalle: por defecto PyMuPDF
            # encaja la imagen dentro del recuadro respetando SU proporción y la
            # centra, así que una firma de 140x50 pt volvía a colocarse de
            # 100x50 —más estrecha— solo por haber bajado de sitio. El recuadro
            # de destino ya es el que tenía, medido en el papel: se respeta tal
            # cual. (18-ago-2026.)
            pagina.insert_image(destino, stream=imagen['bytes'],
                                keep_proportion=False, overlay=True)
        except Exception as excepcion:
            logger.warning('no se pudo recolocar una imagen: %s', excepcion)

    for trazo in trazos:
        forma = pagina.new_shape()
        pintado = False
        for pieza in trazo['piezas']:
            if pieza[0] == 'l':
                inicio = fitz.Point(pieza[1].x, pieza[1].y + dy)
                fin = fitz.Point(pieza[2].x, pieza[2].y + dy)
                if recorte and not recorte(inicio.y):
                    continue
                forma.draw_line(inicio, fin)
                pintado = True
            else:
                caja = fitz.Rect(pieza[1].x0, pieza[1].y0 + dy,
                                 pieza[1].x1, pieza[1].y1 + dy)
                if recorte and not recorte(caja.y0):
                    continue
                forma.draw_rect(caja)
                pintado = True
        if pintado:
            try:
                forma.finish(color=trazo['color'], fill=trazo['relleno'],
                             width=trazo['grosor'])
                forma.commit()
            except Exception:
                pass


def _firma_de_bloque(bloque):
    """Una identificación del bloque que no dependa de la página: su texto y su
    posición redondeada. Los encabezados coinciden en las dos cosas."""
    texto = ''
    for linea in bloque.get('lines', []):
        for span in linea['spans']:
            texto += span['text']
    caja = bloque['bbox']
    return (' '.join(texto.split())[:60], round(caja[0]), round(caja[1]))


def zonas_fijas(documento, numero_pagina):
    """(fin del encabezado, principio del pie) de esa página, en puntos.

    Se considera encabezado —o pie— lo que aparece **igual y en el mismo sitio**
    en otras páginas: es lo que distingue un membrete de un párrafo cualquiera.
    Se miran hasta tres páginas vecinas, que es de sobra para reconocerlo, y solo
    se acepta como fijo lo que esté en la franja de arriba (o de abajo) de la
    hoja: así un párrafo repetido en medio de la página no se confunde.
    """
    pagina = documento[numero_pagina - 1]
    alto = pagina.rect.height
    franja_alta, franja_baja = alto * 0.22, alto * 0.80

    vecinas = []
    for otra in (numero_pagina - 2, numero_pagina, numero_pagina + 1):
        if 0 <= otra < documento.page_count and otra != numero_pagina - 1:
            vecinas.append(otra)
        if len(vecinas) >= 3:
            break
    firmas_vecinas = set()
    alturas_vecinas = []
    for indice in vecinas:
        try:
            for bloque in documento[indice].get_text('dict')['blocks']:
                if bloque.get('lines'):
                    firmas_vecinas.add(_firma_de_bloque(bloque))
                    alturas_vecinas.append((bloque['bbox'][1], bloque['bbox'][3]))
        except Exception:
            pass

    fin_encabezado, inicio_pie = 0.0, alto
    try:
        bloques = pagina.get_text('dict')['blocks']
        for bloque in bloques:
            if not bloque.get('lines'):
                continue
            caja = bloque['bbox']
            # Coincidir en altura NO basta: en un documento de renglones
            # uniformes, el último del cuerpo también coincide y se tomaba por
            # pie. Hace falta que además el texto se parezca (membrete o pie
            # fijo) o que el bloque vaya SEPARADO del cuerpo, que es lo que
            # distingue un pie de un párrafo.
            mismo_texto = _firma_de_bloque(bloque) in firmas_vecinas
            if not mismo_texto:
                if not _altura_repetida(caja, alturas_vecinas):
                    continue
                if not _va_separado(bloques, caja):
                    continue
            if caja[3] <= franja_alta:
                fin_encabezado = max(fin_encabezado, caja[3])
            elif caja[1] >= franja_baja:
                inicio_pie = min(inicio_pie, caja[1])
    except Exception:
        pass

    # Un membrete suele llevar logo y a veces una raya: también son fijos
    try:
        for imagen in pagina.get_image_info():
            caja = imagen['bbox']
            if caja[3] <= franja_alta:
                fin_encabezado = max(fin_encabezado, caja[3])
            elif caja[1] >= franja_baja:
                inicio_pie = min(inicio_pie, caja[1])
        for dibujo in pagina.get_drawings():
            caja = dibujo['rect']
            if caja[3] <= franja_alta and (caja[2] - caja[0]) > pagina.rect.width * 0.4:
                fin_encabezado = max(fin_encabezado, caja[3])
            elif caja[1] >= franja_baja and (caja[2] - caja[0]) > pagina.rect.width * 0.4:
                inicio_pie = min(inicio_pie, caja[1])
    except Exception:
        pass

    if fin_encabezado:
        fin_encabezado += 6.0        # un respiro para no pegarse al membrete
    return fin_encabezado, inicio_pie


def _va_separado(bloques, caja):
    """¿Hay un hueco en blanco claro entre este bloque y lo que tiene encima?

    Un pie de página siempre va despegado del cuerpo; el último párrafo, no.
    Ese hueco es lo que permite distinguirlos cuando el texto no se repite.
    Recibe los bloques ya leídos de la página: releerlos aquí costaba más que
    todo el resto del cálculo junto.
    """
    fondo_anterior = 0.0
    try:
        for bloque in bloques:
            if not bloque.get('lines'):
                continue
            otra = bloque['bbox']
            if otra[3] <= caja[1] + 0.5:      # está por encima
                fondo_anterior = max(fondo_anterior, otra[3])
    except Exception:
        return False
    if not fondo_anterior:
        return True                            # no hay nada encima: es un pie
    return (caja[1] - fondo_anterior) >= HUECO_MINIMO_PIE


def _altura_repetida(caja, alturas_vecinas, tolerancia=2.5):
    """¿Hay algo a esta misma altura en las páginas vecinas?

    Es lo que permite reconocer un pie cuyo texto cambia en cada hoja (el
    número de página, por ejemplo): el texto no coincide, pero el sitio sí.
    """
    for arriba, abajo in alturas_vecinas:
        if abs(arriba - caja[1]) <= tolerancia and abs(abajo - caja[3]) <= tolerancia:
            return True
    return False


def _leer_banda(pagina, y_desde, cliente):
    """Lo que hay bajo una altura: renglones, imágenes y trazos."""
    renglones = _renglones_bajo(pagina, y_desde, cliente)
    imagenes = _imagenes_bajo(pagina, y_desde)
    trazos, complejos = _trazos_bajo(pagina, y_desde)
    return renglones, imagenes, trazos, complejos


def _borrar_banda_entre(pagina, y_desde, y_hasta):
    """Borra solo la franja de en medio: el encabezado y el pie se quedan."""
    banda = fitz.Rect(0, y_desde, pagina.rect.width, y_hasta)
    if banda.height <= 0:
        return
    anotacion = pagina.add_redact_annot(banda)
    anotacion.update()
    try:
        pagina.apply_redactions(graphics=fitz.PDF_REDACT_LINE_ART_REMOVE_IF_TOUCHED)
    except TypeError:
        pagina.apply_redactions()


def _borrar_banda(pagina, y_desde):
    banda = fitz.Rect(0, y_desde, pagina.rect.width, pagina.rect.height)
    anotacion = pagina.add_redact_annot(banda)
    anotacion.update()
    try:
        pagina.apply_redactions(graphics=fitz.PDF_REDACT_LINE_ART_REMOVE_IF_TOUCHED)
    except TypeError:
        pagina.apply_redactions()


def _reparte(renglones, imagenes, trazos, dy, limite):
    """Separa lo que sigue cabiendo de lo que se sale de la hoja."""
    def alto_de(elemento, tipo):
        if tipo == 'l':
            return (elemento[1].y if elemento[0] == 'l' else elemento[1].y0) + dy
        return elemento['rect'].y0 + dy

    # Se mira dónde ACABA cada cosa, no dónde empieza: un bloque que empieza
    # justo antes del límite pero termina más abajo se salía igualmente, y era
    # lo que dejaba el texto pegado al pie pese al respiro.
    cabe_r = [r for r in renglones if r['rect'].y1 + dy < limite]
    fuera_r = [r for r in renglones if r['rect'].y1 + dy >= limite]
    cabe_i = [i for i in imagenes if i['rect'].y1 + dy < limite]
    fuera_i = [i for i in imagenes if i['rect'].y1 + dy >= limite]
    cabe_t, fuera_t = [], []
    for trazo in trazos:
        dentro = [p for p in trazo['piezas']
                  if (p[1].y if p[0] == 'l' else p[1].y0) + dy < limite]
        afuera = [p for p in trazo['piezas']
                  if (p[1].y if p[0] == 'l' else p[1].y0) + dy >= limite]
        if dentro:
            cabe_t.append(dict(trazo, piezas=dentro))
        if afuera:
            fuera_t.append(dict(trazo, piezas=afuera))
    return (cabe_r, cabe_i, cabe_t), (fuera_r, fuera_i, fuera_t)


def _arriba_de(renglones, imagenes, trazos, dy):
    """La y más alta del conjunto, ya desplazado."""
    valores = [r['rect'].y0 + dy for r in renglones]
    valores += [i['rect'].y0 + dy for i in imagenes]
    valores += [(p[1].y if p[0] == 'l' else p[1].y0) + dy
                for t in trazos for p in t['piezas']]
    return min(valores) if valores else 0.0


def _abajo_de(renglones, imagenes, trazos, dy):
    """La y más baja del conjunto, ya desplazado."""
    valores = [r['rect'].y1 + dy for r in renglones]
    valores += [i['rect'].y1 + dy for i in imagenes]
    valores += [(p[2].y if p[0] == 'l' else p[1].y1) + dy
                for t in trazos for p in t['piezas']]
    return max(valores) if valores else 0.0


def empujar(documento, numero_pagina, y_desde, dy):
    """Baja `dy` lo que hay bajo `y_desde`, y **sigue por todo el documento**.

    Lo que se sale de esa página empuja la siguiente, y lo que se salga de esa,
    la de después — hasta el final. Solo si al final sigue sobrando algo se
    crean páginas nuevas. Devuelve un aviso (o cadena vacía).
    """
    cliente = _cliente()
    pagina = documento[numero_pagina - 1]
    _tope, pie_propio = zonas_fijas(documento, numero_pagina)
    limite = min(pagina.rect.height - MARGEN_INFERIOR, pie_propio - RESPIRO_PIE)

    renglones, imagenes, trazos, complejos = _leer_banda(pagina, y_desde, cliente)
    # El pie de esta página no se empuja: se queda donde está
    if pie_propio < pagina.rect.height:
        renglones = [r for r in renglones if r['rect'].y1 <= pie_propio]
        imagenes = [i for i in imagenes if i['rect'].y1 <= pie_propio]
    if not (renglones or imagenes or trazos):
        return ''      # bajo la tabla no hay nada que empujar

    # Se borra hasta donde de verdad llega lo que se va a mover, no solo hasta
    # `limite`: lo que quedaba entre el limite y el pie no se borraba y, como
    # SI se volvia a dibujar (aqui o en la pagina siguiente), salia DUPLICADO
    # -- «me estas duplicando las palabras», el usuario, 28-jul-2026.
    fondo = _abajo_de(renglones, imagenes, trazos, 0.0)
    hasta = max(limite + 2.0, fondo + 2.0)
    if pie_propio < pagina.rect.height:
        hasta = min(hasta, pie_propio - 0.5)      # el pie no se toca
    # Y tampoco debe empezar por encima del primer renglon que SI se mueve: uno
    # que cruce la linea de corte no se lee (se queda donde esta), pero la
    # redaccion borra todo lo que TOCA la banda y desaparecia del documento.
    techo = max(y_desde, _arriba_de(renglones, imagenes, trazos, 0.0) - 0.5)
    _borrar_banda_entre(pagina, techo, hasta)
    cabe, sobra = _reparte(renglones, imagenes, trazos, dy, limite)
    _pintar(pagina, cliente, documento, cabe[0], cabe[1], cabe[2], dy)

    paginas_creadas = 0
    numero = numero_pagina
    # Cada vuelta: el sobrante de la página anterior se coloca arriba de la
    # siguiente, y lo que había en ella baja lo que ese sobrante ocupa.
    while sobra[0] or sobra[1] or sobra[2]:
        numero += 1
        arriba = _arriba_de(sobra[0], sobra[1], sobra[2], dy)
        subir = arriba - MARGEN_SUPERIOR_NUEVA        # para pegarlo al margen
        alto_sobrante = _abajo_de(sobra[0], sobra[1], sobra[2], dy - subir)

        if numero > documento.page_count:
            siguiente = documento.new_page(width=pagina.rect.width,
                                           height=pagina.rect.height)
            paginas_creadas += 1
            _pintar(siguiente, cliente, documento, sobra[0], sobra[1], sobra[2],
                    dy - subir)
            break

        siguiente = documento[numero - 1]
        # El encabezado y el pie de esa página son FIJOS: ni se mueven ni se
        # pisan. Lo que llega empieza por debajo del membrete, y lo que se
        # empuja es solo lo de en medio. (Reporte en vídeo del usuario.)
        tope, pie = zonas_fijas(documento, numero)
        limite_sig = min(siguiente.rect.height - MARGEN_INFERIOR,
                         pie - RESPIRO_PIE)
        arranque = max(tope, MARGEN_SUPERIOR_NUEVA)
        subir = arriba - arranque
        alto_sobrante = _abajo_de(sobra[0], sobra[1], sobra[2], dy - subir)

        propios = _leer_banda(siguiente, tope, cliente)
        # El pie de esa página tampoco se mueve: se queda donde está, igual que
        # el membrete. Sin esto se re-dibujaba más abajo y salía duplicado.
        if pie < siguiente.rect.height:
            propios = (
                [r for r in propios[0] if r['rect'].y1 <= pie],
                [i for i in propios[1] if i['rect'].y1 <= pie],
                [dict(tr, piezas=[p for p in tr['piezas']
                                  if (p[2].y if p[0] == 'l' else p[1].y1) <= pie])
                 for tr in propios[2]],
                propios[3])
            propios = (propios[0], propios[1],
                       [tr for tr in propios[2] if tr['piezas']], propios[3])
        empuje = max(0.0, alto_sobrante - arranque + 8.0)
        # Mismo cuidado que en la pagina de origen: borrar hasta el fondo real
        # de lo que se va a recolocar, o los ultimos renglones se quedan
        # tambien en su sitio viejo y aparecen dos veces.
        fondo_p = _abajo_de(propios[0], propios[1], propios[2], 0.0)
        hasta_p = max(limite_sig, fondo_p + 2.0)
        if pie < siguiente.rect.height:
            hasta_p = min(hasta_p, pie - 0.5)
        techo_p = max(tope, _arriba_de(propios[0], propios[1], propios[2], 0.0) - 0.5)
        _borrar_banda_entre(siguiente, techo_p, hasta_p)
        cabe_p, sobra_p = _reparte(propios[0], propios[1], propios[2],
                                   empuje, limite_sig)
        # Primero lo que llega de la página anterior, arriba del todo
        _pintar(siguiente, cliente, documento, sobra[0], sobra[1], sobra[2],
                dy - subir)
        # Y debajo, lo que ya tenía esta página
        _pintar(siguiente, cliente, documento, cabe_p[0], cabe_p[1], cabe_p[2], empuje)
        sobra = sobra_p
        dy = empuje

        if numero - numero_pagina > 400:      # cortafuegos, nunca debería pasar
            logger.warning('empuje en cascada: demasiadas páginas, se detiene')
            break

    avisos = []
    if numero > numero_pagina:
        avisos.append('el texto se corrió por %d página(s) más'
                      % (numero - numero_pagina))
    if paginas_creadas:
        avisos.append('se añadió %d página(s) al final' % paginas_creadas)
    if complejos:
        avisos.append('había dibujo vectorial complejo y se redibujó de forma simple')
    return '; '.join(avisos)
