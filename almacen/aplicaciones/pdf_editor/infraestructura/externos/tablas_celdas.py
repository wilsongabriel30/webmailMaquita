# -*- coding: utf-8 -*-
"""
Escribir dentro de una celda.
=============================

Reúne el trabajo fino de meter texto en una celda respetando la letra de cada
renglón, y de hacer la fila más alta cuando no cabe.

Se separó de `tablas_pdf.py` el 29-jul-2026: aquel archivo había
llegado a 1.322 líneas y 48 funciones, y su tamaño ya costó un fallo
(una función duplicada que nadie vio). Cada módulo tiene ahora una
sola responsabilidad.

Autoría: Equipo de Tecnología Maquita
"""

import collections
import copy
import hashlib
import logging
import threading

import fitz

from . import cache_tablas
from . import guardado_pdf
from . import tablas_escritura as escritura
from . import tablas_fondos
from . import tablas_imagenes


from .tablas_base import (_bordes_de_columna, _bordes_de_fila,
                          _cliente)
from .tablas_geometria import _acumular
from .tablas_rejilla import (_borrar_zona, _estilo_de_las_rayas, _preparar,
                             _trazar_rejilla)
from .tablas_deteccion import (_abrir, _agrupar_por_linea,
                               _leer_tabla)
from . import guardado_pdf

logger = logging.getLogger(__name__)


def _modelo_de_letra(renglones):
    """De qué renglón se copia la letra para escribir en la celda.

    Del que lleva **más texto**, no del primero: en una lista con viñetas el
    primero es el «•», que suele venir en otra fuente y sin negrita, y copiando
    de ahí la celda entera se reescribía fina —«se me cambió el formato»,
    28-jul-2026—. Los símbolos sueltos (viñetas, guiones) se descartan.
    """
    if not renglones:
        return None
    def util(renglon):
        texto = (renglon.get('texto') or '').strip()
        return len(texto) >= 2 and any(c.isalnum() for c in texto)
    candidatos = [r for r in renglones if util(r)] or list(renglones)
    return max(candidatos, key=lambda r: len((r.get('texto') or '').strip()))


def _modelo_heredado(renglones):
    """La letra que se le presta a una celda que no tiene texto propio.

    Dentro de una celda se copia del renglón más largo (ver arriba), pero cuando
    hay que heredar de OTRAS celdas —la columna entera, o la tabla— el renglón
    más largo suele ser un título o una nota en negrita, y la celda salía en
    negrita aunque toda su columna fuera normal («me vuelve las letras negritas
    y el original es normal», 18-ago-2026). Aquí se coge **la letra del montón**:
    la que más veces se repite; y entre las de esa letra, la del renglón más
    largo, como siempre.
    """
    if not renglones:
        return None
    # Dos reglas, y en este orden:
    #
    #   1. **La letra fina va primero.** Lo corriente en una tabla es el texto
    #      normal; la negrita es de los títulos, los TOTAL y las notas. Una
    #      celda que no tiene texto propio se parece a sus vecinas de todos los
    #      días, no a la excepción. Sin esto, escribir en la celda vacía de la
    #      columna de precios copiaba del TOTAL (28-jul-2026) y una celda
    #      cualquiera copiaba de una nota en negrita (18-ago-2026).
    #   2. Entre las de la misma clase, la que MÁS TEXTO tenga, que es la que da
    #      el tono de la columna.
    #
    # Si toda la tabla va en negrita, no hay fina que elegir y se queda con la
    # negrita, que es lo que toca.
    peso = {}
    for renglon in renglones:
        estilo = renglon.get('estilo') or {}
        clave = (estilo.get('fuente'), bool(estilo.get('negrita')),
                 bool(estilo.get('cursiva')), round(float(estilo.get('size') or 0), 1))
        peso[clave] = peso.get(clave, 0) + len((renglon.get('texto') or '').strip())
    if not peso:
        return None
    mayoria = max(peso.items(), key=lambda par: (not par[0][1], par[1]))[0]

    def es_de_la_mayoria(renglon):
        estilo = renglon.get('estilo') or {}
        return (estilo.get('fuente'), bool(estilo.get('negrita')),
                bool(estilo.get('cursiva')),
                round(float(estilo.get('size') or 0), 1)) == mayoria

    return _modelo_de_letra([r for r in renglones if es_de_la_mayoria(r)])


def _recorte_del_texto(renglones, celda):
    """Solo lo que ocupa el texto de la celda: así no se tocan las rayas."""
    if not renglones:
        return None
    union = None
    for renglon in renglones:
        union = renglon['rect'] if union is None else union | renglon['rect']
    union = fitz.Rect(union)
    union.x0 = max(union.x0 - 1.0, celda.x0 + 0.6)
    union.x1 = min(union.x1 + 1.0, celda.x1 - 0.6)
    union.y0 = max(union.y0 - 0.8, celda.y0 + 0.6)
    union.y1 = min(union.y1 + 0.8, celda.y1 - 0.6)
    return union if union.width > 0 and union.height > 0 else None

