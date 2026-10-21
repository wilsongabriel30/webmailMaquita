#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""T-44 · Candado: la conversación directa PINTA en modo app, y si la ventana llega
sin sesión, o bien la recupera con el token del enlace, o avisa con claridad.
Uso: humo-conversacion <token>"""
import sys
from playwright.sync_api import sync_playwright
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from comun import BASE, HOST, CUENTA, DESTINO, PERSONA, CONVERSACION, UID_CORREO  # noqa: E402,F401
UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/151 Safari/537.36 MaquitaTeams/0.4.46'
fallas = []
def check(n, ok, d=''):
    print(('[OK    ] ' if ok else '[FALLA ] ') + n + (' - ' + d if d else ''))
    if not ok: fallas.append(n)

def estado(pg):
    return pg.evaluate("""() => {
        const a = document.getElementById('chatActiveArea');
        const r = a ? a.getBoundingClientRect() : null;
        return {pinta: !!(r && r.height > 100), mensajes: document.querySelectorAll('#chatMessages > *').length,
                texto: document.body.innerText.trim().length};
    }""")

def main(tok):
    with sync_playwright() as p:
        nav = p.chromium.launch(args=['--no-sandbox'])
        # 1) con sesión, en la ventana pequeña de la app
        for ancho, alto, etiqueta in [(360, 640, 'ventana pequeña'), (1100, 800, 'ventana normal')]:
            ctx = nav.new_context(user_agent=UA, viewport={'width': ancho, 'height': alto})
            ctx.add_cookies([{'name': 'access_token', 'value': tok, 'domain': HOST, 'path': '/', 'secure': True}])
            pg = ctx.new_page()
            pg.goto(BASE + '/chat/conversation/' + CONVERSACION, wait_until='domcontentloaded', timeout=60000)
            pg.wait_for_timeout(12000)
            e = estado(pg)
            check('T-44 . la conversación PINTA en %s' % etiqueta, e['pinta'] and e['mensajes'] > 0,
                  'mensajes=%d texto=%d' % (e['mensajes'], e['texto']))
            ctx.close()
        # 2) ventana NUEVA sin cookie, pero con el token en el enlace (notificación)
        ctx = nav.new_context(user_agent=UA, viewport={'width': 360, 'height': 640})
        pg = ctx.new_page()
        pg.goto(BASE + '/chat/conversation/' + CONVERSACION + '?token=' + tok, wait_until='domcontentloaded', timeout=60000)
        pg.wait_for_timeout(12000)
        e = estado(pg)
        check('T-44 . con el token en el enlace, la ventana nueva abre la conversación',
              e['pinta'] and e['mensajes'] > 0, 'mensajes=%d url=%s' % (e['mensajes'], pg.url.split('.org')[-1]))
        check('T-44 . el token no queda en la barra de direcciones', 'token=' not in pg.url, pg.url.split('.org')[-1])
        ctx.close()
        # 3) sin sesión ni token: aviso entendible, nunca un lienzo mudo
        ctx = nav.new_context(user_agent=UA, viewport={'width': 360, 'height': 640})
        pg = ctx.new_page()
        pg.goto(BASE + '/chat/conversation/' + CONVERSACION, wait_until='domcontentloaded', timeout=60000)
        pg.wait_for_timeout(2500)
        t = pg.inner_text('body')
        botones = pg.evaluate("() => Array.from(document.querySelectorAll('a')).map(a => a.innerText.trim())")
        check('T-44 . sin sesión: explica y ofrece salida (reintentar / iniciar sesión)',
              'sesion' in t.lower() and any('eintentar' in b for b in botones), 'botones=%s' % botones)
        nav.close()
    print('\nCandado T-44 (conversación directa): %s' %
          ('TODO OK - 0 fallas' if not fallas else '%d FALLAS -> %s' % (len(fallas), fallas)))
    return 1 if fallas else 0

if __name__ == '__main__':
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else ''))
