# -*- coding: utf-8 -*-
"""
Tablas EN EL PROPIO PDF: columnas, filas y contenido de las celdas.
====================================================================
El usuario pidió poder editar la tabla **ahí mismo**, sin que el documento se
transforme en otra cosa: «no necesito que me transformes a word sino que ahí
mismo me permitas hacer esos cambios»; y luego «también debe permitirme
agregar filas», «y quitarlas», «y agregar texto en esas filas o columnas
agregadas».

Un PDF no tiene tablas: tiene rayas y texto colocado en coordenadas. Así que
nada de esto "inserta" nada — hay que **reconocer la tabla, borrar esa zona y
volver a dibujarla**. Eso hace este módulo:

  `detectar()`         qué tablas hay en la página y dónde
  `cambiar_columna()`  agrega o quita una columna
  `cambiar_fila()`     agrega o quita una fila
  `mover_columna()`    lleva una columna a otra posición
  `mover_fila()`       lleva una fila a otra posición
  `escribir_celda()`   pone (o cambia) el texto de una celda

Las tres operaciones comparten el mismo motor: leer la tabla entera con su
tipografía, calcular la geometría nueva, borrar y redibujar. Se conserva el
tipo de letra (la incrustada del propio documento cuando se puede), el cuerpo,
la cursiva, la negrita, el color, la alineación de cada celda y el grosor y
color de las rayas. Todo se lee ANTES de borrar, porque después ya no está.

**Al cambiar columnas solo se mueve la horizontal, y al cambiar filas solo la
vertical.** Cada renglón conserva todo lo demás intacto, por eso el resultado
se parece al original y no a una tabla rehecha desde cero.

Las imágenes que haya dentro (un logotipo, una firma escaneada) se leen antes
de borrar y se vuelven a colocar en su celda: hasta el 17-08-2026 se perdían y
solo se avisaba de ello.

Lo que no se puede prometer: si al estrechar una columna un texto ya no cabe,
se encoge hasta un mínimo legible y, si aun así no entra, se parte en
renglones. Eso se le avisa al usuario.

Autoría: Equipo de Tecnología Maquita — 2026-07-27
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

logger = logging.getLogger(__name__)

from .tablas_base import (  # noqa: F401
    ALTO_FILA_POR_DEFECTO, MINIMO_FILA, RESPIRO, SEGURIDAD_ABAJO,
    TOLERANCIA_RAYA, _TablaConocida, _bordes_de_columna, _bordes_de_fila,
    _cliente,
)
from .tablas_rejilla import (  # noqa: F401
    _avisos, _borrar_zona, _preparar, _redibujar,
)
from .tablas_deteccion import _abrir  # noqa: F401

# ── Lo que antes vivía aquí y ahora está repartido ──────────────────────
# Se vuelve a exponer desde este módulo para que nada de fuera tenga que
# cambiar: `tablas_medidas`, `tablas_mover`, `worker_pdf` y la API siguen
# pidiéndoselo a `tablas_pdf` como siempre.
from .tablas_geometria import (  # noqa: F401
    _indice_en, _alineacion, _acumular,
    _mapa_de_columnas, _aire_de_cada_fila, columnas_tras_insertar,
    columnas_tras_eliminar, filas_tras_insertar, filas_tras_eliminar,
    _permutar, _mapa_permutacion, _filas_previas,
)
from .tablas_rejilla import (  # noqa: F401
    _rayas_dibujadas, _hay_raya_en, _trazar_rejilla,
    _estilo_de_las_rayas, _zona_a_borrar,
)
from .tablas_deteccion import (  # noqa: F401
    _texto_legible, _tablas_de, _hay_imagenes,
    _huella, _clave_comun, _recordar_aqui,
    detectar, _fondo_del_texto, _encabezados,
    _interlineado_real, _agrupar_por_linea, _celdas_de,
    _sitio_libre_abajo, _renglones_dentro, _leer_tabla,
)
from .tablas_celdas import (  # noqa: F401
    _modelo_de_letra, _recorte_del_texto, _estilos_por_linea,
    _agrandar_fila, escribir_celda,
)







# ── OPERACIÓN: COLUMNAS ──────────────────────────────────────────────────
def cambiar_columna(contenido_pdf, numero_pagina, indice_tabla, accion, posicion,
                    titulo=''):
    """Inserta o elimina una columna. Devuelve (pdf, aviso)."""
    if accion not in ('insertar', 'eliminar'):
        raise ValueError('Acción desconocida: %s' % accion)
    cliente = _cliente()
    documento, pagina, tabla = _abrir(contenido_pdf, numero_pagina, indice_tabla)
    try:
        columnas = _bordes_de_columna(tabla)
        filas = _bordes_de_fila(tabla)
        recuadro = fitz.Rect(columnas[0], filas[0], columnas[-1], filas[-1])
        renglones = _leer_tabla(pagina, columnas, filas, cliente)
        grosor, color_raya = _estilo_de_las_rayas(pagina, recuadro)
        # Las imágenes de la tabla se leen ANTES de borrar (el borrado se las
        # lleva) y se vuelven a colocar con la geometría nueva.
        imagenes = tablas_imagenes.leer(pagina, columnas, filas)

        nuevas = (columnas_tras_insertar(columnas, posicion) if accion == 'insertar'
                  else columnas_tras_eliminar(columnas, posicion))
        mapa = _mapa_de_columnas(accion, posicion, len(columnas) - 1)
        # Los colores de fondo se leen ANTES de borrar: el borrado se los lleva.
        fondos = tablas_fondos.leer(pagina, columnas, filas)
        _preparar(documento, pagina, cliente, renglones, mapa, nuevas)

        extra = []
        if accion == 'insertar' and titulo.strip():
            modelo = min((r for r in renglones if r.get('resolucion')),
                         key=lambda r: r['rect'].y0, default=None)
            if modelo:
                extra.append({'columna': posicion, 'base': modelo['base'],
                              'texto': titulo.strip(), 'alineacion': 'centro',
                              'resolucion': modelo['resolucion'],
                              'estilo': modelo['estilo']})

        # Dónde estaba antes cada raya vertical. Sin esto se preguntaba por la
        # posición NUEVA —y al agregar una columna se mueven todas—, no se
        # reconocía ninguna raya de antes y la tabla se quedaba SIN sus rayas
        # verticales: a la operación siguiente ya no se reconocía como tabla y
        # se perdían también los fondos. (18-ago-2026.)
        bordes_previos = _filas_previas(columnas, nuevas, posicion, accion)

        apretados = _redibujar(pagina, documento, cliente, renglones, nuevas, filas,
                               grosor, color_raya, None, extra,
                               previas=(bordes_previos, None),
                               fondos=fondos, mapa_columnas=mapa,
                               imagenes=imagenes)
        return guardado_pdf.guardar(documento), _avisos(apretados, imagenes)
    finally:
        guardado_pdf.cerrar(documento)


# ── OPERACIÓN: FILAS ─────────────────────────────────────────────────────
def cambiar_fila(contenido_pdf, numero_pagina, indice_tabla, accion, posicion,
                 empujar=False):
    """Inserta o elimina una fila. Devuelve (pdf, aviso).

    `empujar=True` baja todo lo que hay bajo la tabla EN ESA PÁGINA para hacerle
    sitio a la fila, y lo que se salga pasa a una página nueva (el resto del
    documento no se toca). Es lo que el usuario pidió tras descartar reconstruir
    el documento entero, que dejaba la proforma de 65 páginas en 94.
    """
    if accion not in ('insertar', 'eliminar'):
        raise ValueError('Acción desconocida: %s' % accion)
    cliente = _cliente()
    documento, pagina, tabla = _abrir(contenido_pdf, numero_pagina, indice_tabla)
    try:
        columnas = _bordes_de_columna(tabla)
        filas = _bordes_de_fila(tabla)
        recuadro = fitz.Rect(columnas[0], filas[0], columnas[-1], filas[-1])
        renglones = _leer_tabla(pagina, columnas, filas, cliente)
        grosor, color_raya = _estilo_de_las_rayas(pagina, recuadro)

        aviso_extra = ''
        if accion == 'insertar':
            sitio = _sitio_libre_abajo(pagina, columnas, filas)
            if empujar:
                # Se hace sitio de verdad: lo de abajo baja el alto de una fila
                # y lo que se salga de la hoja pasa a una página nueva.
                from .empuje_pagina import empujar as empujar_banda
                altos = [filas[i + 1] - filas[i] for i in range(len(filas) - 1)]
                alto_nuevo = max(MINIMO_FILA, min(30.0, sorted(altos[1:] or altos)[0]))
                aviso_extra = empujar_banda(documento, int(numero_pagina),
                                            filas[-1] + 0.5, alto_nuevo)
                # Tras empujar, la página cambió: hay que releerla
                pagina = documento[int(numero_pagina) - 1]
                renglones = _leer_tabla(pagina, columnas, filas, cliente)
                sitio = alto_nuevo
            nuevas_filas, desplazamientos, _pos = filas_tras_insertar(
                filas, posicion, renglones, sitio)
            # Los renglones de la fila que se parte en dos no existen: la nueva
            # nace vacía y el usuario escribe en ella.
            for renglon in renglones:
                renglon['destino'] = renglon['columna']
        else:
            nuevas_filas, desplazamientos, alto_quitado = filas_tras_eliminar(filas,
                                                                              posicion)
            fuera = [r for r in renglones if r['fila'] == posicion]
            if fuera:
                aviso_extra = 'se quitó el contenido de esa fila'
            renglones = [r for r in renglones if r['fila'] != posicion]
            for renglon in renglones:
                renglon['destino'] = renglon['columna']

        _preparar(documento, pagina, cliente, renglones, None, columnas)

        # Los colores de fondo (la cabecera azul, el sombreado de las filas) se
        # leen ANTES de borrar, que es cuando todavía están, y se vuelven a
        # pintar más abajo con la geometría nueva. Sin esto, la cabecera se
        # quedaba blanca sobre blanco y parecía haber desaparecido — el vídeo
        # del usuario del 05-08-2026.
        fondos = tablas_fondos.leer(pagina, columnas, filas)
        # Y lo mismo con las imágenes (un logotipo, una firma escaneada). Se
        # leen aquí, y no más arriba, porque al empujar la página para hacer
        # sitio a la fila el documento se rehace y las coordenadas de antes ya
        # no valdrían.
        imagenes = tablas_imagenes.leer(pagina, columnas, filas)
        mapa_de_filas = tablas_fondos.mapa_de_celdas(accion, posicion, len(filas) - 1)
        if accion == 'insertar':
            # «Una fila replicada de la anterior pero vacía»: si sus vecinas van
            # pintadas, la nueva también.
            fondos.agregar_fila(posicion, fondos.heredar_fila(posicion))

        # La zona a borrar tiene que cubrir la tabla vieja Y la nueva (al quitar
        # una fila la tabla se acorta; al meterla, se alarga)
        abarca = fitz.Rect(columnas[0], min(filas[0], nuevas_filas[0]),
                           columnas[-1], max(filas[-1], nuevas_filas[-1]))
        anotacion = pagina.add_redact_annot(abarca)
        anotacion.update()
        _borrar_zona(pagina)

        # Primero el color, que va por debajo de todo; luego las imágenes, y
        # encima las rayas y el texto.
        fondos.pintar(pagina, columnas, nuevas_filas, mapa_filas=mapa_de_filas)
        imagenes.pintar(pagina, columnas, nuevas_filas, mapa_filas=mapa_de_filas)

        # La fila que se acaba de meter (o el hueco de la que se quitó) hace
        # que las listas no casen por índice: se rehace la de antes a la medida.
        _trazar_rejilla(pagina, columnas, nuevas_filas, grosor, color_raya,
                        columnas, _filas_previas(filas, nuevas_filas, posicion,
                                                 accion))

        apretados = 0
        for renglon in renglones:
            if not renglon.get('resolucion'):
                continue
            dy = desplazamientos.get(renglon['fila'], 0.0)
            if escritura.escribir_renglon(pagina, cliente, renglon, columnas, dy):
                apretados += 1

        # Al QUITAR una fila la tabla se acorta: lo que hay debajo sube para
        # cerrar el hueco, y lo que se hubiera ido a otra hoja vuelve — el mismo
        # camino de vuelta que al encoger la tabla arrastrando (19-ago-2026).
        # Después del redibujado, nunca antes: recomponer pinta en la página, y
        # el borrado de la zona de la tabla se lo llevaría por delante.
        if accion == 'eliminar' and alto_quitado > 0.5:
            from .recoger_pagina import recoger
            try:
                subida = recoger(documento, int(numero_pagina),
                                 filas[-1] + 0.5, -alto_quitado)
                if subida:
                    aviso_extra = ((aviso_extra + '; ' + subida)
                                   if aviso_extra else subida)
            except Exception as excepcion:
                logger.warning('no se pudo recomponer bajo la tabla: %s', excepcion)

        aviso = _avisos(apretados, imagenes)
        if aviso_extra:
            aviso = (aviso + '; ' + aviso_extra) if aviso else aviso_extra
        return guardado_pdf.guardar(documento), aviso
    finally:
        guardado_pdf.cerrar(documento)


def mover_columna(contenido_pdf, numero_pagina, indice_tabla, desde, hasta):
    """Lleva una columna a otra posición. Devuelve (pdf, aviso)."""
    cliente = _cliente()
    documento, pagina, tabla = _abrir(contenido_pdf, numero_pagina, indice_tabla)
    try:
        columnas = _bordes_de_columna(tabla)
        filas = _bordes_de_fila(tabla)
        recuadro = fitz.Rect(columnas[0], filas[0], columnas[-1], filas[-1])
        renglones = _leer_tabla(pagina, columnas, filas, cliente)
        grosor, color_raya = _estilo_de_las_rayas(pagina, recuadro)
        # Las imágenes de la tabla se leen ANTES de borrar (el borrado se las
        # lleva) y se vuelven a colocar con la geometría nueva.
        imagenes = tablas_imagenes.leer(pagina, columnas, filas)

        anchos = [columnas[i + 1] - columnas[i] for i in range(len(columnas) - 1)]
        nuevas = _acumular(columnas[0], _permutar(anchos, desde, hasta))
        mapa = _mapa_permutacion(len(anchos), desde, hasta)
        fondos = tablas_fondos.leer(pagina, columnas, filas)
        _preparar(documento, pagina, cliente, renglones, mapa, nuevas)

        apretados = _redibujar(pagina, documento, cliente, renglones, nuevas, filas,
                               grosor, color_raya, None, None,
                               fondos=fondos, mapa_columnas=mapa,
                               imagenes=imagenes)
        return guardado_pdf.guardar(documento), _avisos(apretados, imagenes)
    finally:
        guardado_pdf.cerrar(documento)


def mover_fila(contenido_pdf, numero_pagina, indice_tabla, desde, hasta):
    """Lleva una fila a otra posición. Devuelve (pdf, aviso)."""
    cliente = _cliente()
    documento, pagina, tabla = _abrir(contenido_pdf, numero_pagina, indice_tabla)
    try:
        columnas = _bordes_de_columna(tabla)
        filas = _bordes_de_fila(tabla)
        recuadro = fitz.Rect(columnas[0], filas[0], columnas[-1], filas[-1])
        renglones = _leer_tabla(pagina, columnas, filas, cliente)
        grosor, color_raya = _estilo_de_las_rayas(pagina, recuadro)
        # Las imágenes de la tabla se leen ANTES de borrar (el borrado se las
        # lleva) y se vuelven a colocar con la geometría nueva.
        imagenes = tablas_imagenes.leer(pagina, columnas, filas)

        altos = [filas[i + 1] - filas[i] for i in range(len(filas) - 1)]
        nuevas_filas = _acumular(filas[0], _permutar(altos, desde, hasta))
        mapa = _mapa_permutacion(len(altos), desde, hasta)

        # Cada renglón baja o sube lo que se haya movido SU fila
        desplazamientos = {}
        for vieja, nueva in mapa.items():
            desplazamientos[vieja] = nuevas_filas[nueva] - filas[vieja]

        for renglon in renglones:
            renglon['destino'] = renglon['columna']
        fondos = tablas_fondos.leer(pagina, columnas, filas)
        _preparar(documento, pagina, cliente, renglones, None, columnas)

        apretados = _redibujar(pagina, documento, cliente, renglones, columnas,
                               nuevas_filas, grosor, color_raya, desplazamientos, None,
                               fondos=fondos, mapa_filas=mapa,
                               imagenes=imagenes)
        return guardado_pdf.guardar(documento), _avisos(apretados, imagenes)
    finally:
        guardado_pdf.cerrar(documento)

