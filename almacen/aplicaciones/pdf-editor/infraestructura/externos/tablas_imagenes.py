# -*- coding: utf-8 -*-
"""
Las IMÁGENES de la tabla: guardarlas antes de borrar y volver a ponerlas.
=========================================================================

Un PDF no tiene tablas: tiene rayas, texto, rectángulos de color e imágenes.
Cuando el editor agrega una fila (o una columna, o mueve algo, o cambia un
alto) no puede «insertar» nada: borra la zona de la tabla y la vuelve a
dibujar. El borrado se lleva por delante todo lo que había, y hasta ahora las
imágenes no se reponían: el logotipo de la cabecera, la firma escaneada o la
foto del producto **desaparecían**, y lo único que se hacía era avisar al
usuario de que se iban a perder.

Este módulo es el hermano de `tablas_fondos`, con el mismo reparto de trabajo:

  `leer(pagina, columnas, filas)`     ANTES de borrar: qué imágenes hay, a qué
                                      celda pertenece cada una y con qué
                                      respaldo se puede volver a dibujar
  `Imagenes.pintar(...)`              DESPUÉS de borrar: las vuelve a colocar
                                      con la geometría nueva, encima del color
                                      de fondo y debajo de las rayas y el texto

Cuatro decisiones que conviene conocer:

  · **La imagen no se estira.** Se ancla la esquina de arriba a la izquierda a
    su celda, conservando el tamaño que tenía: un logotipo no tiene por qué
    deformarse porque su fila haya cambiado de alto. Solo se reduce —y
    guardando la proporción— si la celda se quedó más pequeña que él.
  · **Se reponen también las que solo asoman por la tabla.** Una imagen que
    cruza el borde superior se quedaba antes cortada por la mitad; ahora vuelve
    entera a su sitio de siempre, porque no es de la tabla y no tiene por qué
    moverse con ella.
  · **La que va girada o en espejo vuelve como estaba.** El recuadro no dice
    cómo se apoya la imagen dentro de él, así que en esos casos se le reproduce
    su matriz (`_enderezar`, más abajo).
  · **También se conservan las que van metidas en el propio flujo** de la
    página, sin objeto propio del que sacar copia (`_incrustadas`).

Si la fila o la columna donde vivía la imagen se elimina, la imagen se va con
ella: es lo que el usuario espera al borrar esa fila.

Autoría: Equipo de Tecnología Maquita — 2026-08-17
"""

import logging

import fitz

logger = logging.getLogger(__name__)

# Cuánto puede sobresalir una imagen de la tabla y seguir contando como suya
HOLGURA_ZONA = 2.0
# Por debajo de esto no es una imagen que se vea: no merece reponerse
MINIMO_LADO = 1.0


def _celda_de(valor, bordes):
    """En qué hueco de la rejilla cae `valor` (0 … len(bordes) - 2)."""
    for indice in range(len(bordes) - 1):
        if bordes[indice] - 0.01 <= valor <= bordes[indice + 1] + 0.01:
            return indice
    return 0 if valor < bordes[0] else len(bordes) - 2


def _matriz_de(info):
    """Cómo se posa la imagen en la página, o None si no se pudo saber.

    Es la matriz que lleva el cuadrado unidad al sitio que ocupa la imagen: en
    ella está el giro y el espejo, que el recuadro por sí solo no cuenta.
    """
    try:
        matriz = fitz.Matrix(info['transform'])
    except Exception:
        return None
    # Una matriz degenerada (sin área) no sirve para nada
    if abs(matriz.a * matriz.d - matriz.b * matriz.c) < 1e-6:
        return None
    return matriz


def _es_recta(matriz):
    """¿La imagen está derecha, sin giro ni espejo?

    Es el caso corriente y el más barato: basta con volver a colocarla en su
    recuadro. Lo demás —una firma escaneada de lado, un sello torcido— necesita
    que se le reproduzca la matriz.
    """
    if matriz is None:
        return True                     # sin dato, se trata como derecha
    return (abs(matriz.b) < 1e-4 and abs(matriz.c) < 1e-4
            and matriz.a > 0 and matriz.d > 0)


def _respaldo_de(documento, xref):
    """Los bytes de la imagen, por si el objeto del PDF no sobrevive al borrado."""
    if not xref:
        return None
    try:
        return (documento.extract_image(xref) or {}).get('image')
    except Exception:
        logger.debug('no se pudo extraer la imagen xref=%s', xref, exc_info=True)
        return None


