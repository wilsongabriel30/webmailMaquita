# -*- coding: utf-8 -*-
"""
Ancho de las COLUMNAS y alto de las FILAS, arrastrando la raya.
===============================================================
«necesito que me pongas unas barritas deslizantes como esta de aquí para esta
parte de las columnas y las filas, yo poder ponerle al tamaño que yo quiero»
— el usuario, 28-jul-2026.

Hasta ahora la tabla solo se podía cambiar por operaciones enteras (agregar o
quitar una columna, una fila, moverlas). Esto es lo otro que se hace en Word a
diario: **coger la raya y llevarla donde uno quiere**.

Cómo funciona, y por qué así: un PDF no tiene tablas, así que aquí tampoco se
"redimensiona" nada. Se lee la tabla entera con su tipografía, se calcula dónde
queda la raya movida, se borra la zona y se vuelve a dibujar — el mismo motor
que ya usan las demás operaciones (`tablas_pdf`), para que el resultado se
parezca al original y no a una tabla rehecha.

Qué raya se puede mover:

  * las **interiores**: la columna (o fila) de un lado crece justo lo que la
    del otro lado se encoge, así la tabla no cambia de tamaño ni se sale de
    los márgenes;
  * la **última**: alarga o acorta la tabla, y solo hasta donde haya sitio
    libre de verdad (el hueco que hay hasta lo que viene debajo, o el margen
    derecho de la hoja). Nunca se pisa el contenido que ya está.

La primera raya (el borde izquierdo o el de arriba) no se mueve: es el que
ancla la tabla a su sitio en la página.

Autoría: Equipo de Tecnología Maquita — 2026-07-28
"""

import logging

import fitz

from . import guardado_pdf
from . import tablas_fondos
from . import tablas_imagenes
from . import tablas_pdf

logger = logging.getLogger(__name__)

# Nada por debajo de esto sirve para escribir dentro
MINIMO_COLUMNA = 12.0
MINIMO_FILA = 9.0
# Aire que se le deja al margen derecho de la hoja al alargar la tabla
MARGEN_DERECHO = 20.0
# Aire que se respeta contra lo que hay debajo de la tabla
AIRE_ABAJO = 2.0
# Aire que se le deja al texto dentro de su celda
AIRE_TEXTO = 2.5


def _mover_borde(bordes, indice, delta, minimo, tope, minimo_siguiente=None):
    """Los bordes nuevos tras llevar el borde `indice` a `+delta`.

    Solo se mueve ESE borde: los demás se quedan donde están, de modo que el
    cambio afecta a la medida de un lado y del otro y a nada más. El valor se
    recorta para que ninguna de las dos piezas quede por debajo de su mínimo —y
    cada lado tiene el suyo, porque lo que ocupa el texto de arriba no dice nada
    de lo que ocupa el de abajo.
    """
    if indice <= 0 or indice >= len(bordes):
        raise ValueError('Esa raya no se puede mover.')
    minimo_permitido = bordes[indice - 1] + minimo
    if indice == len(bordes) - 1:
        maximo_permitido = tope
    else:
        maximo_permitido = bordes[indice + 1] - (minimo if minimo_siguiente is None
                                                 else minimo_siguiente)
    if maximo_permitido < minimo_permitido:
        # Las dos celdas están al límite de su contenido: no hay margen que
        # repartir. Se deja la raya donde estaba —y se dice por qué— en vez de
        # soltarle un error al usuario, que no puede hacer nada con él.
        return list(bordes), ('esa raya está entre dos celdas llenas: '
                              'no se puede mover sin tapar texto')

    nuevo = min(max(bordes[indice] + delta, minimo_permitido), maximo_permitido)
    salida = list(bordes)
    salida[indice] = nuevo
    aviso = ''
    if abs(nuevo - (bordes[indice] + delta)) > 1.0:
        aviso = 'se movió hasta donde cabía sin tapar el texto'
    return salida, aviso


def _tope_columnas(pagina, columnas):
    """Hasta dónde puede llegar el borde derecho de la tabla."""
    return max(columnas[-2] + MINIMO_COLUMNA, pagina.rect.width - MARGEN_DERECHO)


def _tope_filas(pagina, columnas, filas):
    """Hasta dónde puede bajar el borde inferior sin pisar lo que hay debajo."""
    sitio = tablas_pdf._sitio_libre_abajo(pagina, columnas, filas)
    return max(filas[-2] + MINIMO_FILA, filas[-1] + max(0.0, sitio - AIRE_ABAJO))


