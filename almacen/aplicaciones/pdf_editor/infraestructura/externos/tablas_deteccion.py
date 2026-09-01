# -*- coding: utf-8 -*-
"""
Reconocer las tablas de una página y leer lo que tienen.
========================================================

El reconocimiento es lo más caro de todo (cerca de un segundo), por eso vive
aquí junto a la memoria que lo recuerda.

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


from .tablas_base import (_CACHE_DETECTAR, _CACHE_DETECTAR_MAXIMO,
                          _CANDADO, _EN_CURSO, ESPERA_MAXIMA,
                          SEGURIDAD_ABAJO, _TablaConocida,
                          _bordes_de_columna, _bordes_de_fila,
                          _cliente)
from .tablas_geometria import _alineacion, _indice_en
from . import tablas_partir_renglon
from .tablas_rejilla import _hay_raya_en, _rayas_dibujadas
from . import guardado_pdf

logger = logging.getLogger(__name__)


# ── DETECTAR ─────────────────────────────────────────────────────────────
def _texto_legible(texto):
    """Espacios y guiones normales para editar.

    Al reescribir, el motor guarda los espacios como espacio duro (U+00A0) y el
    guion como guion blando (U+00AD): el documento se ve igual, pero si ese
    texto vuelve al cuadro de edición el usuario acaba guardando esos caracteres
    otra vez. Se normaliza al leer. (28-jul-2026.)
    """
    return (texto or '').replace('\u00a0', ' ').replace('\u00ad', '-')


MARCA_OCR = 'faro-ocr-texto'


def _viene_del_ocr(pagina):
    """¿Este documento lo fabricó la digitalización?

    Si es así, es texto reconstruido renglón a renglón y no tiene ni una raya: sus
    columnas son un espejismo y no hay que deducirle tablas (31-jul-2026).
    """
    try:
        return MARCA_OCR in (pagina.parent.metadata.get('keywords') or '')
    except Exception:
        return False


def _es_texto_corrido(pagina, tabla):
    """¿Esta «tabla» deducida del texto es en realidad un párrafo?

    Una tabla de verdad sin rayas tiene celdas cortas en columnas separadas.
    En un párrafo justificado, las alineaciones casuales de las palabras le
    hacían creer columnas a find_tables(strategy='text') y el editor trataba
    el texto como tabla — «no me agarra como texto, sino como tabla», vídeo
    del 20-ago-2026. La señal que los separa: en el párrafo, la mayoría de
    los renglones cruzan la «tabla» entera; en una tabla, casi ninguno.
    """
    try:
        recuadro = fitz.Rect(tabla.bbox)
        if recuadro.width <= 1:
            return False
        renglones = anchos = 0
        for bloque in pagina.get_text('dict')['blocks']:
            for linea in bloque.get('lines', []):
                caja = fitz.Rect(linea['bbox'])
                if not recuadro.intersects(caja) or caja.width <= 1:
                    continue
                renglones += 1
                if caja.width >= recuadro.width * 0.6:
                    anchos += 1
        return renglones > 0 and anchos >= renglones * 0.34
    except Exception:
        return False


def _tablas_de(pagina):
    """Las tablas de la página, con la estrategia que mejor funcione."""
    estrategias = ('lines',) if _viene_del_ocr(pagina) else ('lines', 'text')
    for estrategia in estrategias:
        try:
            encontradas = pagina.find_tables(strategy=estrategia)
        except Exception as excepcion:
            logger.warning('find_tables(%s): %s', estrategia, excepcion)
            continue
        utiles = [t for t in encontradas.tables if len(_bordes_de_columna(t)) >= 3]
        if estrategia == 'text':
            # Sin rayas dibujadas, la tabla es una deducción: se descartan los
            # espejismos sobre texto corrido antes de creérsela.
            utiles = [t for t in utiles if not _es_texto_corrido(pagina, t)]
        if utiles:
            return utiles, estrategia
    return [], None


def _hay_imagenes(pagina, recuadro):
    try:
        for imagen in pagina.get_image_info():
            if fitz.Rect(imagen['bbox']).intersects(recuadro):
                return True
    except Exception:
        pass
    return False


def _huella(contenido_pdf, numero_pagina):
    """Identifica «esta página de este documento», venga el PDF como venga."""
    return (guardado_pdf.huella_de(contenido_pdf), int(numero_pagina))


def _clave_comun(clave):
    """La misma huella, en el formato que usa la memoria compartida."""
    return '%s-%d' % (clave[0], clave[1])


def _recordar_aqui(clave, valor):
    """Lo guarda en la memoria de este proceso, que es la más rápida de mirar."""
    _CACHE_DETECTAR[clave] = copy.deepcopy(valor)
    _CACHE_DETECTAR.move_to_end(clave)
    while len(_CACHE_DETECTAR) > _CACHE_DETECTAR_MAXIMO:
        _CACHE_DETECTAR.popitem(last=False)


def detectar(contenido_pdf, numero_pagina):
    """Tablas de una página, tal como las necesita el editor para señalarlas.

    Coordenadas en puntos PDF con el origen ARRIBA, que es el sistema del
    visor: basta multiplicarlas por el zoom.
    """
    clave = _huella(contenido_pdf, numero_pagina)
    recordado = _CACHE_DETECTAR.get(clave)
    if recordado is not None:
        _CACHE_DETECTAR.move_to_end(clave)
        return copy.deepcopy(recordado)
    # La memoria de este proceso no lo tiene; puede tenerlo otro. La común vive
    # en memoria compartida y la ven todos los workers y todos los procesos del
    # grupo de trabajo, que es lo que hace que el adelanto sirva de algo.
    recordado = cache_tablas.obtener(_clave_comun(clave))
    if recordado is not None:
        _recordar_aqui(clave, recordado)
        return copy.deepcopy(recordado)

    with _CANDADO:
        en_marcha = _EN_CURSO.get(clave)
        if en_marcha is None:
            en_marcha = threading.Event()
            _EN_CURSO[clave] = en_marcha
            mio = True
        else:
            mio = False
    if not mio:
        en_marcha.wait(ESPERA_MAXIMA)
        recordado = _CACHE_DETECTAR.get(clave)
        if recordado is not None:
            return copy.deepcopy(recordado)
        # el otro no pudo: se calcula aquí

    documento = guardado_pdf.abrir_para_leer(contenido_pdf)
    try:
        indice = int(numero_pagina) - 1
        if indice < 0 or indice >= documento.page_count:
            return []
        pagina = documento[indice]
        tablas, estrategia = _tablas_de(pagina)

        salida = []
        for orden, tabla in enumerate(tablas):
            columnas = _bordes_de_columna(tabla)
            filas = _bordes_de_fila(tabla)
            salida.append({
                'indice': orden,
                'bbox': [round(v, 2) for v in tabla.bbox],
                'columnas': [round(v, 2) for v in columnas],
                'filas_y': [round(v, 2) for v in filas],
                'filas': len(filas) - 1,
                'total_columnas': len(columnas) - 1,
                'estrategia': estrategia,
                # Cuáles de esas rayas están DIBUJADAS en el documento y cuáles
                # se dedujeron del texto. El editor solo debe dejar arrastrar las
                # de verdad: al arrastrar una deducida se movía texto que no
                # tenía por qué moverse y los renglones acababan pisándose
                # (auditoría del 29-jul-2026).
                'filas_reales': [_hay_raya_en(v, _rayas_dibujadas(pagina)[0])
                                 for v in filas],
                'columnas_reales': [_hay_raya_en(v, _rayas_dibujadas(pagina)[1])
                                    for v in columnas],
                'encabezados': _encabezados(pagina, columnas, filas),
                'tiene_imagenes': _hay_imagenes(pagina, fitz.Rect(tabla.bbox)),
                'sitio_abajo': round(_sitio_libre_abajo(pagina, columnas, filas), 1),
                'ancho_pagina': round(pagina.rect.width, 2),
                'alto_pagina': round(pagina.rect.height, 2),
                'fondo_texto': _fondo_del_texto(pagina, columnas, filas),
                'celdas': _celdas_de(pagina, columnas, filas),
            })
        _recordar_aqui(clave, salida)
        cache_tablas.guardar(_clave_comun(clave), salida)
        return salida
    finally:
        guardado_pdf.cerrar(documento)
        with _CANDADO:
            aviso_fin = _EN_CURSO.pop(clave, None)
        if aviso_fin is not None:
            aviso_fin.set()


def _fondo_del_texto(pagina, columnas, filas):
    """Hasta qué altura llega el texto de cada fila.

    Es el suelo de cada fila: por encima de eso, encogerla dejaría el texto
    fuera de la celda. El editor lo usa para no prometer con la barrita un
    tamaño que luego el servidor tendría que recortar.
    """
    zona = fitz.Rect(columnas[0], filas[0], columnas[-1], filas[-1])
    fondos = [filas[i] for i in range(len(filas) - 1)]
    for renglon in _renglones_de_tabla(pagina, columnas, filas):
        centro = (renglon['rect'].y0 + renglon['rect'].y1) / 2
        indice = _indice_en(centro, filas)
        if indice is not None:
            fondos[indice] = max(fondos[indice], renglon['rect'].y1)
    return [round(v, 2) for v in fondos]


def _encabezados(pagina, columnas, filas):
    """El texto de la primera fila, columna por columna."""
    if len(filas) < 2:
        return []
    textos = []
    for i in range(len(columnas) - 1):
        recuadro = fitz.Rect(columnas[i], filas[0], columnas[i + 1], filas[1])
        piezas = [r['texto'] for r in _renglones_dentro(pagina, recuadro)]
        textos.append(_texto_legible(' '.join(piezas)).strip())
    return textos


def _interlineado_real(renglones, cuerpo):
    """La distancia entre líneas DE VERDAD, no entre la viñeta y su texto."""
    grupos = _agrupar_por_linea(renglones)
    if len(grupos) > 1:
        return grupos[1][0]['rect'].y0 - grupos[0][0]['rect'].y0
    return cuerpo * 1.15


def _agrupar_por_linea(renglones):
    """Renglones que van a la misma altura = UNA sola línea.

    En una lista con viñetas, el PDF guarda el «•» y su texto como dos piezas
    separadas (van tabuladas). Si se leen así, el cuadro de edición muestra la
    viñeta en un renglón y el texto en el siguiente: el doble de líneas, el
    contenido desbordado y la celda irreconocible —«se distorsiona totalmente»,
    el usuario, 28-jul-2026—. Y al guardar, esa separación se graba en el PDF.

    Aquí se juntan las piezas que se solapan en vertical, de izquierda a
    derecha, que es como se leen.
    """
    ordenados = sorted(renglones, key=lambda r: (round(r['rect'].y0, 1), r['rect'].x0))
    grupos = []
    for renglon in ordenados:
        if grupos:
            anterior = grupos[-1][-1]
            alto = min(renglon['rect'].height, anterior['rect'].height) or 1.0
            solape = (min(renglon['rect'].y1, anterior['rect'].y1)
                      - max(renglon['rect'].y0, anterior['rect'].y0))
            if solape > alto * 0.5:
                grupos[-1].append(renglon)
                continue
        grupos.append([renglon])
    return grupos


def _celdas_de(pagina, columnas, filas):
    """El contenido de cada celda: texto, cuerpo y alineación.

    Sirve para que el editor pueda poner el texto que ya hay cuando el usuario
    hace clic en la celda para escribir encima. Es una lectura ligera: no hace
    falta resolver fuentes, que es lo caro.
    """
    matriz = []
    zona = fitz.Rect(columnas[0], filas[0], columnas[-1], filas[-1])
    por_celda = {}
    for renglon in _renglones_de_tabla(pagina, columnas, filas):
        centro_x = (renglon['rect'].x0 + renglon['rect'].x1) / 2
        centro_y = (renglon['rect'].y0 + renglon['rect'].y1) / 2
        columna = _indice_en(centro_x, columnas)
        fila = _indice_en(centro_y, filas)
        if columna is None or fila is None:
            continue
        por_celda.setdefault((fila, columna), []).append(renglon)

    for fila in range(len(filas) - 1):
        de_la_fila = []
        for columna in range(len(columnas) - 1):
            renglones = sorted(por_celda.get((fila, columna), []),
                               key=lambda r: r['rect'].y0)
            if renglones:
                # Con SALTOS, no con espacios: una celda de varias líneas
                # (una lista con viñetas, por ejemplo) tiene que abrirse tal
                # como está, no aplastada en un renglón.
                # Cada línea de verdad, con su viñeta pegada al texto
                texto = _texto_legible('\n'.join(
                    ' '.join(p['texto'].strip() for p in grupo)
                    for grupo in _agrupar_por_linea(renglones)))
                cuerpo = max(r['spans'][0].get('size', 9.0) for r in renglones)
                alineacion = _alineacion(renglones[0]['rect'], columnas[columna],
                                         columnas[columna + 1])
                # Con qué letra está escrito y DÓNDE empieza: sin esto el editor
                # no puede escribir en el sitio exacto y el texto «salta» al
                # entrar en edición (reporte del usuario, 28-jul-2026).
                span = renglones[0]['spans'][0]
                banderas = span.get('flags', 0) or 0
                detalles = {
                    'color': '#%06x' % (span.get('color', 0) or 0),
                    'negrita': bool(banderas & 16),
                    'cursiva': bool(banderas & 2),
                    'mono': bool(banderas & 8),
                    'arriba': round(renglones[0]['rect'].y0, 2),
                    'izquierda': round(min(r['rect'].x0 for r in renglones), 2),
                    'interlineado': round(_interlineado_real(renglones, cuerpo), 2),
                }
            else:
                texto, cuerpo, alineacion = '', 0.0, 'centro'
                detalles = {'color': '#000000', 'negrita': False, 'cursiva': False,
                            'mono': False, 'arriba': 0.0, 'izquierda': 0.0,
                            'interlineado': 0.0}
            fila_celda = {'texto': texto, 'tam': round(cuerpo, 1),
                          'alineacion': alineacion}
            fila_celda.update(detalles)
            de_la_fila.append(fila_celda)
        matriz.append(de_la_fila)
    return matriz


def _sitio_libre_abajo(pagina, columnas, filas):
    """Cuánto puede crecer la tabla hacia abajo sin pisar nada.

    Se mira lo primero que aparece por debajo dentro del ancho de la tabla —
    texto, dibujo o imagen — y, si no hay nada, el margen inferior de la hoja.
    """
    limite = pagina.rect.height - 36.0     # margen de hoja razonable
    zona_x0, zona_x1 = columnas[0], columnas[-1]
    abajo = filas[-1]
    try:
        for bloque in pagina.get_text('dict')['blocks']:
            caja = fitz.Rect(bloque['bbox'])
            if caja.y0 >= abajo - 0.5 and caja.x1 > zona_x0 and caja.x0 < zona_x1:
                limite = min(limite, caja.y0)
        for dibujo in pagina.get_drawings():
            caja = fitz.Rect(dibujo['rect'])
            if caja.y0 >= abajo - 0.5 and caja.x1 > zona_x0 and caja.x0 < zona_x1:
                limite = min(limite, caja.y0)
        for imagen in pagina.get_image_info():
            caja = fitz.Rect(imagen['bbox'])
            if caja.y0 >= abajo - 0.5 and caja.x1 > zona_x0 and caja.x0 < zona_x1:
                limite = min(limite, caja.y0)
    except Exception:
        pass
    return max(0.0, limite - abajo - SEGURIDAD_ABAJO)


# ── LEER LA TABLA ────────────────────────────────────────────────────────
def _renglones_dentro(pagina, recuadro):
    """Renglones de texto cuyo CENTRO cae dentro del recuadro.

    Con `get_textbox` no vale: recoge lo que *toca* el recuadro, y en una tabla
    apretada eso mete el renglón de la fila siguiente dentro de la celda (se vio
    salir "SUBTOTAL IVA 15%" pegado en una sola celda). El centro es inequívoco.
    """
    encontrados = []
    try:
        bloques = pagina.get_text('dict')['blocks']
    except Exception:
        return encontrados
    for bloque in bloques:
        for linea in bloque.get('lines', []):
            spans = [s for s in linea['spans'] if s['text'].strip()]
            if not spans:
                continue
            caja = fitz.Rect(linea['bbox'])
            centro = fitz.Point((caja.x0 + caja.x1) / 2, (caja.y0 + caja.y1) / 2)
            if centro not in recuadro:
                continue
            encontrados.append({
                'texto': ''.join(s['text'] for s in spans).strip(),
                'rect': caja,
                'spans': spans,
                'base': max(s['origin'][1] for s in spans),
            })
    return encontrados


def _renglones_de_tabla(pagina, columnas, filas):
    """Los renglones de la tabla, ya repartidos por columna.

    Un renglón que cruza una raya («15% IVA   $ 187,35» escrito de un tirón)
    son dos celdas: `tablas_partir_renglon` lo parte antes de asignarle columna.
    """
    zona = fitz.Rect(columnas[0], filas[0], columnas[-1], filas[-1])
    return tablas_partir_renglon.partir_por_columnas(
        pagina, _renglones_dentro(pagina, zona), columnas)


def _leer_tabla(pagina, columnas, filas, cliente):
    """Todos los renglones, cada uno con su fila, su columna y su tipografía."""
    renglones = []
    zona = fitz.Rect(columnas[0], filas[0], columnas[-1], filas[-1])
    for renglon in _renglones_de_tabla(pagina, columnas, filas):
        centro_x = (renglon['rect'].x0 + renglon['rect'].x1) / 2
        centro_y = (renglon['rect'].y0 + renglon['rect'].y1) / 2
        columna = _indice_en(centro_x, columnas)
        fila = _indice_en(centro_y, filas)
        if columna is None or fila is None:
            continue
        renglon['columna'] = columna
        renglon['fila'] = fila
        renglon['alineacion'] = _alineacion(renglon['rect'],
                                            columnas[columna], columnas[columna + 1])
        renglon['estilo'] = cliente._estilo_de_span(
            renglon['spans'][0], renglon['rect'], 10.0, renglon['base'], False, pagina)
        renglones.append(renglon)
    return renglones


def _abrir(contenido_pdf, numero_pagina, indice_tabla):
    """Documento, página y tabla listos, o un error con sentido."""
    # Se abre en archivo para poder guardar por añadido (`guardado_pdf`): el
    # guardado deja de costar lo que pesa el documento entero.
    documento = guardado_pdf.abrir(contenido_pdf)
    indice = int(numero_pagina) - 1
    if indice < 0 or indice >= documento.page_count:
        documento.close()
        raise ValueError('Esa página no existe.')
    pagina = documento[indice]
    # ¿Ya se reconoció esta misma página de este mismo PDF? La clave es el
    # contenido entero, así que no puede quedarse obsoleta.
    clave_pagina = _huella(contenido_pdf, numero_pagina)
    recordado = _CACHE_DETECTAR.get(clave_pagina)
    if recordado is None:
        recordado = cache_tablas.obtener(_clave_comun(clave_pagina))
        if recordado is not None:
            _recordar_aqui(clave_pagina, recordado)
    if recordado is not None:
        if indice_tabla < 0 or indice_tabla >= len(recordado):
            documento.close()
            raise ValueError('Esa tabla ya no está en la página.')
        return documento, pagina, _TablaConocida(recordado[indice_tabla])

    tablas, _estrategia = _tablas_de(pagina)
    if not tablas:
        documento.close()
        raise ValueError('No se reconoció ninguna tabla en esta página.')
    if indice_tabla < 0 or indice_tabla >= len(tablas):
        documento.close()
        raise ValueError('Esa tabla ya no está en la página.')
    return documento, pagina, tablas[indice_tabla]
