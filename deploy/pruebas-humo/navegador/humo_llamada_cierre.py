#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""T-26 · Candado: la ventana de llamada abre UNA sola vez y se cierra sola al terminar.
Se comprueba sobre el código servido (no hace falta llamar de verdad a nadie):
  · la llamada 1a1 cierra al colgar, cuando cuelga el otro, al rechazar y sin respuesta;
  · la conferencia cierra al salir y cuando te quedas solo;
  · el embudo del chat abre una sola ventana (sin window.open + location a la vez).
Uso: humo-llamada-cierre <token>"""
import sys
from playwright.sync_api import sync_playwright
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from comun import BASE, HOST, CUENTA, DESTINO, PERSONA, CONVERSACION, UID_CORREO  # noqa: E402,F401
UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/151 MaquitaTeams/0.4.47'
fallas = []
def check(n, ok, d=''):
    print(('[OK    ] ' if ok else '[FALLA ] ') + n + (' - ' + d if d else ''))
    if not ok: fallas.append(n)

def main(tok):
    with sync_playwright() as p:
        nav = p.chromium.launch(args=['--no-sandbox'])
        ctx = nav.new_context(user_agent=UA, viewport={'width': 1000, 'height': 800})
        ctx.set_default_timeout(20000)
        ctx.add_cookies([{'name': 'access_token', 'value': tok, 'domain': HOST, 'path': '/', 'secure': True}])
        pg = ctx.new_page()

        pg.goto(BASE + '/chat/llamada?role=caller&tipo=audio&peer=1&name=Prueba',
                wait_until='domcontentloaded', timeout=45000)
        pg.wait_for_timeout(4000)
        fuente = pg.content()
        check('T-26 . la llamada cierra la ventana al colgar', 'cerrarVistaLlamada' in fuente, 'función presente')
        for caso, marca in [('cuando cuelga el otro', "socket.on('call_hangup'"),
                            ('cuando rechazan', "socket.on('call_rejected'"),
                            ('cuando no contestan', 'ringTimeout')]:
            check('T-26 . la llamada termina %s' % caso, marca in fuente, 'manejado')

        pg.goto(BASE + '/chat/conferencia?role=guest&room=humo&name=Prueba',
                wait_until='domcontentloaded', timeout=45000)
        pg.wait_for_timeout(4000)
        conf = pg.content()
        check('T-26 . la conferencia cierra al salir', 'cerrarVistaLlamada' in conf, 'función presente')
        check('T-26 . la conferencia cierra sola si te quedas solo',
              'cierreSiVacia' in conf and 'temporizadorVacia' in conf, 'cierre por sala vacía')

        pg.goto(BASE + '/chat/', wait_until='domcontentloaded', timeout=45000)
        pg.wait_for_timeout(6000)
        js = pg.evaluate("""async () => {
            const r = await fetch('/static/js/chat-llamadas.js?v=20260831-t15');
            return await r.text();
        }""")
        aperturas = js.count('window.open(')
        navega = ('location.href' in js) or ('location.assign' in js)
        check('T-26 . el chat abre la llamada por un solo camino (sin doble ventana)',
              aperturas == 1 and not navega, 'window.open=%d · navegación directa=%s' % (aperturas, navega))
        nav.close()
    print('\nCandado T-26 (ventana de llamada): %s' %
          ('TODO OK - 0 fallas' if not fallas else '%d FALLAS -> %s' % (len(fallas), fallas)))
    return 1 if fallas else 0

if __name__ == '__main__':
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else ''))