def _anclado_al_fondo(renglon, filas):
    """¿Este renglón va pegado al borde de ABAJO de su fila?

    Vive aquí, y no repetido en cada sitio, porque medir el mínimo de una fila y
    mover su texto tienen que usar exactamente el mismo criterio: si
    discrepasen, la fila diría que no puede encoger por un texto que en realidad
    iba a subir con ella.
    """
    i = renglon.get('fila')
    if i is None or i + 1 >= len(filas):
        return False
    alto = filas[i + 1] - filas[i]
    return alto > 0 and (filas[i + 1] - renglon['rect'].y1) <= alto * 0.35


def _alto_ocupado(renglones, indice_fila, arriba):
    """Lo que baja el contenido de una fila desde su borde de arriba.

    Es el suelo por debajo del cual una fila NO se puede encoger: si se pasara,
    el texto se saldría por debajo y se montaría sobre las filas de abajo, que
    es justo lo que reportó el usuario (28-jul-2026, foto de la proforma).
    """
    fondos = [r['rect'].y1 for r in renglones if r.get('fila') == indice_fila]
    if not fondos:
        return 0.0
    return max(0.0, max(fondos) - arriba)


def _minimo_de_fila(renglones, indice_fila, filas, minimo_base):
    """El alto mínimo de una fila: el mayor entre el legible y lo que ocupa el texto.

    Lo que ocupa NO es «desde el borde de arriba hasta el fondo del texto»
    cuando el texto va pegado al borde de abajo: ese texto SUBE con el borde al
    encoger la fila —lo hace `_desplazamiento_de`—, así que el hueco vacío que
    tiene encima no es alto obligatorio, sino sitio libre.

    Contarlo hacía imposible deshacer un agrandamiento: al crecer 190 pt, el
    texto se quedaba pegado al fondo y ese mismo hueco pasaba a ser el mínimo de
    la fila, así que el arrastre de vuelta no encogía ni un punto. («el momento
    que le reduzco el texto que viene debajo también debería subirse», vídeo del
    usuario, 19-ago-2026.)
    """
    propios = [r for r in renglones if r.get('fila') == indice_fila]
    if not propios:
        return minimo_base
    if all(_anclado_al_fondo(r, filas) for r in propios):
        # Solo hace falta el alto del propio texto: puede subir con el borde.
        ocupado = (max(r['rect'].y1 for r in propios)
                   - min(r['rect'].y0 for r in propios))
    else:
        ocupado = _alto_ocupado(renglones, indice_fila, filas[indice_fila])
    return max(minimo_base, ocupado + AIRE_TEXTO)


def _desplazamiento_de(renglon, filas, nuevas):
    """Cuánto baja (o sube) un renglón, sin salirse NUNCA de su celda.

    Se mueve con el borde al que estaba pegado —arriba o abajo, como ya hace
    `_agrandar_fila`— y después se recorta para que quede dentro de su celda
    nueva. Sin ese recorte, encoger una fila dejaba el texto por fuera.
    """
    i = renglon.get('fila')
    if i is None or i + 1 >= len(filas):
        return 0.0
    dy = ((nuevas[i + 1] - filas[i + 1]) if _anclado_al_fondo(renglon, filas)
          else (nuevas[i] - filas[i]))

    # Que no se salga: primero por abajo, luego por arriba (manda el techo, para
    # que una celda demasiado baja no empuje el texto fuera por el otro lado).
    if renglon['rect'].y1 + dy > nuevas[i + 1] - 1.0:
        dy = nuevas[i + 1] - 1.0 - renglon['rect'].y1
    if renglon['rect'].y0 + dy < nuevas[i] + 0.5:
        dy = nuevas[i] + 0.5 - renglon['rect'].y0
    return dy


