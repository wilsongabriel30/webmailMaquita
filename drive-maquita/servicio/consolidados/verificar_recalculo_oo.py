#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Comprueba que recalcular un consolidado con OnlyOffice no estropea nada.

Wilson pidió verificar bien antes de publicar. El Document Server reescribe el libro
entero para calcular las fórmulas, así que hay que confirmar, sobre COPIAS, que:

  1. no desaparece ni cambia ningún dato;
  2. las fórmulas siguen siendo las mismas;
  3. los totales que estaban en blanco vuelven, y coinciden con los de Google;
  4. se conserva el formato que se ve: hojas, celdas combinadas, formato
     condicional, validaciones, anchos de columna e imágenes;
  5. el archivo resultante es un zip íntegro (abre y se descarga entero).

No toca ningún archivo de la unidad: trabaja en copias dentro de /tmp.
"""
import os
import shutil
import sys
import zipfile

import openpyxl

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from recalcular_onlyoffice import recalcular  # noqa: E402

BASE = ('/mnt/almacen/_unidades/12/archivos/Mi unidad de Google/'
        'Mapa de inversiones/')
CRUDO = '/mnt/almacen/_sincronizacion-asc/crudo/mi-unidad/Mapa de inversiones/'
TRABAJO = '/tmp/verificacion-recalculo-oo'

ARCHIVOS = [
    'Mapa general de inversiones 2026.xlsx',
    'Mapa general Ejec. Técnica 2026.xlsx',
    'Mapa general de inversiones 2025.xlsx',
    'Respaldo mapa inversiones.xlsx',
]


def leer(ruta, con_valores):
    libro = openpyxl.load_workbook(ruta, data_only=con_valores)
    datos, formato = {}, {}
    try:
        for nombre in libro.sheetnames:
            pagina = libro[nombre]
            for fila in pagina.iter_rows():
                for celda in fila:
                    if celda.value is not None:
                        datos[(nombre, celda.row, celda.column)] = celda.value
            formato[nombre] = {
                'combinadas': len(pagina.merged_cells.ranges),
                'condicional': sum(1 for _ in pagina.conditional_formatting),
                'validaciones': len(pagina.data_validations.dataValidation),
                'columnas': len(pagina.column_dimensions),
                'imagenes': len(getattr(pagina, '_images', [])),
            }
        return datos, formato, list(libro.sheetnames)
    finally:
        libro.close()


def comparar(nombre):
    print('\n' + '=' * 74)
    print('== %s' % nombre)
    original = os.path.join(TRABAJO, 'orig-' + nombre)
    recalculado = os.path.join(TRABAJO, 'recalc-' + nombre)
    shutil.copy2(BASE + nombre, original)

    ok, motivo = recalcular(original, recalculado)
    if not ok:
        print('   NO SE PUDO RECALCULAR: %s' % motivo)
        return False

    # 5. integridad
    try:
        with zipfile.ZipFile(recalculado) as paquete:
            if paquete.testzip() is not None:
                print('   ARCHIVO DAÑADO')
                return False
    except Exception as excepcion:
        print('   ARCHIVO DAÑADO: %s' % excepcion)
        return False

    val_antes, fmt_antes, hojas_antes = leer(original, True)
    val_despues, fmt_despues, hojas_despues = leer(recalculado, True)
    for_antes, _, _ = leer(original, False)
    for_despues, _, _ = leer(recalculado, False)

    # 1. datos
    perdidos = [k for k in val_antes if k not in val_despues]
    cambiados = [k for k in val_antes
                 if k in val_despues and val_antes[k] != val_despues[k]]
    recuperados = [k for k in val_despues if k not in val_antes]

    # 2. fórmulas
    formulas_antes = {k: v for k, v in for_antes.items()
                      if isinstance(v, str) and v.startswith('=')}
    formulas_despues = {k: v for k, v in for_despues.items()
                        if isinstance(v, str) and v.startswith('=')}
    formulas_perdidas = [k for k in formulas_antes if k not in formulas_despues]

    print('   hojas            : %d -> %d  %s'
          % (len(hojas_antes), len(hojas_despues),
             'OK' if hojas_antes == hojas_despues else 'CAMBIARON'))
    print('   valores          : %d -> %d' % (len(val_antes), len(val_despues)))
    print('     perdidos       : %d' % len(perdidos))
    print('     cambiados      : %d' % len(cambiados))
    print('     RECUPERADOS    : %d  (totales que estaban en blanco)'
          % len(recuperados))
    print('   fórmulas         : %d -> %d   perdidas: %d'
          % (len(formulas_antes), len(formulas_despues), len(formulas_perdidas)))

    for hoja in hojas_antes:
        a, d = fmt_antes.get(hoja, {}), fmt_despues.get(hoja, {})
        difs = [k for k in a if a[k] != d.get(k)]
        if difs:
            print('   formato hoja %-18s difiere en: %s'
                  % (hoja[:18], ', '.join('%s %s->%s' % (k, a[k], d.get(k))
                                          for k in difs)))

    for clave in cambiados[:4]:
        print('     CAMBIO %s fila %s col %s: %r -> %r'
              % (clave[0], clave[1], clave[2],
                 val_antes[clave], val_despues[clave]))
    for clave in perdidos[:4]:
        print('     PERDIDO %s fila %s col %s: %r'
              % (clave[0], clave[1], clave[2], val_antes[clave]))

    # 3. ¿los totales coinciden con los de Google?
    if os.path.exists(CRUDO + nombre):
        val_google, _, _ = leer(CRUDO + nombre, True)
        comunes = [k for k in recuperados if k in val_google]
        iguales = sum(1 for k in comunes
                      if _parecidos(val_google[k], val_despues[k]))
        print('   de los recuperados, %d estaban en Google y %d coinciden'
              % (len(comunes), iguales))

    return not (perdidos or cambiados or formulas_perdidas)


def _parecidos(uno, otro):
    if isinstance(uno, float) and isinstance(otro, float):
        return abs(uno - otro) < max(abs(uno), abs(otro), 1) * 1e-9
    return uno == otro


def main():
    os.makedirs(TRABAJO, exist_ok=True)
    resultados = {}
    for nombre in ARCHIVOS:
        if not os.path.exists(BASE + nombre):
            print('no existe: %s' % nombre)
            continue
        try:
            resultados[nombre] = comparar(nombre)
        except Exception as excepcion:
            print('   ERROR: %s' % excepcion)
            resultados[nombre] = False

    print('\n' + '=' * 74)
    print('VEREDICTO')
    for nombre, ok in resultados.items():
        print('  %-46s %s' % (nombre[:46],
                              'SIN PÉRDIDAS' if ok else 'REVISAR'))
    print('\n(los archivos de prueba quedan en %s)' % TRABAJO)


if __name__ == '__main__':
    main()
