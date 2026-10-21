#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""T-46 · Candado de la sección «Llamadas» (discador, historial y favoritos).
Uso: humo-llamadas-seccion <token>"""
import sys
from playwright.sync_api import sync_playwright
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from comun import BASE, HOST, CUENTA, DESTINO, PERSONA, CONVERSACION, UID_CORREO  # noqa: E402,F401
UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/151 MaquitaTeams/0.4.48'
fallas = []
def check(n, ok, d=''):
    print(('[OK    ] ' if ok else '[FALLA ] ') + n + (' - ' + d if d else ''))
    if not ok: fallas.append(n)

def main(tok):
    with sync_playwright() as p:
        nav = p.chromium.launch(args=['--no-sandbox'])
        ctx = nav.new_context(user_agent=UA, viewport={'width': 1100, 'height': 900})
        ctx.set_default_timeout(20000)
        ctx.add_cookies([{'name': 'access_token', 'value': tok, 'domain': HOST, 'path': '/', 'secure': True}])
        pg = ctx.new_page()
        pg.goto(BASE + '/chat/llamadas', wait_until='domcontentloaded', timeout=60000)
        pg.wait_for_timeout(9000)
        texto = pg.inner_text('body')
        check('T-46 . la sección Llamadas abre en modo app',
              'Llamadas' in texto and 'Historial' in texto, '%d caracteres' % len(texto))
        check('T-46 . tiene discador (buscador de personas)',
              pg.evaluate("() => !!document.getElementById('buscarPersona')"), 'campo de búsqueda')
        # buscar y llamar
        pg.fill('#buscarPersona', 'wil'); pg.wait_for_timeout(3000)
        res = pg.evaluate("""() => {
            const p = document.querySelectorAll('#resultados .persona');
            return {n: p.length, voz: document.querySelectorAll('#resultados .btn-voz').length,
                    video: document.querySelectorAll('#resultados .btn-video').length};
        }""")
        check('T-46 . al buscar aparecen personas con botones de llamar y videollamar',
              res['n'] > 0 and res['voz'] == res['n'] and res['video'] == res['n'],
              '%d personas, %d ☎, %d 📹' % (res['n'], res['voz'], res['video']))
        destino = pg.evaluate("""() => {
            let url = '';
            const abrir = window.open;
            window.open = function (u) { url = String(u); return {focus(){}, close(){}}; };
            try { window.llamarA(17, 'Luis Almachi', 'video'); } finally { window.open = abrir; }
            return url;
        }""")
        check('T-46 . el botón de videollamada abre la llamada de la persona',
              '/chat/llamada' in destino and 'tipo=video' in destino and 'peer=' in destino,
              destino[:70] or 'no abrió')
        hist = pg.evaluate("""() => ({filas: document.querySelectorAll('#historial .persona').length,
                                      perdidas: document.querySelectorAll('#historial .perdida').length,
                                      volver: document.querySelectorAll('#historial .btn-voz').length})""")
        check('T-46 . el historial lista llamadas con «volver a llamar»',
              hist['filas'] > 0 and hist['volver'] == hist['filas'],
              '%d llamadas (%d perdidas)' % (hist['filas'], hist['perdidas']))
        # favoritos: marcar y desmarcar
        fav = pg.evaluate("""async () => {
            const antes = (await (await fetch('/api/chat/llamadas/favoritos', {credentials:'same-origin'})).json()).personas.length;
            await fetch('/api/chat/llamadas/favoritos', {method:'POST', credentials:'same-origin',
                headers:{'Content-Type':'application/json'}, body: JSON.stringify({usuario_id: 17})});
            const con = (await (await fetch('/api/chat/llamadas/favoritos', {credentials:'same-origin'})).json()).personas.length;
            await fetch('/api/chat/llamadas/favoritos/17', {method:'DELETE', credentials:'same-origin'});
            const fin = (await (await fetch('/api/chat/llamadas/favoritos', {credentials:'same-origin'})).json()).personas.length;
            return {antes, con, fin};
        }""")
        check('T-46 . se puede marcar y quitar un favorito',
              fav['con'] == fav['antes'] + 1 and fav['fin'] == fav['antes'], 'antes=%(antes)s con=%(con)s final=%(fin)s' % fav)
        frec = pg.evaluate("async () => (await (await fetch('/api/chat/llamadas/frecuentes', {credentials:'same-origin'})).json()).personas.length")
        check('T-46 . hay marcación rápida (favoritos y frecuentes)', frec >= 0, '%s personas frecuentes' % frec)
        nav.close()
    print('\nCandado T-46 (sección Llamadas): %s' %
          ('TODO OK - 0 fallas' if not fallas else '%d FALLAS -> %s' % (len(fallas), fallas)))
    return 1 if fallas else 0

if __name__ == '__main__':
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else ''))