def _estilos_por_linea(documento, pagina, cliente, renglones, ancho, estilo_base,
                       resolucion_base):
    """Con qué letra se escribe cada línea de la celda, en orden.

    Se toma de la línea original que ocupaba ese sitio (agrupando la viñeta con
    su texto), de modo que la celda se reescribe **como estaba**: el título en
    negrita sigue en negrita y los puntos de la lista, normales. Las
    resoluciones se reutilizan por estilo para no repetir el trabajo caro.
    """
    salida, memoria = [], {}
    for grupo in _agrupar_por_linea(renglones or []):
        modelo = _modelo_de_letra(grupo) or (grupo[0] if grupo else None)
        if modelo is None:
            continue
        estilo = dict(modelo.get('estilo') or estilo_base)
        # Los nombres son los de `_estilo_de_span`: fuente/negrita/cursiva. Con
        # los de otro sitio la clave salía siempre igual y todas las líneas
        # acababan compartiendo letra —la cursiva final se perdía—.
        clave = (estilo.get('fuente'), round(estilo.get('size', 0.0), 2),
                 estilo.get('negrita'), estilo.get('cursiva'), estilo.get('color'))
        if clave not in memoria:
            texto_modelo = (modelo.get('texto') or ' ')
            memoria[clave] = cliente._resolver_escritura(
                documento, pagina, estilo, texto_modelo, texto_modelo,
                ancho, ajustar_tam=False) or resolucion_base
        salida.append({'estilo': estilo, 'resolucion': memoria[clave]})
    return salida


def _agrandar_fila(documento, pagina, columnas, filas, indice_fila, falta, cliente):
    """Da `falta` puntos más de alto a una fila. Devuelve (filas_nuevas, aviso).

    Primero se hace sitio bajo la tabla —empujando lo de abajo, que ya sabe
    respetar encabezados y pies y pasar a otra página lo que no quepa— y después
    se redibuja la tabla con la fila crecida y las de abajo corridas.
    """
    from .empuje_pagina import empujar as empujar_banda

    aviso = ''
    try:
        aviso = empujar_banda(documento, int(pagina), filas[-1] + 0.5, falta) or ''
    except Exception as excepcion:
        logger.warning('no se pudo hacer sitio bajo la tabla: %s', excepcion)

    hoja = documento[int(pagina) - 1]
    renglones = _leer_tabla(hoja, columnas, filas, cliente)
    grosor, color_raya = _estilo_de_las_rayas(
        hoja, fitz.Rect(columnas[0], filas[0], columnas[-1], filas[-1]))

    altos = [filas[i + 1] - filas[i] for i in range(len(filas) - 1)]
    altos[indice_fila] += falta
    nuevas = _acumular(filas[0], altos)

    # Cada renglón se mueve con el borde al que estaba pegado: si se apoyaba
    # en la parte baja de su celda, baja con el fondo; si iba arriba, se queda
    # arriba. Mirando solo el borde de arriba, el texto de la fila que crece se
    # quedaba clavado mientras el fondo bajaba (TOTAL y 2.530 desalineados).
    def _desplazamiento(renglon):
        i = renglon['fila']
        if i is None or i >= len(altos):
            return 0.0
        alto_viejo = filas[i + 1] - filas[i]
        # ¿Dónde se apoyaba dentro de su fila? Cerca del fondo = anclado al fondo
        hueco_abajo = filas[i + 1] - renglon['rect'].y1
        anclado_al_fondo = alto_viejo > 0 and hueco_abajo <= alto_viejo * 0.35
        if anclado_al_fondo:
            return nuevas[i + 1] - filas[i + 1]
        return nuevas[i] - filas[i]

    desplazamientos = None      # se calcula renglón a renglón
    for renglon in renglones:
        renglon['destino'] = renglon['columna']
        renglon['dy'] = _desplazamiento(renglon)
    # El color de fondo, antes de borrar: al agrandar la fila la tabla se
    # redibuja entera y era «cuando la celda perdía su color de fondo».
    fondos = tablas_fondos.leer(hoja, columnas, filas)
    # Lo mismo con las imágenes: al agrandar la fila se redibuja la tabla
    # entera, y hasta el 17-08-2026 ahí se perdía el logotipo de la cabecera.
    imagenes = tablas_imagenes.leer(hoja, columnas, filas)
    _preparar(documento, hoja, cliente, renglones, None, columnas)

    abarca = fitz.Rect(columnas[0], min(filas[0], nuevas[0]),
                       columnas[-1], max(filas[-1], nuevas[-1]))
    anotacion = hoja.add_redact_annot(abarca)
    anotacion.update()
    _borrar_zona(hoja)

    fondos.pintar(hoja, columnas, nuevas)
    imagenes.pintar(hoja, columnas, nuevas)
    _trazar_rejilla(hoja, columnas, nuevas, grosor, color_raya, columnas, filas)

    for renglon in renglones:
        if renglon.get('resolucion'):
            escritura.escribir_renglon(hoja, cliente, renglon, columnas,
                                       renglon.get('dy', 0.0))

    aviso = ('la fila se agrandó para que cupiera el texto'
             + ('; ' + aviso if aviso else ''))
    return nuevas, aviso


