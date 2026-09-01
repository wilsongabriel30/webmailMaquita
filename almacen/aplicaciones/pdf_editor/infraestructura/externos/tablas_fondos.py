# -*- coding: utf-8 -*-
"""
El COLOR DE FONDO de las celdas: leerlo antes de borrar y volver a pintarlo.
===========================================================================

Un PDF no tiene tablas: tiene rayas, texto y **rectángulos de color**. Cuando
el editor agrega una fila (o una columna, o mueve algo, o cambia un alto) no
puede «insertar» nada: borra la zona de la tabla y la vuelve a dibujar. El
borrado se lleva por delante esos rectángulos, y hasta ahora nadie los volvía
a pintar: la cabecera azul con letras blancas se quedaba **blanca sobre
blanco** —parecía que el encabezado había desaparecido— y el sombreado de las
filas se perdía.

Es justo lo que el usuario grabó el 05-08-2026: «en el momento que agrego una
fila, fíjate en el estilo, en los colores de estilo, se cambia totalmente;
quiero que me mantengas el estilo original sin cambiar colores».

Este módulo hace las dos mitades del trabajo:

  `leer(pagina, columnas, filas)`     ANTES de borrar: qué rellenos hay y a qué
                                      celdas están pegados
  `Fondos.pintar(...)`                DESPUÉS de borrar: los vuelve a pintar con
                                      la geometría nueva, debajo de la rejilla y
                                      del texto

Cada relleno se guarda **anclado a los bordes de la rejilla**, no a coordenadas
sueltas: así, si la fila cambia de sitio o de alto, el color la acompaña. Lo
que no cae sobre un borde se recuerda con su desfase, para no deformar los
rellenos que no siguen la cuadrícula.

Un relleno que abarque **varias filas** (un grupo resaltado, los subtotales de
una cotización) se vuelve a pintar **a trozos** si la reordenación ha separado
sus celdas: cada tramo de celdas seguidas lleva su color. Hasta el 17-08-2026
en ese caso se prefería no pintar nada, y el bloque desaparecía entero.

Autoría: Equipo de Tecnología Maquita — 2026-08-05
"""

import logging

import fitz

logger = logging.getLogger(__name__)

# Hasta dónde se considera que un lado del rectángulo «es» un borde de la tabla
TOLERANCIA_BORDE = 2.5
# Por debajo de esto un rectángulo de color no es un fondo: es una raya
MINIMO_LADO = 2.0
# Cuánto puede sobresalir un relleno de la tabla y seguir siendo suyo
HOLGURA_ZONA = 2.0


def _indice_de_borde(valor, bordes):
    """El borde más cercano a `valor`, y a qué distancia quedó."""
    mejor, distancia = 0, None
    for indice, borde in enumerate(bordes):
        separacion = abs(valor - borde)
        if distancia is None or separacion < distancia:
            mejor, distancia = indice, separacion
    return mejor, (valor - bordes[mejor])


def _rectangulos_con_color(pagina):
    """Los rectángulos rellenos de la página: (rect, color, opacidad)."""
    salida = []
    try:
        dibujos = pagina.get_drawings()
    except Exception:
        logger.debug('no se pudieron leer los dibujos de la página', exc_info=True)
        return salida
    for dibujo in dibujos:
        color = dibujo.get('fill')
        if not color or 'f' not in (dibujo.get('type') or ''):
            continue
        opacidad = dibujo.get('fill_opacity')
        if opacidad is None:
            opacidad = 1.0
        for trazo in dibujo.get('items') or []:
            if trazo[0] != 're':
                continue
            salida.append((fitz.Rect(trazo[1]), tuple(color), float(opacidad)))
    return salida


def leer(pagina, columnas, filas):
    """Los fondos de color de la tabla, anclados a los bordes de su rejilla.

    Se llama SIEMPRE antes de borrar: después de borrar ya no están.
    """
    zona = fitz.Rect(columnas[0], filas[0], columnas[-1], filas[-1])
    zona_holgada = fitz.Rect(zona.x0 - HOLGURA_ZONA, zona.y0 - HOLGURA_ZONA,
                             zona.x1 + HOLGURA_ZONA, zona.y1 + HOLGURA_ZONA)
    recogidos = []
    for rect, color, opacidad in _rectangulos_con_color(pagina):
        if rect.width < MINIMO_LADO or rect.height < MINIMO_LADO:
            continue                    # es una raya dibujada como rectángulo
        if not zona_holgada.contains(rect):
            continue                    # el fondo de la hoja u otra cosa de fuera
        col_ini, dx0 = _indice_de_borde(rect.x0, columnas)
        col_fin, dx1 = _indice_de_borde(rect.x1, columnas)
        fil_ini, dy0 = _indice_de_borde(rect.y0, filas)
        fil_fin, dy1 = _indice_de_borde(rect.y1, filas)
        if col_fin <= col_ini or fil_fin <= fil_ini:
            continue                    # no llega a cubrir ni una celda
        recogidos.append({
            'color': color, 'opacidad': opacidad,
            'col_ini': col_ini, 'col_fin': col_fin,
            'fil_ini': fil_ini, 'fil_fin': fil_fin,
            'dx0': dx0, 'dx1': dx1, 'dy0': dy0, 'dy1': dy1,
            'a_medida': (max(abs(dx0), abs(dx1), abs(dy0), abs(dy1))
                         > TOLERANCIA_BORDE),
        })
    return Fondos(recogidos, len(columnas), len(filas))


