# -*- coding: utf-8 -*-
"""
De qué COLOR está escrito cada renglón del papel.
=================================================
La digitalización escribía todo en negro: un título azul o un importe en rojo
del escaneo salían negros, y el usuario lo veía como «se me cambia el color»
en cuanto cualquier edición reescribía la zona (vídeo del 20-ago-2026).

Se mira el recorte del renglón en la imagen A COLOR: la tinta son los píxeles
claramente más oscuros que el fondo del propio recorte, y el color del renglón
es la mediana de esos píxeles canal a canal. La mediana ignora el suavizado de
los bordes (píxeles a medio camino entre tinta y fondo) sin listas de casos.

Un escaneo tiñe el negro de gris pardo o azulado: si el color medido apenas
tiene saturación, se devuelve negro puro, que es lo que el documento quería
decir. Solo un color franco (azul, rojo, verde...) se conserva como tal.

Autoría: Equipo de Tecnología Maquita — 2026-08-20
"""

# Cuánto más oscuro que el fondo tiene que ser un píxel para contar como tinta.
CONTRASTE_MINIMO = 60
# Con menos píxeles de tinta que esto, la medida no es fiable.
TINTA_MINIMA = 12
# Diferencia máxima entre canales para considerar el color «sin color» (gris).
SATURACION_GRIS = 28


def color_de_renglon(imagen_rgb, renglon):
    """(r, g, b) en 0..1 del trazo de ese renglón, o None si no se puede medir.

    `imagen_rgb` es la página escaneada abierta con PIL en modo RGB; `renglon`
    lleva su caja en píxeles ('x', 'y', 'ancho', 'alto'), la misma que usa
    `ocr_estilo.medir_renglon`.
    """
    try:
        recorte = imagen_rgb.crop((renglon['x'], renglon['y'],
                                   renglon['x'] + renglon['ancho'],
                                   renglon['y'] + renglon['alto']))
        if recorte.height < 4 or recorte.width < 4:
            return None
        pixeles = list(recorte.getdata())
    except Exception:
        return None

    luces = sorted(r + g + b for r, g, b in pixeles)
    # El fondo es lo más claro que abunda: el percentil alto de la luz.
    fondo = luces[int(len(luces) * 0.85)]
    umbral = fondo - CONTRASTE_MINIMO * 3
    tinta = [p for p in pixeles if p[0] + p[1] + p[2] < umbral]
    if len(tinta) < TINTA_MINIMA:
        return None
    # El corazon del trazo: el suavizado de los bordes son pixeles a medio
    # camino entre la tinta y el fondo, y aclaraban el color medido (un rojo
    # cc1a1a salia d54747). Se mide solo sobre la mitad mas oscura.
    tinta.sort(key=lambda p: p[0] + p[1] + p[2])
    tinta = tinta[:max(TINTA_MINIMA, len(tinta) // 2)]

    def mediana(valores):
        ordenados = sorted(valores)
        return ordenados[len(ordenados) // 2]

    rojo = mediana([p[0] for p in tinta])
    verde = mediana([p[1] for p in tinta])
    azul = mediana([p[2] for p in tinta])

    if max(rojo, verde, azul) - min(rojo, verde, azul) <= SATURACION_GRIS:
        return (0.0, 0.0, 0.0)      # gris del escáner: era negro
    return (rojo / 255.0, verde / 255.0, azul / 255.0)