def redimensionar(contenido_pdf, numero_pagina, indice_tabla, que, borde, delta):
    """Mueve una raya de la tabla. Devuelve (pdf, aviso).

    `que`   'columna' (raya vertical) o 'fila' (raya horizontal)
    `borde` índice de la raya: 1 .. n (la 0 no se mueve)
    `delta` cuánto se movió, en puntos PDF (positivo = derecha / abajo)
    """
    if que not in ('columna', 'fila'):
        raise ValueError('Solo se pueden mover rayas de columna o de fila.')
    if abs(delta) < 0.2:
        raise ValueError('El movimiento fue demasiado pequeño.')

    aviso_extra = ''
    recogida = None      # (y_desde, dy) si al final hay que subir lo de abajo

    cliente = tablas_pdf._cliente()
    documento, pagina, tabla = tablas_pdf._abrir(contenido_pdf, numero_pagina,
                                                 indice_tabla)
    try:
        columnas = tablas_pdf._bordes_de_columna(tabla)
        filas = tablas_pdf._bordes_de_fila(tabla)

        # Solo se arrastran las rayas que el documento tiene DIBUJADAS. Cuando
        # una tabla no separa sus filas con rayas, el reconocimiento las deduce
        # del texto y da una "fila" por renglón; si se dejara arrastrar una de
        # esas, se movería texto que no tenía por qué moverse y los renglones
        # acabarían pisándose unos a otros. (Auditoría del 29-jul-2026.)
        bordes = filas if que == 'fila' else columnas
        if not (0 <= borde < len(bordes)):
            raise ValueError('Esa raya no existe en la tabla.')
        # Las rayas HORIZONTALES deducidas no se pueden arrastrar: cuando una
        # tabla no separa sus filas con rayas, el reconocimiento las deduce del
        # texto y da una "fila" por renglón; moverla descolocaba los renglones,
        # que acababan pisándose (auditoría del 29-jul-2026).
        # Con las VERTICALES no pasa: cambiar el ancho reparte el texto por
        # columnas, que es una operación con sentido aunque no haya bordes
        # dibujados, y así se conserva para las tablas que solo alinean texto.
        if que == 'fila':
            horizontales, _verticales = tablas_pdf._rayas_dibujadas(pagina)
            if not tablas_pdf._hay_raya_en(bordes[borde], horizontales):
                raise ValueError('Esa raya no está dibujada en el documento: es '
                                 'una separación que se dedujo del texto, y '
                                 'moverla descolocaría los renglones.')
        recuadro = fitz.Rect(columnas[0], filas[0], columnas[-1], filas[-1])
        renglones = tablas_pdf._leer_tabla(pagina, columnas, filas, cliente)
        grosor, color_raya = tablas_pdf._estilo_de_las_rayas(pagina, recuadro)

        if que == 'columna':
            interior = borde < len(columnas) - 1
            deseado = columnas[borde] + delta
            tope_sin_crecer = (columnas[borde + 1] - MINIMO_COLUMNA) if interior else None
            if interior and deseado > tope_sin_crecer + 0.5:
                # La columna de al lado ya está en su mínimo: en vez de frenar,
                # la tabla se ENSANCHA hacia la derecha mientras quede papel.
                nuevas_columnas, aviso_extra = _ensanchar_tabla(
                    pagina, columnas, borde, deseado)
            else:
                nuevas_columnas, aviso_extra = _mover_borde(
                    columnas, borde, delta, MINIMO_COLUMNA,
                    _tope_columnas(pagina, columnas))
            nuevas_filas = filas
            desplazamientos = None
        else:
            # Ninguna de las dos filas puede encogerse por debajo de lo que ocupa
            # su texto: si se permitiera, el contenido se saldría de la celda y
            # pisaría lo que viene después (foto del usuario, 28-jul-2026).
            minimo_arriba = _minimo_de_fila(renglones, borde - 1, filas, MINIMO_FILA)
            minimo_abajo = (_minimo_de_fila(renglones, borde, filas, MINIMO_FILA)
                            if borde < len(filas) - 1 else MINIMO_FILA)
            interior = borde < len(filas) - 1
            deseado = filas[borde] + delta
            tope_sin_crecer = (filas[borde + 1] - minimo_abajo) if interior else None

            # Si no hay adónde crecer —la fila de abajo está llena, o es la
            # ÚLTIMA raya y el texto empieza justo debajo— la tabla se ALARGA
            # haciendo sitio, en vez de frenar el arrastre. Sin lo segundo no se
            # podía «agrandar las casillas para abajo» (usuario, 28-jul-2026).
            tope_hoja = _tope_filas(pagina, columnas, filas)
            if ((interior and deseado > tope_sin_crecer + 0.5)
                    or (not interior and deseado > tope_hoja + 0.5)):
                nuevas_filas, aviso_extra = _alargar_tabla(
                    documento, numero_pagina, columnas, filas, borde,
                    max(deseado, filas[borde - 1] + minimo_arriba), cliente)
                pagina = documento[int(numero_pagina) - 1]
                renglones = tablas_pdf._leer_tabla(pagina, columnas, filas, cliente)
            elif not interior and deseado < filas[borde] - 0.5:
                # El camino de vuelta: al encoger la tabla por su raya de abajo,
                # lo que hay debajo SUBE —y si se habia ido a otra hoja, vuelve—.
                # Sin esto el editor era asimetrico: bajaba pero no subia.
                # («el momento que le reduzco el texto que viene debajo tambien
                # deberia subirse», video del usuario, 19-ago-2026.)
                nuevas_filas, encogio = _acortar_tabla(
                    filas, borde, max(deseado, filas[borde - 1] + minimo_arriba))
                # Se apunta para el final: lo de abajo sube cuando la tabla ya
                # este redibujada en su sitio nuevo.
                if encogio > 0.5:
                    recogida = (filas[-1] + 0.5, -encogio)
            else:
                nuevas_filas, aviso_extra = _mover_borde(
                    filas, borde, delta, minimo_arriba,
                    _tope_filas(pagina, columnas, filas),
                    minimo_siguiente=minimo_abajo)
            nuevas_columnas = columnas
            desplazamientos = None      # se calcula renglón a renglón, más abajo

        # Todo el texto se queda en su misma columna: aquí no se reparte nada,
        # solo cambia de medida la celda que lo contiene.
        for renglon in renglones:
            renglon['destino'] = renglon['columna']
        tablas_pdf._preparar(documento, pagina, cliente, renglones, None,
                             nuevas_columnas)

        # Los colores de fondo, antes de borrar nada: la rejilla tiene los
        # mismos bordes, solo que en otro sitio, así que cada relleno vuelve a
        # su misma celda y acompaña a la fila o columna que cambió de medida.
        fondos = tablas_fondos.leer(pagina, columnas, filas)
        # Y las imágenes que hubiera dentro (un logotipo, una firma escaneada).
        # Se leen aquí, después de un posible alargado de la tabla: ese empuja
        # el contenido de la página y rehace la hoja, así que las coordenadas de
        # antes ya no valdrían.
        imagenes = tablas_imagenes.leer(pagina, columnas, filas)

        # Al ENCOGER, la tabla nueva no cubre a la vieja: hay que borrar la
        # unión de las dos o se quedarían las rayas de antes.
        abarca = fitz.Rect(min(columnas[0], nuevas_columnas[0]),
                           min(filas[0], nuevas_filas[0]),
                           max(columnas[-1], nuevas_columnas[-1]),
                           max(filas[-1], nuevas_filas[-1]))
        anotacion = pagina.add_redact_annot(abarca)
        anotacion.update()
        tablas_pdf._borrar_zona(pagina)

        if que == 'fila':
            # Cada renglón lleva su propio desplazamiento, recortado para que no
            # se salga de la celda; `_redibujar` solo sabe de desplazamiento por
            # fila, así que se le pasa el de cada uno ya calculado.
            desplazamientos = {}
            for renglon in renglones:
                renglon['dy_propio'] = _desplazamiento_de(renglon, filas, nuevas_filas)
            apretados = _redibujar_con_dy(pagina, documento, cliente, renglones,
                                          nuevas_columnas, nuevas_filas, grosor,
                                          color_raya, columnas, filas, fondos,
                                          imagenes)
        else:
            apretados = tablas_pdf._redibujar(pagina, documento, cliente, renglones,
                                              nuevas_columnas, nuevas_filas, grosor,
                                              color_raya, desplazamientos,
                                              previas=(columnas, filas),
                                              fondos=fondos, imagenes=imagenes)
        # Y ahora si: con la tabla ya dibujada en su sitio nuevo, lo de debajo
        # sube para cerrar el hueco, y lo que se hubiera ido a otra hoja vuelve.
        if recogida:
            from .recoger_pagina import recoger
            try:
                subida = recoger(documento, int(numero_pagina), *recogida)
                if subida:
                    aviso_extra = (aviso_extra + '; ' + subida) if aviso_extra else subida
            except Exception as excepcion:
                logger.warning('no se pudo recomponer bajo la tabla: %s', excepcion)

        aviso = tablas_pdf._avisos(apretados, imagenes)
        if aviso_extra:
            aviso = (aviso + '; ' + aviso_extra) if aviso else aviso_extra
        return guardado_pdf.guardar(documento), aviso
    finally:
        guardado_pdf.cerrar(documento)


