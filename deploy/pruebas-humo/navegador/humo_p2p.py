#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""T-25 · Candado de las llamadas 1a1 DIRECTAS (PC a PC).
Comprueba que el circuito está armado y que el respaldo por servidor sigue existiendo:
  · la página de llamada carga el motor directo (llamada-p2p.js);
  · negocia por WebRTC con la señalización del chat (call_offer/call_answer/ice);
  · si no conecta, cae al servidor (LiveKit) — el camino de siempre;
  · cada llamada deja su métrica y el resumen la devuelve.
Uso: humo-p2p <token>"""
import json
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
        ctx = nav.new_context(user_agent=UA, viewport={'width': 1000, 'height': 800})
        ctx.set_default_timeout(20000)
        ctx.add_cookies([{'name': 'access_token', 'value': tok, 'domain': HOST, 'path': '/', 'secure': True}])
        pg = ctx.new_page()
        pg.goto(BASE + '/chat/llamada?role=caller&tipo=audio&peer=1&name=Prueba',
                wait_until='domcontentloaded', timeout=45000)
        pg.wait_for_timeout(5000)
        html = pg.content()
        # T-57 (28/09/2026): la capa directa se desactivo a proposito y el 1a1 va por LiveKit.
        # Lo que se vigila ahora es que no vuelva sola y que el motor de LiveKit este.
        check('T-57 . la llamada 1a1 va por LiveKit (la directa sigue desactivada)',
              'llamada-p2p.js' not in html and 'livekit-client' in html, 'LiveKit presente, P2P apagado')
        # se pide la MISMA url que usa la página (con su ?v=), que es lo que recibe la gente
        js = pg.evaluate("""async () => {
            const s = Array.from(document.scripts).map(x => x.getAttribute('src') || '')
                .find(x => x.includes('llamada-p2p.js')) || '/static/js/llamada-p2p.js';
            const r = await fetch(s);
            return r.ok ? await r.text() : ('ERROR ' + r.status);
        }""")
        check('T-25 . el motor directo se sirve de verdad al navegador',
              not js.startswith('ERROR') and len(js) > 2000, '%d caracteres' % len(js))
        check('T-25 . negocia por WebRTC con la señalización del chat',
              'RTCPeerConnection' in js and 'call_offer' in js and 'ice_candidate' in js, 'WebRTC + señalización')
        check('T-25 . si no conecta en unos segundos, cae al servidor (respaldo)',
              'empezarSFU' in js and 'ESPERA_MS' in js, 'respaldo a LiveKit')
        check('T-25 . las llamadas de grupo siguen por el servidor (sin cambios)',
              'conferencia' not in js.lower() or 'empezarSFU' in js, 'solo afecta al 1a1')
        # la métrica se registra y el resumen responde
        r = pg.evaluate("""async () => {
            const a = await fetch('/api/chat/llamada/metrica', {method: 'POST', credentials: 'same-origin',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({room: 'humo-t25', modo: 'p2p', motivo: 'candado', tipo: 'audio', role: 'caller'})});
            const b = await fetch('/api/chat/llamada/metrica/resumen?dias=30', {credentials: 'same-origin'});
            return {registro: a.status, resumen: await b.json()};
        }""")
        res = r.get('resumen') or {}
        check('T-25 . cada llamada deja su métrica (directa o por servidor)', r.get('registro') in (200, 201),
              'estado=%s' % r.get('registro'))
        check('T-25 . el resumen dice el porcentaje de llamadas directas',
              'porcentaje_p2p' in res, 'p2p=%s sfu=%s (%s%%)' % (res.get('p2p'), res.get('sfu'), res.get('porcentaje_p2p')))
        nav.close()
    print('\nCandado T-25 (llamadas directas): %s' %
          ('TODO OK - 0 fallas' if not fallas else '%d FALLAS -> %s' % (len(fallas), fallas)))
    return 1 if fallas else 0

if __name__ == '__main__':
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else ''))
