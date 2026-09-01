# -*- coding: utf-8 -*-
"""
Recomponer hacia ARRIBA: subir lo de abajo y recuperar lo que se fue de hoja.
=============================================================================
El gemelo de `empuje_pagina.py`. Aquel baja lo que hay bajo una tabla cuando
esta crece, y lo que no cabe lo pasa a la pagina siguiente. Este hace el camino
de vuelta.

Hacia falta porque el editor era ASIMETRICO y el usuario lo vio enseguida:

  «esto si se va para abajo, pero el momento que le reduzco, el texto que viene
   debajo tambien deberia subirse» — video del 19-ago-2026.

Al agrandar una fila 220 pt, los totales de su cotizacion pasaban a una segunda
hoja. Al volver a reducirla, en la primera hoja subia lo que quedaba... y los
totales se quedaban abandonados en la pagina 2, que ademas ya no se borraba.
Sin ningun aviso.

Que hace ahora, decidido con el usuario el 19-ago-2026: **recomponer el
documento entero**. Se sube lo de esta pagina, y con el hueco que queda libre al
final se va subiendo, en cascada, lo que quepa de las paginas siguientes. Una
pagina que se queda sin nada se elimina.

Que se respeta, igual que al empujar: el encabezado y el pie de cada pagina son
FIJOS —ni se mueven ni se pisan—, y el texto sigue siendo texto, con su letra,
su color y su sitio horizontal.

Autoria: Equipo de Tecnologia Maquita — 2026-08-19
"""

import logging

import fitz

from .empuje_pagina import (MARGEN_INFERIOR, MARGEN_SUPERIOR_NUEVA, RESPIRO_PIE,
                            _abajo_de, _arriba_de, _borrar_banda_entre, _cliente,
                            _leer_banda, _pintar, _reparte, zonas_fijas)

logger = logging.getLogger(__name__)

# Aire entre lo ultimo de una pagina y el bloque que sube desde la siguiente.
# Es el hueco que deja un documento de oficina entre dos bloques seguidos.
SEPARACION_BLOQUES = 12.0
# Por debajo de esto no merece la pena subir nada: el hueco no da ni para un
# renglon y solo se conseguiria mover el texto de sitio sin ganar nada.
HUECO_MINIMO = 16.0


def _limite_de(pagina, pie):
    """Hasta donde se puede dibujar en esa hoja sin pisar el pie."""
    return min(pagina.rect.height - MARGEN_INFERIOR, pie - RESPIRO_PIE)


def _cuerpo_de(documento, numero, cliente, zonas=None):
    """Lo que hay entre el encabezado y el pie de esa pagina, y sus dos topes.

    `zonas` es una memoria {numero: (tope, pie)} compartida por toda la
    recomposicion: el encabezado y el pie son FIJOS —ni se mueven ni se pisan—
    asi que medirlos una vez por pagina basta, y medirlos cada vuelta costaba
    130 ms por pagina en un documento largo.
    """
    pagina = documento[numero - 1]
    if zonas is not None and numero in zonas:
        tope, pie = zonas[numero]
    else:
        tope, pie = zonas_fijas(documento, numero)
        if zonas is not None:
            zonas[numero] = (tope, pie)
    renglones, imagenes, trazos, complejos = _leer_banda(pagina, tope, cliente)
    if pie < pagina.rect.height:
        renglones = [r for r in renglones if r['rect'].y1 <= pie]
        imagenes = [i for i in imagenes if i['rect'].y1 <= pie]
        trazos = [dict(t, piezas=[p for p in t['piezas']
                                  if (p[2].y if p[0] == 'l' else p[1].y1) <= pie])
                  for t in trazos]
        trazos = [t for t in trazos if t['piezas']]
    return (renglones, imagenes, trazos, complejos), tope, pie


def _esta_vacia(pagina):
    """Una pagina sin nada: ni texto, ni imagenes, ni un solo trazo."""
    try:
        if pagina.get_text('text').strip():
            return False
        if pagina.get_image_info():
            return False
        if pagina.get_drawings():
            return False
    except Exception:
        return False
    return True