class Fondos(object):
    """Los rellenos leídos, listos para volver a pintarse."""

    def __init__(self, piezas, cuantas_columnas, cuantas_filas):
        self.piezas = piezas
        # Las que nacen con la operación (el fondo de una fila recién metida):
        # van aparte porque sus índices ya son los de la rejilla NUEVA y no hay
        # que trasladarlos.
        self.nuevas = []
        self.cuantas_columnas = cuantas_columnas
        self.cuantas_filas = cuantas_filas

    def __len__(self):
        return len(self.piezas) + len(self.nuevas)

    # ── heredar el fondo de una fila nueva ───────────────────────────────
    def _fondo_por_fila(self):
        """Color de las filas que están pintadas de lado a lado, una a una."""
        por_fila = {}
        for pieza in self.piezas:
            de_lado_a_lado = (pieza['col_ini'] == 0
                              and pieza['col_fin'] == self.cuantas_columnas - 1)
            una_sola = pieza['fil_fin'] == pieza['fil_ini'] + 1
            if de_lado_a_lado and una_sola and not pieza['a_medida']:
                por_fila[pieza['fil_ini']] = pieza
        return por_fila

    def heredar_fila(self, posicion):
        """El fondo que le toca a la fila recién insertada en `posicion`.

        «Solo agregues una fila replicada de la anterior pero vacía» (el
        usuario, 05-08-2026). Se copia el color de las filas de datos, nunca el
        del encabezado —una segunda cabecera azul no es lo que nadie espera—, y
        respetando el sombreado alterno cuando lo hay: la fila nueva se mira en
        la de su misma paridad.
        """
        datos = {f: p for f, p in self._fondo_por_fila().items() if f >= 1}
        if not datos or posicion < 1:
            return None

        # Sombreado alterno: la fila nueva se mira en las de su misma paridad, y
        # solo si el patrón se repite (dos filas o más); con una sola sería un
        # resaltado suelto de esa fila, no un patrón.
        misma_paridad = [p for f, p in datos.items() if f % 2 == posicion % 2]
        if len(misma_paridad) >= 2 and len({p['color'] for p in misma_paridad}) == 1:
            return dict(misma_paridad[0])

        # Si no hay patrón, se copia la fila de encima, que es lo que se pidió.
        anterior = datos.get(posicion - 1)
        return dict(anterior) if anterior else None

    def agregar_fila(self, posicion, plantilla):
        """Mete el fondo heredado en la fila `posicion` de la rejilla NUEVA."""
        if not plantilla:
            return
        pieza = dict(plantilla)
        pieza.update({'fil_ini': posicion, 'fil_fin': posicion + 1,
                      'dy0': 0.0, 'dy1': 0.0, 'a_medida': False})
        self.nuevas.append(pieza)

    # ── volver a pintar ──────────────────────────────────────────────────
    def pintar(self, pagina, columnas, filas, mapa_columnas=None, mapa_filas=None):
        """Vuelve a pintar los fondos sobre la geometría nueva.

        `mapa_columnas` y `mapa_filas` llevan de índice de borde viejo a nuevo
        (los devuelve `mapa_de_bordes`). Sin ellos se entiende que la rejilla
        tiene los mismos bordes, solo que en otro sitio.

        Se llama DESPUÉS de borrar y ANTES de trazar la rejilla y de escribir el
        texto, para que el color quede por debajo y no tape nada.
        """
        todas = ([(p, mapa_columnas, mapa_filas) for p in self.piezas]
                 + [(p, None, None) for p in self.nuevas])
        for pieza, mapa_c, mapa_f in todas:
            for rect in self._rects_de(pieza, columnas, filas, mapa_c, mapa_f):
                try:
                    pagina.draw_rect(rect, color=None, fill=pieza['color'], width=0,
                                     fill_opacity=pieza['opacidad'], overlay=True)
                except Exception:
                    logger.debug('no se pudo repintar un fondo de la tabla',
                                 exc_info=True)

    def _rects_de(self, pieza, columnas, filas, mapa_columnas, mapa_filas):
        """Dónde va esta pieza con la geometría nueva: uno o varios recuadros.

        Suele ser uno solo. Son varios cuando las celdas que llevaban el color
        han dejado de estar seguidas —se sacó del grupo una fila de en medio y
        se mandó a otro sitio—: entonces el color se pinta **a trozos**, uno por
        cada tramo, y así cada fila conserva el suyo. Hasta el 17-08-2026 en ese
        caso no se pintaba nada y el bloque de color desaparecía entero.
        """
        tramos_columna = self._tramos(pieza['col_ini'], pieza['col_fin'],
                                      mapa_columnas, len(columnas))
        tramos_fila = self._tramos(pieza['fil_ini'], pieza['fil_fin'],
                                   mapa_filas, len(filas))
        if not tramos_columna or not tramos_fila:
            return []                   # su fila o su columna ya no existe

        # El desfase solo se conserva si el relleno no seguía la cuadrícula:
        # si la seguía, se pega al borde nuevo aunque la fila haya cambiado de
        # alto, que es lo que hace que el color «acompañe» a la fila. Y solo se
        # aplica en los extremos: al primer tramo por un lado y al último por el
        # otro, que es donde estaban los bordes del relleno original.
        dx0 = pieza['dx0'] if pieza['a_medida'] else 0.0
        dx1 = pieza['dx1'] if pieza['a_medida'] else 0.0
        dy0 = pieza['dy0'] if pieza['a_medida'] else 0.0
        dy1 = pieza['dy1'] if pieza['a_medida'] else 0.0

        salida = []
        for indice_c, (col_ini, col_fin) in enumerate(tramos_columna):
            izquierda = dx0 if indice_c == 0 else 0.0
            derecha = dx1 if indice_c == len(tramos_columna) - 1 else 0.0
            for indice_f, (fil_ini, fil_fin) in enumerate(tramos_fila):
                arriba = dy0 if indice_f == 0 else 0.0
                abajo = dy1 if indice_f == len(tramos_fila) - 1 else 0.0
                rect = fitz.Rect(columnas[col_ini] + izquierda,
                                 filas[fil_ini] + arriba,
                                 columnas[col_fin] + derecha,
                                 filas[fil_fin] + abajo)
                if rect.width >= 0.5 and rect.height >= 0.5:
                    salida.append(rect)
        return salida

    @staticmethod
    def _tramos(borde_ini, borde_fin, mapa, cuantos_bordes):
        """Los tramos de bordes nuevos que encierran las mismas celdas de antes.

        Se traducen las CELDAS, no los bordes: así el color viaja con su fila
        aunque la fila cambie de sitio (mover una fila arriba o abajo).

        Devuelve una lista de `(borde_inicial, borde_final)`, normalmente con un
        solo tramo. Sale más de uno cuando la reordenación ha separado las
        celdas del relleno: cada grupo de celdas seguidas se pinta por su
        cuenta, en vez de renunciar a pintar —que es lo que se hacía hasta el
        17-08-2026 y hacía desaparecer el bloque de color entero—.

        Si entre medias aparece una celda RECIÉN NACIDA —la fila o la columna
        que se acaba de insertar— el fondo se estira para cubrirla: una cabecera
        de color pintada de lado a lado sigue llegando de lado a lado cuando se
        mete una columna en medio. Una celda AJENA, en cambio, corta el tramo:
        ahí empieza otro trozo y la fila de en medio se queda sin pintar, que es
        lo correcto.
        """
        if mapa is None:
            destinos = set(range(borde_ini, borde_fin))
            nacidas = set()
        else:
            destinos = set(mapa.get(celda) for celda in range(borde_ini, borde_fin))
            destinos.discard(None)
            # Las que no son destino de ninguna vieja: acaban de nacer.
            ocupadas = set(v for v in mapa.values() if v is not None)
            nacidas = set(range(cuantos_bordes - 1)) - ocupadas
        destinos = set(d for d in destinos if 0 <= d < cuantos_bordes - 1)
        if not destinos:
            return []

        tramos, inicio, ultimo = [], None, None
        for celda in range(min(destinos), max(destinos) + 1):
            suya = celda in destinos
            if suya or (inicio is not None and celda in nacidas):
                if inicio is None:
                    inicio = celda
                if suya:
                    ultimo = celda      # el tramo termina en una celda SUYA
            elif inicio is not None:
                tramos.append((inicio, ultimo + 1))
                inicio = ultimo = None
        if inicio is not None:
            tramos.append((inicio, ultimo + 1))
        return tramos


def mapa_de_celdas(accion, posicion, cuantas):
    """A qué fila (o columna) nueva va cada vieja tras insertar o eliminar.

    `None` = desaparece. Es el mismo criterio que `_mapa_de_columnas` de
    `tablas_geometria`, escrito aquí para las filas y para no cruzar módulos.
    """
    mapa = {}
    for vieja in range(cuantas):
        if accion == 'insertar':
            mapa[vieja] = vieja if vieja < posicion else vieja + 1
        elif vieja != posicion:
            mapa[vieja] = vieja if vieja < posicion else vieja - 1
    return mapa


def sin_fondos():
    """Un juego vacío, para cuando no se pudo leer nada."""
    return Fondos([], 0, 0)
