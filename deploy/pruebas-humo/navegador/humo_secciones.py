#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""T-16 · Candado de los enlaces directos a las secciones del correo (riel del cliente).
Comprueba con navegador real y UA del cliente Windows que cada URL abre SU seccion,
y que los atajos cortos redirigen bien. Uso: humo-secciones <token>"""
import sys
from playwright.sync_api import sync_playwright
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from comun import BASE, HOST, CUENTA, DESTINO, PERSONA, CONVERSACION, UID_CORREO  # noqa: E402,F401

UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/151 Safari/537.36 MaquitaTeams/0.4.42'
SECCIONES = [
    ('/webmail/tasks', ['Mi día', 'Tareas', 'Asignado a mí']),
    ('/webmail/contacts', ['Contactos', 'Todos los contactos']),
    ('/webmail/calendar', ['Agosto', 'Septiembre', 'Octubre', 'Hoy']),
    ('/webmail/files', ['Mis archivos', 'Unidades']),
]
ATAJOS = ['/tareas', '/tasks', '/contactos', '/contacts', '/calendario', '/calendar', '/archivos', '/files']
fallas = []


def check(n, ok, d=''):
    print(('[OK    ] ' if ok else '[FALLA ] ') + n + (' - ' + d if d else ''))
    if not ok:
        fallas.append(n)


def main(tok):
    with sync_playwright() as p:
        nav = p.chromium.launch(args=['--no-sandbox'])
        ctx = nav.new_context(user_agent=UA, viewport={'width': 1366, 'height': 850})
        ctx.add_cookies([{'name': 'access_token', 'value': tok, 'domain': HOST,
                          'path': '/', 'secure': True}])
        pg = ctx.new_page()
        for ruta, marcas in SECCIONES:
            pg.goto(BASE + ruta, wait_until='domcontentloaded', timeout=60000)
            pg.wait_for_timeout(4500)
            texto = pg.inner_text('body')[:1500]
            ok = pg.url.endswith(ruta) and any(m in texto for m in marcas)
            check('T-16 . %s abre su sección en modo app' % ruta, ok,
                  'url=%s' % pg.url.split('.org')[-1])
        # El aviso de correo nuevo manda /webmail/?folder=INBOX&uid=<uid>: debe abrir ESE correo.
        pg.goto(BASE + '/webmail/?folder=INBOX&uid=' + UID_CORREO, wait_until='domcontentloaded', timeout=60000)
        pg.wait_for_timeout(11000)
        con_uid = pg.inner_text('body')
        pg.goto(BASE + '/webmail/', wait_until='domcontentloaded', timeout=60000)
        pg.wait_for_timeout(9000)
        sin_uid = pg.inner_text('body')
        marca = 'Prueba T-35: adjunto para lectura sin conexion'
        check('T-16 . el enlace con uid abre ESE correo (aviso de correo nuevo)',
              marca in con_uid and marca not in sin_uid,
              'con uid=%d apariciones · sin uid=%d' % (con_uid.count(marca), sin_uid.count(marca)))

        for atajo in ATAJOS:
            pg.goto(BASE + atajo, wait_until='domcontentloaded', timeout=60000)
            pg.wait_for_timeout(2500)
            check('T-16 . el atajo %s lleva a su sección' % atajo, '/webmail/' in pg.url,
                  'destino=%s' % pg.url.split('.org')[-1])
        nav.close()
    print('\nCandado T-16 (secciones del correo): %s' %
          ('TODO OK - 0 fallas' if not fallas else '%d FALLAS -> %s' % (len(fallas), fallas)))
    return 1 if fallas else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else ''))