def recoger(documento, numero_pagina, y_desde, dy):
    """Sube `-dy` lo que hay bajo `y_desde` y recompone el resto del documento.

    `dy` es negativo (subir). Devuelve un aviso, o cadena vacia.

    IMPORTANTE para quien llame: esto PINTA en la pagina. Si la operacion en
    curso todavia va a borrar y redibujar una zona —como hace el arrastre de una
    tabla—, hay que llamar aqui DESPUES de ese redibujado; si no, el borrado se
    lleva por delante lo que se acaba de recolocar. Se aprendio en el propio
    arreglo del 19-ago-2026: al encoger la tabla, el bloque de totales subia
    bien y acto seguido lo borraba el redibujado de la tabla, y en el papel
    quedaba el texto amontonado y a medias.
    """
    if dy >= 0:
        raise ValueError('recoger() sube: dy tiene que ser negativo.')

    cliente = _cliente()
    pagina = documento[numero_pagina - 1]
    _tope, pie_propio = zonas_fijas(documento, numero_pagina)
    renglones, imagenes, trazos, complejos = _leer_banda(pagina, y_desde, cliente)
    if pie_propio < pagina.rect.height:
        renglones = [r for r in renglones if r['rect'].y1 <= pie_propio]
        imagenes = [i for i in imagenes if i['rect'].y1 <= pie_propio]

    # 1) Subir lo de esta misma pagina. Se borra hasta el fondo real de lo que
    #    se mueve —no solo hasta donde acaba tras subir—: si no, la parte de
    #    abajo se queda dibujada en su sitio viejo y sale por duplicado.
    if renglones or imagenes or trazos:
        techo = max(y_desde, _arriba_de(renglones, imagenes, trazos, dy) - 0.5)
        hasta = _abajo_de(renglones, imagenes, trazos, 0.0) + 2.0
        if pie_propio < pagina.rect.height:
            hasta = min(hasta, pie_propio - 0.5)
        _borrar_banda_entre(pagina, techo, hasta)
        _pintar(pagina, cliente, documento, renglones, imagenes, trazos, dy)

    # 2) Y ahora, en cascada: lo que quepa de cada pagina sube a la anterior.
    zonas = {}
    subidas, borradas = 0, 0
    numero = numero_pagina
    vueltas = 0
    while numero < documento.page_count:
        vueltas += 1
        if vueltas > 400:              # cortafuegos, nunca deberia pasar
            logger.warning('recomposicion: demasiadas vueltas, se detiene')
            break

        actual = documento[numero - 1]
        cuerpo, _tope_a, pie_a = _cuerpo_de(documento, numero, cliente, zonas)
        limite = _limite_de(actual, pie_a)
        fondo = _abajo_de(cuerpo[0], cuerpo[1], cuerpo[2], 0.0)
        if not fondo:                  # pagina sin cuerpo: se llena desde arriba
            fondo = max(_tope_a, MARGEN_SUPERIOR_NUEVA) - SEPARACION_BLOQUES
        hueco = limite - fondo - SEPARACION_BLOQUES
        if hueco < HUECO_MINIMO:
            break                      # ya no cabe nada mas: se acabo

        siguiente = documento[numero]           # la de abajo (0-based)
        traido, tope_s, pie_s = _cuerpo_de(documento, numero + 1, cliente, zonas)
        if not (traido[0] or traido[1] or traido[2]):
            if _esta_vacia(siguiente):
                documento.delete_page(numero)   # 0-based: borra la de abajo
                borradas += 1
                zonas.clear()                   # la numeracion cambio
                continue                        # sin avanzar: se corrio una
            numero += 1
            continue

        arriba_s = _arriba_de(traido[0], traido[1], traido[2], 0.0)
        # Cuanto hay que subir para pegarlo justo tras lo ultimo de esta pagina.
        desplazamiento = (fondo + SEPARACION_BLOQUES) - arriba_s
        sube, queda = _reparte(traido[0], traido[1], traido[2],
                               desplazamiento, limite)
        if not (sube[0] or sube[1] or sube[2]):
            break                      # no cabe ni el primer bloque

        # Se borra en la de abajo TODO lo que se va a recolocar (lo que sube y
        # lo que se queda), y se vuelve a dibujar donde toque.
        techo_s = max(tope_s, arriba_s - 0.5)
        hasta_s = _abajo_de(traido[0], traido[1], traido[2], 0.0) + 2.0
        if pie_s < siguiente.rect.height:
            hasta_s = min(hasta_s, pie_s - 0.5)
        _borrar_banda_entre(siguiente, techo_s, hasta_s)

        _pintar(actual, cliente, documento, sube[0], sube[1], sube[2], desplazamiento)
        subidas += 1

        if queda[0] or queda[1] or queda[2]:
            # Lo que no cupo se queda en su pagina, pero pegado a su margen: si
            # no, dejaria arriba el hueco de lo que acaba de irse.
            arranque = max(tope_s, MARGEN_SUPERIOR_NUEVA)
            resto_arriba = _arriba_de(queda[0], queda[1], queda[2], 0.0)
            _pintar(siguiente, cliente, documento, queda[0], queda[1], queda[2],
                    arranque - resto_arriba)
            numero += 1                # esta pagina ya esta llena; a la siguiente
        elif _esta_vacia(siguiente):
            documento.delete_page(numero)
            borradas += 1              # sin avanzar: la de mas abajo ocupa su sitio
            zonas.clear()              # la numeracion cambio

    avisos = []
    if subidas:
        avisos.append('el texto de abajo subió')
    if borradas:
        avisos.append('se quitó %d página(s) que quedó vacía' % borradas
                      if borradas == 1 else
                      'se quitaron %d páginas que quedaron vacías' % borradas)
    if complejos:
        avisos.append('había dibujo vectorial complejo y se redibujó de forma simple')
    return '; '.join(avisos)
