#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""QA: assets ESTATICOS referenciados por la UI del Drive vs. los que existen.

Caza la familia de fallos #1/#6/#10 (una plantilla/CSS referencia un asset que no se sirve).
Revisa url_for('static', ...), href/src=/almacen-static/... en plantillas, y url(...) en CSS.
Sale != 0 si falta algun asset LOCAL. No arranca nada; es un chequeo de ficheros.
"""
import glob
import os
import re
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))   # .../almacen
SERV = os.path.join(BASE, 'servicio')
STATIC = os.path.join(SERV, 'estaticos')                            # servido en /almacen-static/

faltan = set()
refs = 0


def _dinamico(x):
    return ('{{' in x) or ('{%' in x) or ('${' in x)


# 1) plantillas HTML
for f in glob.glob(os.path.join(SERV, 'plantillas', '**', '*.html'), recursive=True):
    if '.bak' in f:
        continue
    t = open(f, encoding='utf-8', errors='ignore').read()
    base = os.path.basename(f)
    for m in re.findall(r"url_for\('static',\s*filename='([^']+)'\)", t):
        m = m.split('?')[0].split('#')[0]
        if _dinamico(m):
            continue
        refs += 1
        if not os.path.exists(os.path.join(STATIC, m)):
            faltan.add('%s -> static/%s' % (base, m))
    for m in re.findall(r'(?:href|src)=["\'](/almacen-static/[^"\']+)["\']', t):
        if _dinamico(m):
            continue
        p = os.path.join(STATIC, m[len('/almacen-static/'):].split('?')[0].split('#')[0])
        refs += 1
        if not os.path.exists(p):
            faltan.add('%s -> %s' % (base, m))

# 2) CSS: url(...) relativo al propio CSS o /almacen-static/
for f in glob.glob(os.path.join(STATIC, '**', '*.css'), recursive=True):
    if '.bak' in f:
        continue
    t = open(f, encoding='utf-8', errors='ignore').read()
    d = os.path.dirname(f)
    for m in re.findall(r'url\(([^)]+)\)', t):
        m = m.strip().strip('\'"').split('?')[0].split('#')[0]
        if m.startswith(('http', 'data:', '//')) or _dinamico(m):
            continue
        if m.startswith('/almacen-static/'):
            p = os.path.join(STATIC, m[len('/almacen-static/'):])
        elif m.startswith('/'):
            continue   # ruta absoluta de otro servicio: no verificable aqui
        else:
            p = os.path.normpath(os.path.join(d, m))
        refs += 1
        if not os.path.exists(p):
            faltan.add('%s -> %s' % (os.path.relpath(f, STATIC), m))

if faltan:
    print('ASSETS FALTANTES (%d):' % len(faltan))
    for x in sorted(faltan):
        print('  -', x)
    sys.exit(1)
print('OK: %d assets referenciados, todos servidos.' % refs)