# ── OPERACIÓN: TEXTO DE UNA CELDA ────────────────────────────────────────
def escribir_celda(contenido_pdf, numero_pagina, indice_tabla, fila, columna, texto):
    """Pone el texto en una celda (borrando lo que hubiera). Devuelve (pdf, aviso).

    Es lo que permite rellenar las filas y columnas recién agregadas, que nacen
    vacías. La letra se toma de la propia tabla: la de la celda si tenía algo, y
    si estaba vacía, la de su columna o la de la tabla.
    """
    cliente = _cliente()
    documento, pagina, tabla = _abrir(contenido_pdf, numero_pagina, indice_tabla)
    try:
        columnas = _bordes_de_columna(tabla)
        filas = _bordes_de_fila(tabla)
        if not (0 <= fila < len(filas) - 1) or not (0 <= columna < len(columnas) - 1):
            raise ValueError('Esa celda no existe en la tabla.')
        renglones = _leer_tabla(pagina, columnas, filas, cliente)

        # ¿Con qué letra? La de la celda; si está vacía, la de su columna; si no,
        # la de cualquier renglón de datos. Así el texto nuevo no desentona.
        modelo = _modelo_de_letra([r for r in renglones
                                   if r['fila'] == fila and r['columna'] == columna])
        if modelo is None:
            modelo = _modelo_heredado([r for r in renglones
                                       if r['columna'] == columna and r['fila'] > 0])
        if modelo is None:
            modelo = _modelo_heredado([r for r in renglones if r['fila'] > 0])
        if modelo is None:
            modelo = _modelo_heredado(renglones)
        if modelo is None:
            raise ValueError('Esta tabla no tiene texto del que copiar la letra.')

        estilo = dict(modelo['estilo'])
        alineacion = modelo['alineacion']
        # A que distancia del borde empezaba el texto que habia. Se respeta al
        # reescribir: sin esto, un renglon que estaba a 14 pt del borde volvia pegado
        # al borde y el cambio saltaba a la vista.
        sangria_original = None
        arriba, abajo = filas[fila], filas[fila + 1]
        propios = [r for r in renglones if r['fila'] == fila and r['columna'] == columna]
        if propios:
            sangria_original = min(r['rect'].x0 for r in propios) - columnas[columna]
        # La primera línea, ARRIBA: donde empezaba el texto que había. Antes se
        # tomaba la base del ÚLTIMO renglón y un texto de dos líneas aparecía
        # pegado al fondo de una celda alta (defecto del 27-jul-2026).
        if propios:
            base = min(r['base'] for r in propios)
        elif abajo - arriba > 24:
            # Celda alta y vacía (una fila recién agregada, o una celda que se
            # vació): el texto se apoya arriba, no flotando en medio.
            base = arriba + max(8.0, estilo.get('size', 9.0))
        else:
            base = abajo - max(2.5, (abajo - arriba) * 0.25)

        ancho_celda = columnas[columna + 1] - columnas[columna]
        resolucion = cliente._resolver_escritura(
            documento, pagina, estilo, texto or ' ', texto or ' ',
            ancho_celda, ajustar_tam=False)

        # El estilo de CADA línea que había: así un título en negrita seguido de
        # sus puntos normales se reescribe como estaba, y no todo con la misma
        # letra. Se resuelve antes de borrar, que es cuando la información existe.
        estilos_linea = _estilos_por_linea(documento, pagina, cliente, propios,
                                           ancho_celda, estilo, resolucion)

        # Fuera lo que hubiera en la celda (solo la celda, no la tabla entera)
        celda = fitz.Rect(columnas[columna], arriba, columnas[columna + 1], abajo)
        recorte = _recorte_del_texto(propios, celda)
        if recorte is not None:
            anotacion = pagina.add_redact_annot(recorte)
            anotacion.update()
            try:
                pagina.apply_redactions(images=fitz.PDF_REDACT_IMAGE_NONE,
                                                 graphics=fitz.PDF_REDACT_LINE_ART_NONE)
            except (TypeError, AttributeError):
                pagina.apply_redactions()

        apretado = False
        # Se prepara aquí, y no dentro del `if`, porque más abajo se lee siempre:
        # al VACIAR una celda (texto en blanco) no se entraba en el `if` y la
        # variable no llegaba a existir. (Auditoría del 29-jul-2026.)
        aviso_extra_alto = ''
        if (texto or '').strip():
            # Cada renglón que escribió el usuario se respeta como renglón; si
            # alguno no cabe de ancho, ese se reparte solo.
            renglones_texto = [l for l in (texto or '').split('\n')]
            # El alto de un renglón se mide con el CUERPO de la letra, no con un
            # mínimo fijo. Con el mínimo de 8 pt que había antes, una tabla apretada
            # —renglones de 7,5 pt y letra de 6— creía que no cabía ni una sola línea
            # y agrandaba la fila CADA VEZ que se escribía, aunque se escribiera
            # exactamente lo mismo que ya estaba. Y al agrandar se redibuja la tabla,
            # que es cuando la celda perdía su color de fondo. (Vídeo del usuario,
            # 30-jul-2026: «se me cambia el formato, se me distorsiona».)
            interlineado = max(estilo.get('size', 9.0) * 1.15, 5.0)

            # ¿Cabe de alto? Contando también los renglones que se partan por
            # ser más anchos que la celda. Si no cabe, la fila CRECE en vez de
            # apretar el texto (pedido del usuario, 27-jul-2026).
            ancho_util = max(1.0, columnas[columna + 1] - columnas[columna] - 4.0)
            total_lineas = 0
            for linea in renglones_texto:
                total_lineas += (len(escritura.partir(linea.strip(), resolucion, ancho_util))
                                 if linea.strip() else 1)
            necesario_total = interlineado * total_lineas + 1.0
            falta_alto = necesario_total - (abajo - arriba)
            # Cuántas líneas había ANTES en esta celda. Si el texto nuevo no ocupa más
            # líneas que el que había, cabe seguro —el de antes cabía— y la fila no se
            # toca. Es la regla que evita agrandar por redondeos de medio punto.
            lineas_antes = len({round(r['base'], 1) for r in propios}) if propios else 0
            if lineas_antes and total_lineas <= lineas_antes:
                falta_alto = 0.0
            if falta_alto > 1.0:
                filas, aviso_alto = _agrandar_fila(documento, numero_pagina, columnas,
                                                   filas, fila, falta_alto, cliente)
                arriba, abajo = filas[fila], filas[fila + 1]
                base = arriba + interlineado * 0.9
                propios = []          # la tabla se acaba de redibujar entera
                aviso_extra_alto = aviso_alto
            else:
                aviso_extra_alto = ''
            # Que quepa ENTERO: si el texto trae varias líneas y desde la base
            # de siempre no hay alto para todas, se empieza más arriba dentro de
            # la celda. Antes se escribía la primera y las demás se perdían
            # («solo se me guarda la primera fila»).
            necesario = interlineado * max(0, len(renglones_texto) - 1)
            if base + necesario > abajo - 1.0:
                base = max(arriba + interlineado * 0.9, abajo - 1.0 - necesario)
            altura = base
            for numero, renglon in enumerate(renglones_texto):
                if not renglon.strip():
                    altura += interlineado
                    continue
                # La letra de ESA línea, si la tenía; si el usuario añadió
                # líneas nuevas, heredan la de la última que había.
                propio = (estilos_linea[numero] if numero < len(estilos_linea)
                          else (estilos_linea[-1] if estilos_linea else None))
                res_linea = propio['resolucion'] if propio else resolucion
                est_linea = propio['estilo'] if propio else estilo
                if escritura.escribir(pagina, cliente, res_linea, est_linea,
                                      renglon.strip(), columnas[columna],
                                      columnas[columna + 1], altura, alineacion,
                                      alto_disponible=max(0.0, abajo - altura - 1.0),
                                      sangria=sangria_original):
                    apretado = True
                # Lo que ocupó de verdad: si se partió, el siguiente va más abajo
                ancho = max(1.0, columnas[columna + 1] - columnas[columna] - 4.0)
                trozos = escritura.partir(renglon.strip(), resolucion, ancho)
                altura += interlineado * max(1, len(trozos))
                if altura > abajo - 1.0 and numero < len(renglones_texto) - 1:
                    # No cabe más: se apretará el resto, pero NO se descarta
                    apretado = True
        aviso = 'el texto se ajustó para caber en la celda' if apretado else ''
        if aviso_extra_alto:
            aviso = (aviso_extra_alto + ('; ' + aviso if aviso else ''))
        return guardado_pdf.guardar(documento), aviso
    finally:
        guardado_pdf.cerrar(documento)
