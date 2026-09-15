#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Barre TODAS las hojas de cálculo buscando dependencias entre archivos.

Motivo (Wilson, 09/09/2026): el consolidado que se revisó era «un ejemplo nada
más»; nadie había mirado el resto. Este barrido dice, archivo por archivo, qué
hojas dependen de otras y cuáles de esas dependencias están HOY rotas.

Qué busca, leyendo el .xlsx como zip (rápido, sin abrir el libro):
  · __xludf.DUMMYFUNCTION  → fórmula de Google que no sobrevivió a la exportación
  · IMPORTRANGE / QUERY    → funciones de Google que no existen en OnlyOffice
  · xl/externalLinks/      → vínculos a otros archivos al estilo Excel
  · #REF! #NAME? #VALUE!   → errores ya visibles en las celdas

Uso:  auditar_formulas.py <carpeta> [carpeta...]
"""
import os
import re
import sys
import zipfile

PATRONES = {
    'google_muerta': re.compile(rb'__xludf', re.I),
    'importrange': re.compile(rb'IMPORTRANGE', re.I),
    'query': re.compile(rb'\bQUERY\(', re.I),
    'ref_rota': re.compile(rb'#REF!'),
    'nombre_desconocido': re.compile(rb'#NAME\?|#\xc2\xbfNOMBRE\?'),
    'valor_error': re.compile(rb'#VALUE!|#\xc2\xa1VALOR!'),
}


def revisar(ruta):
    """Devuelve dict con los hallazgos del archivo, o None si no hay ninguno."""
    hallazgos = {}
    try:
        with zipfile.ZipFile(ruta) as paquete:
            nombres = paquete.namelist()
            enlaces = [n for n in nombres if n.startswith('xl/externalLinks/externalLink')
                       and n.endswith('.xml')]
            if enlaces:
                hallazgos['vinculos_externos'] = len(enlaces)
            for interno in nombres:
                if not (interno.startswith('xl/worksheets/')
                        or interno.startswith('xl/sharedStrings')):
                    continue
                datos = paquete.read(interno)
                for clave, patron in PATRONES.items():
                    encontrados = len(patron.findall(datos))
                    if encontrados:
                        hallazgos[clave] = hallazgos.get(clave, 0) + encontrados
    except (zipfile.BadZipFile, OSError) as excepcion:
        return {'ilegible': str(excepcion)[:60]}
    return hallazgos or None


def main():
    if len(sys.argv) < 2:
        sys.exit('uso: auditar_formulas.py <carpeta> [carpeta...]')

    revisados = 0
    con_hallazgos = []
    for raiz in sys.argv[1:]:
        for carpeta, _, archivos in os.walk(raiz):
            for nombre in sorted(archivos):
                if not nombre.lower().endswith(('.xlsx', '.xlsm')):
                    continue
                ruta = os.path.join(carpeta, nombre)
                revisados += 1
                hallazgos = revisar(ruta)
                if hallazgos:
                    con_hallazgos.append((os.path.relpath(ruta, raiz), hallazgos))

    print('hojas de cálculo revisadas: %d' % revisados)
    print('con dependencias o errores : %d\n' % len(con_hallazgos))

    resumen = {}
    for _, hallazgos in con_hallazgos:
        for clave in hallazgos:
            resumen[clave] = resumen.get(clave, 0) + 1
    print('--- cuántos archivos por tipo de hallazgo ---')
    for clave, cuantos in sorted(resumen.items(), key=lambda par: -par[1]):
        print('  %-22s %d' % (clave, cuantos))

    print('\n--- detalle ---')
    for relativa, hallazgos in con_hallazgos:
        detalle = ' '.join('%s=%s' % (k, v) for k, v in sorted(hallazgos.items()))
        print('  %-88s %s' % (relativa[:88], detalle))


if __name__ == '__main__':
    main()