def _redibujar_con_dy(pagina, documento, cliente, renglones, columnas, filas,
                      grosor, color_raya, previas_columnas=None,
                      previas_filas=None, fondos=None, imagenes=None):
    """Como `tablas_pdf._redibujar`, pero cada renglón con SU desplazamiento.

    Hace falta porque al cambiar el alto de una fila no todos sus renglones se
    mueven igual: los que estaban pegados al fondo bajan con el fondo, los de
    arriba se quedan arriba, y ninguno puede salirse de su celda.
    """
    anotacion = pagina.add_redact_annot(
        fitz.Rect(columnas[0], filas[0], columnas[-1], filas[-1]))
    anotacion.update()
    tablas_pdf._borrar_zona(pagina)

    if fondos is not None:
        fondos.pintar(pagina, columnas, filas)
    if imagenes is not None:
        imagenes.pintar(pagina, columnas, filas)

    tablas_pdf._trazar_rejilla(pagina, columnas, filas, grosor, color_raya,
                               previas_columnas, previas_filas)

    from . import tablas_escritura as escritura
    apretados = 0
    for renglon in renglones:
        if renglon.get('destino') is None or not renglon.get('resolucion'):
            continue
        # Cambio de alto: las columnas no se mueven, el renglón se reescribe
        # con su misma letra y su misma x; solo cambia de altura.
        if escritura.reescribir_fiel(pagina, cliente, renglon, columnas,
                                     renglon.get('dy_propio', 0.0)):
            apretados += 1
    return apretados


