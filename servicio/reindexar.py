# -*- coding: utf-8 -*-
"""
Reconstruye el índice de búsqueda del Almacén leyendo el disco.
===============================================================
El índice se mantiene solo con cada operación (subir, mover, borrar…). Este
comando existe para el poblado inicial, para reparar si algo se desfasó y para
la pasada nocturna de seguridad.

Uso:
  python3 reindexar.py            # todos los usuarios con datos en el almacén
  python3 reindexar.py 104        # solo ese usuario

Autoría: Equipo de Tecnología Maquita — 2026-07-22
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config_almacen import raiz_datos                      # noqa: E402
from indice_busqueda import (asegurar_esquema_indice, reindexar_unidades,
                             reindexar_usuario)  # noqa: E402


def usuarios_con_datos():
    """Ids de usuario que tienen carpeta propia en la raíz de datos."""
    raiz = raiz_datos()
    if not os.path.isdir(raiz):
        return []
    return sorted(int(n) for n in os.listdir(raiz) if n.isdigit())


def main():
    asegurar_esquema_indice()
    objetivos = [int(sys.argv[1])] if len(sys.argv) > 1 else usuarios_con_datos()
    if not objetivos:
        print('No hay usuarios con datos en el almacén.')
        return 0
    total = 0
    for usuario_id in objetivos:
        cuantos = reindexar_usuario(usuario_id)
        total += cuantos
        print('usuario %-6s → %6d elementos indexados' % (usuario_id, cuantos))
    # Unidades compartidas (12/08/2026): solo en la pasada completa.
    if len(sys.argv) <= 1:
        cuantos = reindexar_unidades()
        total += cuantos
        print('unidades compartidas → %6d elementos indexados' % cuantos)
    print('-' * 42)
    print('Total: %d elementos en %d usuario(s).' % (total, len(objetivos)))
    return 0


if __name__ == '__main__':
    sys.exit(main())
