#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Detalla las dependencias entre archivos que quedan en las hojas de cálculo.

Complementa a `auditar_formulas.py`, que solo cuenta. Aquí se responden las dos
preguntas que importan para la migración:

  1. ¿A DÓNDE apunta cada vínculo externo? Si apunta al disco de alguien
     (`C:\\Users\\...`, `Y:\\...`), lleva roto desde antes de la migración y no
     hay nada que recuperar. Si apuntara a un archivo del propio Drive, sí
     habría que rehacerlo.
  2. Los `#REF!` ¿son FÓRMULAS rotas o solo texto? Un `#REF!` dentro de `<f>` es
     una fórmula que ya no encuentra su destino; dentro de las cadenas
     compartidas es texto que alguien pegó y no rompe nada.

Uso:  auditar_vinculos.py <carpeta>
"""
import os
import re
import sys
import zipfile
from urllib.parse import unquote

RE_DESTINO = re.compile(rb'Target="([^"]+)"')
RE_FORMULA = re.compile(rb'<f[ >][^<]*?#REF!', re.S)
RE_FORMULA_SIMPLE = re.compile(rb'<f>[^<]*#REF!')


def destinos_externos(paquete):
    destinos = []
    for interno in paquete.namelist():
        if '/externalLinks/_rels/' in interno and interno.endswith('.rels'):
            for encontrado in RE_DESTINO.findall(paquete.read(interno)):
                destinos.append(unquote(encontrado.decode('utf-8', 'ignore')))
    return destinos


def main():
    raiz = sys.argv[1] if len(sys.argv) > 1 else '.'
    destinos_todos = {}
    formulas_rotas = []

    for carpeta, _, archivos in os.walk(raiz):
        for nombre in sorted(archivos):
            if not nombre.lower().endswith(('.xlsx', '.xlsm')):
                continue
            ruta = os.path.join(carpeta, nombre)
            relativa = os.path.relpath(ruta, raiz)
            try:
                with zipfile.ZipFile(ruta) as paquete:
                    for destino in destinos_externos(paquete):
                        destinos_todos.setdefault(destino, []).append(relativa)
                    en_formula = 0
                    for interno in paquete.namelist():
                        if interno.startswith('xl/worksheets/'):
                            datos = paquete.read(interno)
                            en_formula += len(RE_FORMULA.findall(datos))
                    if en_formula:
                        formulas_rotas.append((relativa, en_formula))
            except (zipfile.BadZipFile, OSError):
                continue

    print('=== 1. A dónde apuntan los vínculos externos ===')
    if not destinos_todos:
        print('  (ninguno)')
    for destino, archivos in sorted(destinos_todos.items(), key=lambda p: -len(p[1])):
        clase = 'DISCO DE ALGUIEN (roto)' if re.search(
            r'^(file:|[A-Za-z]:|/Users/|\\\\)', destino) else 'REVISAR'
        print('  [%s] %s' % (clase, destino[:96]))
        for archivo in archivos[:3]:
            print('        ← %s' % archivo[:92])

    print('\n=== 2. #REF! dentro de FÓRMULAS (no texto) ===')
    if not formulas_rotas:
        print('  ninguno: los #REF! encontrados son texto, no fórmulas')
    for relativa, cuantos in sorted(formulas_rotas, key=lambda p: -p[1]):
        print('  %-84s %d fórmula(s)' % (relativa[:84], cuantos))


if __name__ == '__main__':
    main()