def _incrustadas(pagina):
    """Los píxeles de las imágenes metidas DENTRO del flujo de la página.

    La mayoría de las imágenes de un PDF son un objeto aparte al que la página
    apunta, y de ahí se sacan con `extract_image`. Unas pocas van escritas
    dentro del propio flujo de instrucciones (`BI … ID … EI`), sin objeto
    propio: algunos generadores lo hacen con las imágenes pequeñas —un logotipo
    diminuto, un icono, una firma de poco peso—. De esas no hay nada que
    extraer, y hasta el 17-08-2026 se avisaba de que se perdían.

    Sí se pueden pedir por otro lado: la lectura de la página las entrega ya
    convertidas a PNG, con su recuadro. Devuelve `[(recuadro, bytes), …]`.

    Se llama SOLO si hace falta —renderiza la página y no es barato—, y solo
    cuando una tabla tiene alguna de estas, que es poco común.
    """
    salida = []
    try:
        bloques = pagina.get_text('dict').get('blocks') or []
    except Exception:
        logger.debug('no se pudieron leer las imágenes del flujo', exc_info=True)
        return salida
    for bloque in bloques:
        if bloque.get('type') == 1 and bloque.get('image'):
            salida.append((fitz.Rect(bloque['bbox']), bloque['image']))
    return salida


def _respaldo_del_flujo(incrustadas, rect):
    """Los bytes de la imagen del flujo que ocupa ese recuadro (o None)."""
    for caja, datos in incrustadas:
        if (abs(caja.x0 - rect.x0) <= 1.0 and abs(caja.y0 - rect.y0) <= 1.0
                and abs(caja.x1 - rect.x1) <= 1.0 and abs(caja.y1 - rect.y1) <= 1.0):
            return datos
    return None


def leer(pagina, columnas, filas):
    """Las imágenes de la tabla, ancladas a la celda en la que están.

    Se llama SIEMPRE antes de borrar: después de borrar ya no están.
    """
    zona = fitz.Rect(columnas[0] - HOLGURA_ZONA, filas[0] - HOLGURA_ZONA,
                     columnas[-1] + HOLGURA_ZONA, filas[-1] + HOLGURA_ZONA)
    documento = pagina.parent
    recogidas = []
    try:
        encontradas = pagina.get_image_info(xrefs=True)
    except Exception:
        logger.debug('no se pudieron leer las imágenes de la página', exc_info=True)
        return Imagenes([])

    for info in encontradas:
        rect = fitz.Rect(info.get('bbox') or (0, 0, 0, 0))
        if rect.width < MINIMO_LADO or rect.height < MINIMO_LADO:
            continue
        if not rect.intersects(zona):
            continue                    # no tiene nada que ver con esta tabla
        xref = int(info.get('xref') or 0)
        matriz = _matriz_de(info)
        pieza = {
            'xref': xref,
            'respaldo': _respaldo_de(documento, xref),
            'rect': rect,
            'ancho': rect.width,
            'alto': rect.height,
            # Cómo estaba colocada: si va girada o en espejo hay que reproducir
            # su matriz, porque el recuadro solo no dice cómo se posa dentro.
            'matriz': matriz,
            'recta': _es_recta(matriz),
            # Solo viajan con la rejilla las que están DENTRO de la tabla; las
            # que apenas asoman vuelven a su sitio de siempre.
            'de_la_tabla': zona.contains(rect),
            'columna': _celda_de((rect.x0 + rect.x1) / 2, columnas),
            'fila': _celda_de((rect.y0 + rect.y1) / 2, filas),
        }
        pieza['dx'] = rect.x0 - columnas[pieza['columna']]
        pieza['dy'] = rect.y0 - filas[pieza['fila']]
        recogidas.append(pieza)

    # Las que no tienen objeto propio van metidas en el flujo de la página: sus
    # píxeles se piden aparte, y solo si de verdad hay alguna así.
    faltan = [p for p in recogidas if not p['xref'] and not p['respaldo']]
    if faltan:
        incrustadas = _incrustadas(pagina)
        for pieza in faltan:
            pieza['respaldo'] = _respaldo_del_flujo(incrustadas, pieza['rect'])
            if not pieza['respaldo']:
                logger.info('imagen del flujo que no se pudo recuperar: %s',
                            pieza['rect'])
                pieza['irrecuperable'] = True
    return Imagenes(recogidas)


