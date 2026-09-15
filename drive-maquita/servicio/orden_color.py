"""Drive Maquita — ordenar por COLOR de carpeta (14/09/2026).

Pedido de Wilson: en «08 Proyectos» pintan las carpetas por estado y quieren
verlas agrupadas por ese color. El menú «Ordenar» solo ofrecía nombre/fecha.

Criterio: primero las carpetas pintadas, agrupadas siguiendo el orden de la
paleta del menú contextual (rojo → rosa → púrpura → … → gris), y al final las
sin color; dentro de cada color, por nombre natural. Los archivos no tienen
color: van por nombre. Lo usa api_archivos.listar cuando ?orden=color.
"""
import re

# Mismo orden que los botones .gd-color-btn de _menu-contextual.html.
PALETA = [
    '#ef9a9a', '#f48fb1', '#f8bbd9', '#ce93d8', '#b39ddb', '#9fa8da',
    '#90caf9', '#81d4fa', '#b3e5fc', '#80deea', '#80cbc4', '#a5d6a7',
    '#c8e6c9', '#c5e1a5', '#e6ee9c', '#fff59d', '#ffe082', '#ffcc80',
    '#ffab91', '#bcaaa4', '#d7ccc8', '#e8d5b7', '#b0bec5',
]
_POS = {c: n for n, c in enumerate(PALETA)}
SIN_COLOR = ('', None, '#5f6368')


def _nombre_natural(nombre):
    return [int(t) if t.isdigit() else t.lower()
            for t in re.split(r'(\d+)', nombre or '')]


def clave_color(item):
    color = (item.get('color') or '').strip().lower()
    if color in SIN_COLOR:
        grupo = len(PALETA) + 1          # sin color: al final
    else:
        grupo = _POS.get(color, len(PALETA))   # color fuera de la paleta: antes de «sin color»
    return (grupo, color, _nombre_natural(item.get('nombre')))
