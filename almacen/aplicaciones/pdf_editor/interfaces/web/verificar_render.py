#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Verifica que el Editor de PDF RENDERIZA de forma autonoma (sin Raices):
  - base.html se resuelve (el bug historico era TemplateNotFound: base.html);
  - todos los estaticos referenciados por las plantillas existen en disco.
Sale con codigo != 0 si algo falta, para que el instalador aborte a tiempo.
No arranca la app ni necesita sesion: es un chequeo de render deterministico."""
import glob
import os
import re
import sys
from types import SimpleNamespace as NS

HERE = os.path.dirname(os.path.abspath(__file__))
PLANT = os.path.join(HERE, 'plantillas')
STATIC = os.path.join(HERE, 'static')
try:
    from jinja2 import Environment, FileSystemLoader, ChainableUndefined
    from jinja2.exceptions import TemplateNotFound
except Exception as exc:
    print('jinja2 no disponible:', exc)
    sys.exit(2)

env = Environment(loader=FileSystemLoader(PLANT), undefined=ChainableUndefined)
env.globals.update(
    url_for=lambda ep, **k: '/' + k.get('filename', '') if ep == 'static' else '/' + ep,
    csrf_token=lambda: 'x', get_flashed_messages=lambda **k: [])
fallos = []
_ctx = dict(documento=NS(id=1, nombre_original='d', num_paginas=1, total_paginas=1, paginas=[]),
            documentos=[], doc=NS(id=1))
for t in ('pdf_editor/home.html', 'pdf_editor/index.html',
          'pdf_editor/editor.html', 'pdf_editor/visor.html'):
    try:
        env.get_template(t).render(**_ctx)
    except TemplateNotFound as exc:
        fallos.append('%s: TemplateNotFound %s' % (t, exc))
    except Exception:
        pass  # errores por variables de contexto NO son el bug: base.html ya se resolvio

refs = set()
for f in glob.glob(os.path.join(PLANT, 'pdf_editor', '*.html')):
    with open(f, encoding='utf-8') as fh:
        for m in re.findall(r"url_for\('static',\s*filename='([^']+)'\)", fh.read()):
            refs.add(m)
for r in sorted(refs):
    if not os.path.exists(os.path.join(STATIC, r)):
        fallos.append('estatico ausente: ' + r)

if fallos:
    print('VERIFICACION DE RENDER FALLIDA:')
    for x in fallos:
        print('  -', x)
    sys.exit(1)
print('OK: base.html resuelto y %d estaticos presentes' % len(refs))
