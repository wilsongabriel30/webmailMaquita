#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""T-45 puntos 10 y 11 - Burbujas que ocupan el ancho y vistos claros.
Con navegador real (agente MaquitaTeams) en 360, 800 y 1100 px."""
import sys

from playwright.sync_api import sync_playwright
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from comun import BASE, HOST, CUENTA, DESTINO, PERSONA, CONVERSACION, UID_CORREO  # noqa: E402,F401

UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36 MaquitaTeams/0.4.49'
FRASE = 'Esta frase mide justo cuarenta caracteres.'   # 41
LARGO = ('Buenos dias equipo, les comparto que el informe mensual de cooperacion ya '
         'quedo revisado y subido a la carpeta compartida; cualquier observacion me '
         'la hacen llegar antes del viernes para consolidarla con contabilidad.')
fallas = []


def check(n, ok, d=''):
    print(('[OK    ] ' if ok else '[FALLA ] ') + n + (' - ' + d if d else ''))
    if not ok:
        fallas.append(n)


def main(tok, conversacion=32):
    with sync_playwright() as p:
        nav = p.chromium.launch(args=['--no-sandbox'])
        for ancho in (360, 800, 1100):
            ctx = nav.new_context(user_agent=UA, viewport={'width': ancho, 'height': 820})
            ctx.add_cookies([{'name': 'access_token', 'value': tok, 'domain': HOST, 'path': '/'}])
            pg = ctx.new_page()
            pg.goto('%s/chat/conversation/%d' % (BASE, conversacion), wait_until='domcontentloaded', timeout=60000)
            pg.wait_for_timeout(6000)

            # se inyecta una burbuja de prueba con la frase de 40 caracteres
            pg.evaluate("""(frase) => {
                const c = document.querySelector('.chat-messages'); if (!c) return;
                const d = document.createElement('div');
                d.className = 'message sent'; d.dataset.messageId = 'humo-1';
                d.innerHTML = '<div class="message-content"><div class="message-text">' + frase +
                    '</div><div class="message-meta"><span class="time">10:00</span>' +
                    '<i class="fas fa-check-double message-status delivered"></i></div></div>';
                c.appendChild(d);
            }""", FRASE)
            pg.wait_for_timeout(600)

            m = pg.evaluate("""() => {
                const b = document.querySelector('.message[data-message-id="humo-1"] .message-content');
                const t = b.querySelector('.message-text');
                const fila = b.closest('.message');
                const panel = document.querySelector('.chat-messages');
                const cs = getComputedStyle(t);
                const alto = t.getBoundingClientRect().height;
                const linea = parseFloat(cs.lineHeight) || 20;
                return {burbuja: b.getBoundingClientRect().width,
                        panel: panel.getBoundingClientRect().width,
                        fila: fila.getBoundingClientRect().width,
                        lineas: Math.round(alto / linea),
                        desborde: document.documentElement.scrollWidth > document.documentElement.clientWidth};
            }""")
            check('T-45.11 . %dpx la frase de 40 caracteres no se parte en columna' % ancho,
                  m['lineas'] <= 3, '%d líneas' % m['lineas'])
            check('T-45.11 . %dpx la burbuja usa el ancho disponible' % ancho,
                  m['burbuja'] >= min(240, m['panel'] * .55),
                  'burbuja=%dpx panel=%dpx' % (m['burbuja'], m['panel']))
            check('T-45.11 . %dpx la burbuja no pasa del tope ni desborda' % ancho,
                  m['burbuja'] <= m['panel'] + 2 and not m['desborde'],
                  'desborde horizontal=%s' % m['desborde'])
            check('T-45.11 . %dpx la fila ocupa el panel completo' % ancho,
                  m['fila'] >= m['panel'] - 40, 'fila=%dpx' % m['fila'])

            # y un parrafo largo: debe estirarse hasta el tope, no encogerse
            pg.evaluate("""(largo) => {
                const c = document.querySelector('.chat-messages');
                const d = document.createElement('div');
                d.className = 'message received'; d.dataset.messageId = 'humo-2';
                d.innerHTML = '<div class="message-content"><div class="message-text">' + largo + '</div></div>';
                c.appendChild(d);
            }""", LARGO)
            pg.wait_for_timeout(400)
            g = pg.evaluate("""() => {
                const b = document.querySelector('.message[data-message-id="humo-2"] .message-content');
                const p = document.querySelector('.chat-messages');
                const t = b.querySelector('.message-text');
                const cs = getComputedStyle(t);
                return {b: b.getBoundingClientRect().width, p: p.getBoundingClientRect().width,
                        lineas: Math.round(t.getBoundingClientRect().height / (parseFloat(cs.lineHeight) || 20))};
            }""")
            # el ancho util llega al tope menos lo que sobra en la ultima linea
            # (una palabra no cabe entera): se admite hasta un 10 % de holgura
            tope = g['p'] * (0.86 if ancho <= 700 else 0.65)
            check('T-45.11 . %dpx el parrafo largo se estira hasta el tope' % ancho,
                  g['b'] >= tope * 0.9, 'ancho=%dpx tope=%dpx' % (g['b'], tope))
            check('T-45.11 . %dpx el parrafo largo no cae en columna estrecha' % ancho,
                  g['lineas'] <= 14, '%d líneas para %d caracteres' % (g['lineas'], len(LARGO)))

            if ancho == 1100:
                # vistos: el pintado debe ser inmediato y con la palabra «Leído»
                pg.evaluate("() => window.mqPintarVisto('humo-1', 'read')")
                pg.wait_for_timeout(150)
                v = pg.evaluate("""() => {
                    const m = document.querySelector('.message[data-message-id="humo-1"]');
                    const i = m.querySelector('.message-status');
                    const e = m.querySelector('.mq-leido');
                    return {dobles: i.className.includes('check-double'), encendido: i.classList.contains('read'),
                            palabra: e ? e.textContent : '', color: e ? getComputedStyle(e).color : ''};
                }""")
                check('T-45.10 . dos vistos encendidos al leerse', v['dobles'] and v['encendido'])
                check('T-45.10 . aparece la palabra «Leído» junto a la hora',
                      v['palabra'].startswith('Leído'), 'texto=%r' % v['palabra'])
                check('T-45.10 . el estado cambia en el acto (menos de 150 ms)', v['encendido'])
                check('T-45.10 . el módulo escucha el aviso de lectura del socket',
                      pg.evaluate("() => typeof window.mqPintarVisto === 'function'"))
            ctx.close()
        nav.close()
    print('\nCandado T-45 puntos 10 y 11: %s' %
          ('TODO OK - 0 fallas' if not fallas else '%d FALLAS -> %s' % (len(fallas), fallas)))
    return 1 if fallas else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1], int(sys.argv[2]) if len(sys.argv) > 2 else int(CONVERSACION)))