def _alargar_tabla(documento, numero_pagina, columnas, filas, borde, hasta, cliente):
    """Baja la raya `borde` hasta `hasta` alargando la tabla. Devuelve (filas, aviso).

    Las rayas de abajo bajan lo mismo, así que ninguna fila pierde alto: la tabla
    crece. Antes se hace sitio debajo empujando lo que hubiera, que ya sabe
    respetar encabezados y pies y pasar a otra página lo que no quepa.
    """
    from .empuje_pagina import empujar as empujar_banda

    crecimiento = hasta - filas[borde]
    aviso = ''
    try:
        aviso = empujar_banda(documento, int(numero_pagina), filas[-1] + 0.5,
                              crecimiento) or ''
    except Exception as excepcion:
        logger.warning('no se pudo hacer sitio bajo la tabla: %s', excepcion)

    nuevas = [y if i < borde else y + crecimiento for i, y in enumerate(filas)]
    return nuevas, aviso


def _acortar_tabla(filas, borde, hasta):
    """Sube la raya `borde` hasta `hasta` encogiendo la tabla.

    Devuelve (filas nuevas, cuanto se encogio). El gemelo de `_alargar_tabla`,
    con una diferencia de orden que importa: alargar hace sitio ANTES (empuja lo
    de abajo y luego crece), pero encoger tiene que recomponer DESPUES, cuando
    la tabla ya se ha redibujado. Si se recompone antes, el borrado de la zona
    de la tabla se lleva por delante el texto recien subido y queda amontonado a
    medias. (19-ago-2026.)
    """
    encogimiento = filas[borde] - hasta
    nuevas = [y if i < borde else y - encogimiento for i, y in enumerate(filas)]
    return nuevas, encogimiento


def _ensanchar_tabla(pagina, columnas, borde, hasta):
    """Lleva la raya `borde` a `hasta` ensanchando la tabla. Devuelve (columnas, aviso).

    Las rayas de la derecha se corren lo mismo, así que ninguna columna pierde
    ancho: crece la tabla. Se para en el margen de la hoja — el papel manda.
    """
    margen = max(0.0, _tope_columnas(pagina, columnas) - columnas[-1])
    exceso = hasta - (columnas[borde + 1] - MINIMO_COLUMNA)
    corrimiento = min(exceso, margen)
    if corrimiento <= 0.5:
        return list(columnas), ('la tabla ya llega al margen de la hoja: '
                                'para ensanchar esta columna hay que estrechar otra')
    nuevas = [x if i <= borde else x + corrimiento for i, x in enumerate(columnas)]
    nuevas[borde] = columnas[borde + 1] - MINIMO_COLUMNA + corrimiento
    nuevas[borde] = min(nuevas[borde], nuevas[borde + 1] - MINIMO_COLUMNA)
    aviso = 'la tabla se ensanchó'
    if corrimiento < exceso - 0.5:
        aviso += ' hasta el margen de la hoja'
    return nuevas, aviso