class Imagenes(object):
    """Las imágenes leídas, listas para volver a colocarse."""

    def __init__(self, piezas):
        self.piezas = piezas
        # Las que se intentó reponer y no se pudo. Es lo que se le avisa al
        # usuario: las que desaparecen porque se borró SU fila no cuentan.
        self.perdidas = 0

    def __len__(self):
        return len(self.piezas)

    def pintar(self, pagina, columnas, filas, mapa_columnas=None, mapa_filas=None):
        """Vuelve a colocar las imágenes sobre la geometría nueva.

        `mapa_columnas` y `mapa_filas` llevan de celda vieja a celda nueva (los
        mismos que usa `tablas_fondos`). Sin ellos se entiende que la rejilla
        tiene las mismas celdas, solo que en otro sitio.

        Se llama DESPUÉS de borrar, después del color de fondo y ANTES de las
        rayas y del texto: así el color queda debajo y las rayas y las letras,
        encima, que es como estaba el documento.
        """
        self.perdidas = 0
        for pieza in self.piezas:
            destino = self._destino_de(pieza, columnas, filas,
                                       mapa_columnas, mapa_filas)
            if destino is None:
                continue                # su celda ya no existe: se va con ella
            if pieza.get('irrecuperable'):
                self.perdidas += 1
                continue
            if not self._colocar(pagina, destino, pieza):
                self.perdidas += 1

    def _colocar(self, pagina, destino, pieza):
        """Dibuja una imagen. Primero el objeto del PDF; si no, su respaldo."""
        rect, movimiento = destino
        # Por `xref` se reutiliza el objeto tal cual está en el documento, con su
        # transparencia y su máscara. El respaldo en bytes es la red de
        # seguridad para cuando ese objeto no sobrevivió al borrado.
        for intento in ('xref', 'respaldo'):
            if intento == 'xref' and not pieza.get('xref'):
                continue
            if intento == 'respaldo' and not pieza.get('respaldo'):
                continue
            try:
                marca = set(pagina.get_contents())
                if intento == 'xref':
                    pagina.insert_image(rect, xref=pieza['xref'],
                                        keep_proportion=False, overlay=True)
                else:
                    pagina.insert_image(rect, stream=pieza['respaldo'],
                                        keep_proportion=False, overlay=True)
                if not pieza.get('recta', True):
                    _enderezar(pagina, marca, pieza['matriz'] * movimiento)
                return True
            except Exception:
                logger.debug('no se pudo reponer una imagen de la tabla (%s)',
                             intento, exc_info=True)
        return False

    def _destino_de(self, pieza, columnas, filas, mapa_columnas, mapa_filas):
        """Dónde va esta imagen con la geometría nueva (o None si ya no cabe).

        Devuelve `(recuadro, movimiento)`. El recuadro es dónde se posa si está
        derecha; el `movimiento` es lo que se le ha hecho —correrla y, si acaso,
        reducirla—, y sirve para recolocar las que van giradas o en espejo, que
        no se pueden describir con un recuadro.
        """
        if not pieza['de_la_tabla']:
            # No es de la tabla: vuelve a su sitio de siempre, sin tocarla.
            return fitz.Rect(pieza['rect']), fitz.Matrix(1, 0, 0, 1, 0, 0)

        columna = self._celda_destino(pieza['columna'], mapa_columnas,
                                      len(columnas) - 1)
        fila = self._celda_destino(pieza['fila'], mapa_filas, len(filas) - 1)
        if columna is None or fila is None:
            return None                 # se eliminó su fila o su columna

        # La esquina de arriba a la izquierda, a la misma distancia del borde de
        # su celda; el tamaño, el de siempre.
        x0 = columnas[columna] + pieza['dx']
        y0 = filas[fila] + pieza['dy']
        ancho, alto = pieza['ancho'], pieza['alto']

        # Si la celda se quedó más pequeña, la imagen se reduce guardando la
        # proporción, antes que salirse de la celda y pisar lo de al lado.
        hueco_ancho = max(1.0, columnas[columna + 1] - x0)
        hueco_alto = max(1.0, filas[fila + 1] - y0)
        escala = min(1.0, hueco_ancho / ancho, hueco_alto / alto)
        if escala < 1.0:
            ancho, alto = ancho * escala, alto * escala

        rect = fitz.Rect(x0, y0, x0 + ancho, y0 + alto)
        if rect.width < MINIMO_LADO or rect.height < MINIMO_LADO:
            return None

        # Lo mismo, contado como movimiento: primero se corre a su sitio nuevo y
        # después, si hizo falta, se reduce desde esa esquina.
        movimiento = fitz.Matrix(1, 0, 0, 1, x0 - pieza['rect'].x0,
                                 y0 - pieza['rect'].y0)
        if escala < 1.0:
            movimiento = (movimiento
                          * fitz.Matrix(1, 0, 0, 1, -x0, -y0)
                          * fitz.Matrix(escala, escala)
                          * fitz.Matrix(1, 0, 0, 1, x0, y0))
        return rect, movimiento

    @staticmethod
    def _celda_destino(celda, mapa, cuantas_celdas):
        """La celda nueva que le corresponde a `celda` (o None si desapareció)."""
        destino = celda if mapa is None else mapa.get(celda)
        if destino is None or not (0 <= destino < cuantas_celdas):
            return None
        return destino


