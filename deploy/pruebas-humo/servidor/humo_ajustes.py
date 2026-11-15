#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Candado de AJUSTES: guardar las preferencias funciona.

Una columna nueva de user_preferences sin su migración hace que guardar CUALQUIER ajuste (firma,
respuesta automática, panel de lectura) devuelva 500, y el validador de despliegue no lo ve
(informe de Andes, 15/11/2026: `acuse_lectura`). Esta prueba lee las preferencias de la cuenta de
pruebas y las vuelve a guardar tal cual: no cambia nada y falla si el guardado no responde 200.

Uso: humo-ajustes [cuenta]
"""
import json
import os
import sys
import urllib.error
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from comun import BASE, CUENTA  # noqa: E402

UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/151 MaquitaHumo/1'
fallas = []


def check(nombre, ok, detalle=''):
    print(('[OK    ] ' if ok else '[FALLA ] ') + nombre + (' - ' + detalle if detalle else ''))
    if not ok:
        fallas.append(nombre)


def token(correo):
    sys.path.insert(0, '/opt/maquita-webmail/backend')
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from sesion_prueba import abrir
    t = abrir(correo)
    if not t:
        raise SystemExit('no se pudo abrir la sesion de pruebas de %s' % correo)
    return t


def api(tok, metodo, ruta, cuerpo=None):
    datos = json.dumps(cuerpo).encode() if cuerpo is not None else None
    r = urllib.request.Request(BASE + ruta, data=datos, method=metodo)
    r.add_header('User-Agent', UA)
    r.add_header('Cookie', 'access_token=' + tok)
    if datos:
        r.add_header('Content-Type', 'application/json')
    try:
        resp = urllib.request.urlopen(r, timeout=25)
        texto = resp.read().decode('utf-8', 'ignore')
        return resp.status, (json.loads(texto) if texto.strip() else None)
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode('utf-8', 'ignore')[:200]


def main(cuenta=CUENTA):
    tok = os.environ.get('HUMO_TOKEN') or token(cuenta)
    est, actuales = api(tok, 'GET', '/api/settings')
    check('Ajustes . se leen las preferencias', est == 200 and isinstance(actuales, dict), 'HTTP %s' % est)
    if est != 200 or not isinstance(actuales, dict):
        return 1
    # Se guarda un solo campo con el valor que ya tiene: el servidor conserva el resto.
    panel = actuales.get('reading_pane') or 'right'
    est, resp = api(tok, 'PUT', '/api/settings', {'reading_pane': panel})
    check('Ajustes . guardar las preferencias responde 200', est == 200,
          'HTTP %s %s' % (est, resp if est != 200 else ''))
    est, despues = api(tok, 'GET', '/api/settings')
    iguales = est == 200 and isinstance(despues, dict) and all(
        despues.get(k) == v for k, v in actuales.items() if k not in ('updated_at',))
    check('Ajustes . nada cambio al guardar lo mismo', iguales)
    print('\nCandado de ajustes: %s' % ('TODO OK - 0 fallas' if not fallas else '%d FALLAS -> %s' % (len(fallas), fallas)))
    return 1 if fallas else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else CUENTA))
