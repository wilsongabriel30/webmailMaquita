"""Qué nombres de carpeta acepta la API (11/11/2026).

La lista de caracteres permitidos estaba copiada en cuatro rutas y no incluía «․» (U+2024), el
punto que la interfaz pone desde el 10/11 en lugar del punto normal (que en el servidor separa
niveles). Resultado: una carpeta renombrada con punto, p. ej. «1․Dirección», se veía en el árbol
pero no se podía abrir (400 «Nombre de carpeta inválido»).

Aquí se valida por lo que NO puede llevar un nombre para ser seguro en IMAP: caracteres de
control, comillas, barra invertida, llaves y los comodines de LIST. Todo lo demás (tildes, signos,
el punto especial…) es válido; `_quote_folder` lo codifica y lo entrecomilla al usarlo.
"""

from __future__ import annotations

LONGITUD_MAXIMA = 200
_PROHIBIDOS = set('"\\{}*%')


def nombre_valido(carpeta: str) -> bool:
    if (
        not isinstance(carpeta, str)
        or not carpeta.strip()
        or len(carpeta) > LONGITUD_MAXIMA
    ):
        return False
    return not any(ord(c) < 32 or ord(c) == 127 or c in _PROHIBIDOS for c in carpeta)