# ── devolverle el giro a una imagen recién colocada ──────────────────────
# `insert_image` solo sabe posar la imagen derecha dentro de un recuadro: no
# tiene forma de pedirle un giro que no sea de 90 en 90, ni un espejo. Pero deja
# el trabajo hecho —el objeto en los recursos de la página y un trocito de
# instrucciones aparte, de la forma `q  a b c d e f cm  /Nombre Do  Q`—, y en ese
# trocito la colocación es UNA sola instrucción. Así que se coloca la imagen y
# acto seguido se le corrige esa instrucción con la que tenía de verdad.
#
# La conversión entre las dos formas de medir —la de la página, con la Y hacia
# abajo, y la del PDF, con la Y hacia arriba y la imagen apoyada en su esquina de
# abajo— es la de `_a_instruccion`, comprobada contra lo que escribe el propio
# PyMuPDF.
_VOLTEAR_UNIDAD = fitz.Matrix(1, 0, 0, -1, 0, 1)


def _a_instruccion(pagina, matriz):
    """La matriz de la página, escrita como la espera el PDF."""
    return _VOLTEAR_UNIDAD * matriz * ~pagina.transformation_matrix


def _enderezar(pagina, contenidos_antes, matriz):
    """Le devuelve su giro a la imagen que se acaba de colocar.

    `contenidos_antes` son los trozos de instrucciones que tenía la página justo
    antes de colocarla: el que aparece de nuevo es el suyo. Si no aparece uno y
    solo uno, o no tiene la forma esperada, se deja como está —derecha— antes
    que tocar instrucciones que no se sabe de quién son.
    """
    nuevos = [x for x in pagina.get_contents() if x not in contenidos_antes]
    if len(nuevos) != 1:
        logger.debug('no se pudo identificar el trozo de la imagen: se queda derecha')
        return False
    documento = pagina.parent
    try:
        instrucciones = documento.xref_stream(nuevos[0]).decode('latin-1')
    except Exception:
        logger.debug('no se pudo leer el trozo de la imagen', exc_info=True)
        return False
    if instrucciones.count(' cm') != 1 or instrucciones.count(' Do') != 1:
        logger.debug('el trozo de la imagen no tiene la forma esperada: %r',
                     instrucciones[:80])
        return False

    destino = _a_instruccion(pagina, matriz)
    antes, _resto = instrucciones.split(' cm', 1)
    cabecera = antes.rsplit('\n', 1)[0] if '\n' in antes else ''
    nueva = '%s\n%g %g %g %g %g %g cm%s' % (
        cabecera, destino.a, destino.b, destino.c, destino.d, destino.e,
        destino.f, instrucciones.split(' cm', 1)[1])
    try:
        documento.update_stream(nuevos[0], nueva.encode('latin-1'))
        return True
    except Exception:
        logger.debug('no se pudo devolverle el giro a la imagen', exc_info=True)
        return False


def sin_imagenes():
    """Un juego vacío, para cuando no se pudo leer nada."""
    return Imagenes([])
