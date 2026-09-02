#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""QA: valida que las PERILLAS de configuracion del Drive REALMENTE lean config_kv
(y no devuelvan siempre el default por un fallo silencioso, como el #13).

Para cada perilla: guarda su valor, setea uno de PRUEBA, llama la funcion y comprueba que
lo refleja; luego RESTAURA el valor original. Sale != 0 si alguna no lee su config.
Complementa a verificar_assets.py (que valida la plantilla): esto valida la FUNCION.
Requiere el entorno del Almacen (carga .env si esta presente).
"""
import os
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))   # .../almacen
_envf = os.path.join(BASE, '.env')
if os.path.exists(_envf):
    for _l in open(_envf, encoding='utf-8'):
        _l = _l.strip()
        if _l and not _l.startswith('#') and '=' in _l:
            _k, _v = _l.split('=', 1)
            os.environ.setdefault(_k.strip(), _v.strip())
sys.path.insert(0, os.path.join(BASE, 'servicio'))

import almacen_bd as db          # noqa: E402
import config_almacen as cfg     # noqa: E402

# (clave en config_kv, funcion que la lee, valor de prueba, normalizador del resultado)
PERILLAS = [
    ('drive_name', cfg.drive_name, 'QA-PERILLA-DRIVE', lambda x: x),
]

fallos = []
for clave, fn, prueba, norm in PERILLAS:
    prev = db.consultar("SELECT valor FROM config_kv WHERE clave = %s", (clave,))
    prev_val = prev[0]['valor'] if prev else None
    try:
        db.ejecutar("INSERT INTO config_kv (clave, valor) VALUES (%s, %s) "
                    "ON CONFLICT (clave) DO UPDATE SET valor = EXCLUDED.valor", (clave, prueba))
        got = norm(fn())
        if got != prueba:
            fallos.append("%s: se seteo '%s' pero la funcion devolvio '%s' "
                          "(no lee config_kv o lo traga en silencio)" % (clave, prueba, got))
    except Exception as exc:
        fallos.append("%s: excepcion al probar: %s" % (clave, exc))
    finally:
        if prev_val is None:
            db.ejecutar("DELETE FROM config_kv WHERE clave = %s", (clave,))
        else:
            db.ejecutar("UPDATE config_kv SET valor = %s WHERE clave = %s", (prev_val, clave))

if fallos:
    print('PERILLAS QUE NO LEEN SU CONFIG:')
    for f in fallos:
        print('  -', f)
    sys.exit(1)
print('OK: %d perilla(s) leen config_kv correctamente.' % len(PERILLAS))
