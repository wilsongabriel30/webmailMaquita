# -*- coding: utf-8 -*-
"""
Trabajador del índice de CONTENIDO del Almacén (extrae el texto de los documentos).
==================================================================================
Corre en segundo plano: el usuario nunca espera por esto.

Uso:
  python3 indexar_contenido.py                # encola lo que falte y procesa la cola rápida
  python3 indexar_contenido.py --ocr          # procesa los escaneados (lento, pasada aparte)
  python3 indexar_contenido.py --usuario 104  # limita el encolado a un usuario
  python3 indexar_contenido.py --lote 200     # cuántos documentos por corrida
  python3 indexar_contenido.py --estado       # solo muestra cómo va

Autoría: Equipo de Tecnología Maquita — 2026-07-22
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from indice_contenido import (asegurar_esquema_contenido, encolar_faltantes,   # noqa: E402
                              estado_indice, procesar_pendientes)


def _argumento(nombre, por_defecto=None):
    if nombre in sys.argv:
        posicion = sys.argv.index(nombre) + 1
        if posicion < len(sys.argv):
            return sys.argv[posicion]
    return por_defecto


def main():
    asegurar_esquema_contenido()

    if '--estado' in sys.argv:
        for fila in estado_indice():
            print('%-16s %6d' % (fila['estado'], fila['cuantos']))
        return 0

    con_ocr = '--ocr' in sys.argv
    lote = int(_argumento('--lote', 60 if not con_ocr else 15))
    usuario = _argumento('--usuario')

    if not con_ocr:
        nuevos = encolar_faltantes(int(usuario) if usuario else None)
        if nuevos:
            print('Encolados %d documentos nuevos.' % nuevos)

    resumen = procesar_pendientes(limite=lote, con_ocr=con_ocr)
    print('Procesados — con texto: %(listos)d · sin texto: %(sin_texto)d · '
          'para OCR: %(para_ocr)d · errores: %(errores)d' % resumen)
    return 0


if __name__ == '__main__':
    sys.exit(main())
