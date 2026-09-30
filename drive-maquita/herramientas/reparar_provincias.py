# -*- coding: utf-8 -*-
"""Repasa las pestañas de provincia y repone las fórmulas que falten.

Al escribir 45.000 celdas de una vez, el editor puede saltarse alguna (el
21/09/2026 se quedó sin fórmula la columna «Provincia» de CHIMBORAZO). Esto lo
comprueba columna a columna y escribe solo lo que falta.

Uso:  python reparar_provincias.py <usuario> <ruta> [--aplicar]
"""
import importlib.util
import io
import os
import secrets
import sys
import time

sys.path.insert(0, '/home/sistemas/almacen-maquita/servicio')

import openpyxl
import requests

import nucleo_archivos as nucleo
from api_onlyoffice import firmar_jwt, url_interna_ds, _reescribir_url_interna
from config_almacen import URL_PUBLICA
from encuestas_hoja_recalculo import CARPETA_SCRIPTS, URL_SCRIPTS

GUION = '/home/sistemas/almacen-maquita/herramientas/formulas_provincias.py'
spec = importlib.util.spec_from_file_location('fp', GUION)
fp = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fp)

USUARIO = int(sys.argv[1])
RUTA = sys.argv[2]
APLICAR = '--aplicar' in sys.argv
PRIMERA = fp.FILA_CABECERAS_PESTANA + 1
FIN = fp.FILA_CABECERAS_PESTANA + fp.FILAS


def formula_de(columna_base, fila):
    origen = "'%s'!%s$%d:%s$%d" % (fp.HOJA_BASE, fp.letra(columna_base),
                                   fp.FILA_CABECERAS_BASE + 1,
                                   fp.letra(columna_base), fp.ULTIMA_BASE)
    return ('=IF($%s%d="","",IF(INDEX(%s,$%s%d)="","",INDEX(%s,$%s%d)))'
            % (fp.COL_INDICE, fila, origen, fp.COL_INDICE, fila, origen, fp.COL_INDICE, fila))


def faltantes(fisica):
    """[(pestaña, columna de la pestaña, columna de la base)] sin fórmula."""
    estructura = fp.leer_estructura(fisica)
    libro = openpyxl.load_workbook(fisica)
    pendientes = []
    for pestana, datos in estructura.items():
        hoja = libro[pestana]
        for columna, columna_base in sorted(datos['mapa'].items()):
            for fila in range(PRIMERA, FIN + 1):
                valor = hoja.cell(row=fila, column=columna).value
                if not (isinstance(valor, str) and 'INDEX' in valor):
                    pendientes.append((pestana, columna, columna_base))
                    break
    return pendientes


fisica = nucleo.ruta_fisica(USUARIO, RUTA)
pendientes = faltantes(fisica)
print('columnas sin fórmula: %d' % len(pendientes))
for pestana, columna, _ in pendientes:
    print('  %s!%s' % (pestana, fp.letra(columna)))
if not pendientes:
    sys.exit(0)

token = firmar_jwt({'u': USUARIO, 'r': RUTA, 'uso': 'descarga', 'exp': int(time.time()) + 600})
url_libro = '%s/api/almacen/onlyoffice/download?t=%s' % (URL_PUBLICA, token)
lineas = ['builder.OpenFile("%s");' % url_libro]
for pestana, columna, columna_base in pendientes:
    lineas.append('var hoja = Api.GetSheet(%s);' % fp._js(pestana))
    lineas.append('if (hoja) {')
    for fila in range(PRIMERA, FIN + 1):
        lineas.append('  hoja.GetRange("%s%d").SetValue(%s);'
                      % (fp.letra(columna), fila, fp._js(formula_de(columna_base, fila))))
    lineas.append('}')
lineas += ['Api.RecalculateAllFormulas();',
           'builder.SaveFile("xlsx", "reparado.xlsx");', 'builder.CloseFile();']

os.makedirs(CARPETA_SCRIPTS, exist_ok=True)
nombre = secrets.token_hex(16) + '.docbuilder'
camino = os.path.join(CARPETA_SCRIPTS, nombre)
open(camino, 'w', encoding='utf-8').write('\n'.join(lineas) + '\n')
os.chmod(camino, 0o644)
try:
    cuerpo = {'async': False, 'key': 'rep' + secrets.token_hex(8),
              'url': '%s%s/%s' % (URL_PUBLICA, URL_SCRIPTS, nombre)}
    cuerpo['token'] = firmar_jwt(dict(cuerpo))
    respuesta = requests.post(
        url_interna_ds().rstrip('/') + '/docbuilder', json=cuerpo, timeout=(3, 600),
        headers={'Authorization': 'Bearer ' + firmar_jwt({'payload': cuerpo})})
    urls = list((respuesta.json() or {}).get('urls', {}).values())
    if not urls:
        print('el docbuilder respondió:', respuesta.status_code, respuesta.text[:200])
        sys.exit(1)
    salida = requests.get(_reescribir_url_interna(urls[0]), timeout=(3, 120)).content
    destino = '/tmp/reconectar-ifo/reparado.xlsx'
    open(destino, 'wb').write(salida)
    print('resultado en %s (%.0f KB)' % (destino, len(salida) / 1024))
    if APLICAR:
        import sala_editor
        from api_onlyoffice import _base_documento, invalidar_cache
        dentro = sala_editor.usuarios_conectados(_base_documento(USUARIO, RUTA))
        if dentro is None or dentro:
            print('NO se aplica: el Excel está abierto (%s)' % dentro)
            sys.exit(2)
        carpeta, _, archivo = RUTA.rpartition('/')
        nucleo.subir(USUARIO, carpeta, archivo, io.BytesIO(salida))
        invalidar_cache(USUARIO, RUTA)
        print('aplicado; quedan sin fórmula: %d' % len(faltantes(fisica)))
finally:
    os.remove(camino)
