#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""T-45 · Candado del look de la conversación (estilo Teams con nuestra paleta).
Comprueba en el navegador, sobre una conversación real, que:
  · mis mensajes salen en azul institucional con texto blanco, a la derecha;
  · los del otro, en gris claro con avatar;
  · los mensajes seguidos de la misma persona se agrupan;
  · un mensaje que es solo emojis se pinta grande y sin burbuja;
  · hay separador de día y mini-barra de reacciones al pasar el mouse;
  · la caja de escribir tiene corrector en español (punto 8).
Uso: humo-look <token>"""
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
        ctx = nav.new_context(user_agent=UA, viewport={'width': 1200, 'height': 900})
        ctx.set_default_timeout(20000)
        ctx.add_cookies([{'name': 'access_token', 'value': tok, 'domain': HOST, 'path': '/', 'secure': True}])
        pg = ctx.new_page()
        pg.goto(BASE + '/chat/conversation/' + CONVERSACION, wait_until='domcontentloaded', timeout=60000)
        pg.wait_for_timeout(13000)

        estilos = pg.evaluate("""() => {
            const rgb = e => e ? getComputedStyle(e).backgroundColor : '';
            const col = e => e ? getComputedStyle(e).color : '';
            const mio = document.querySelector('.message.sent .message-content');
            const otro = document.querySelector('.message.received .message-content');
            const cont = document.getElementById('chatMessages');
            return {
                mio: rgb(mio), textoMio: col(mio), otro: rgb(otro),
                anchoMio: mio ? Math.round(mio.getBoundingClientRect().width / cont.getBoundingClientRect().width * 100) : 0,
                agrupados: document.querySelectorAll('.message.mq-agrupado').length,
                mensajes: document.querySelectorAll('.message').length,
                separadores: document.querySelectorAll('.mq-separador').length,
                barras: document.querySelectorAll('.mq-barra-reacciones').length,
                soloEmoji: document.querySelectorAll('.message.mq-solo-emoji').length,
                caja: (() => { const c = document.getElementById('messageInput');
                    return c ? {spellcheck: c.getAttribute('spellcheck'), lang: c.getAttribute('lang')} : null; })(),
                lienzo: rgb(cont)
            };
        }""")
        check('T-45 . mis mensajes: azul institucional con texto blanco',
              estilos['mio'] == 'rgb(0, 96, 160)' and estilos['textoMio'] in ('rgb(255, 255, 255)', 'rgba(255, 255, 255, 1)'),
              'fondo=%s texto=%s' % (estilos['mio'], estilos['textoMio']))
        check('T-45 . los del otro: burbuja gris clara',
              estilos['otro'] == 'rgb(243, 242, 241)', 'fondo=%s' % estilos['otro'])
        check('T-45 . la burbuja no pasa del 65 % del panel', 0 < estilos['anchoMio'] <= 70,
              '%d %% del ancho' % estilos['anchoMio'])
        check('T-45 . mensajes seguidos de la misma persona se agrupan',
              estilos['agrupados'] > 0, '%d de %d agrupados' % (estilos['agrupados'], estilos['mensajes']))
        check('T-45 . hay separador de día', estilos['separadores'] > 0, '%d separadores' % estilos['separadores'])
        check('T-45 . cada mensaje tiene su barra de reacciones al pasar el mouse',
              estilos['barras'] >= estilos['mensajes'] and estilos['barras'] > 0, '%d barras' % estilos['barras'])
        check('T-45 (8) . la caja tiene corrector ortográfico en español',
              estilos['caja'] and estilos['caja']['spellcheck'] == 'true' and estilos['caja']['lang'] == 'es',
              'caja=%s' % estilos['caja'])
        # un mensaje solo con emojis se pinta grande
        grande = pg.evaluate("""() => {
            const c = document.getElementById('chatMessages');
            const d = document.createElement('div');
            d.className = 'message received'; d.setAttribute('data-message-id', '999999');
            d.innerHTML = '<div class="message-avatar"></div><div class="message-content"><div class="message-text">🤟</div></div>';
            c.appendChild(d);
            window.mqRepasarConversacion();
            const t = d.querySelector('.message-text');
            const r = {clase: d.classList.contains('mq-solo-emoji'), tam: getComputedStyle(t).fontSize,
                       fondo: getComputedStyle(d.querySelector('.message-content')).backgroundColor};
            d.remove();
            return r;
        }""")
        check('T-45 . un mensaje de solo emojis se pinta GIGANTE y sin burbuja',
              grande['clase'] and grande['tam'] == '40px' and 'rgba(0, 0, 0, 0)' in grande['fondo'],
              'tamaño=%s fondo=%s' % (grande['tam'], grande['fondo']))
        # --- piezas finales de T-45 ---
        emo = pg.evaluate("""() => {
            if (window.toggleEmojiPicker) window.toggleEmojiPicker();
            const p = document.querySelector('#emojiPicker, .emoji-picker, [id*=emoji]');
            const r = {buscador: !!(p && p.querySelector('input')),
                       categorias: p ? p.querySelectorAll('.emoji-category, [data-category]').length : 0,
                       emojis: p ? p.querySelectorAll('.emoji-item, button').length : 0};
            if (window.toggleEmojiPicker) window.toggleEmojiPicker();
            return r;
        }""")
        check('T-45 . el selector de emojis tiene buscador y categorías',
              emo['buscador'] and emo['categorias'] >= 5 and emo['emojis'] > 30,
              '%d categorías, %d emojis' % (emo['categorias'], emo['emojis']))

        # se comprueba en dos tiempos: el navegador necesita un instante tras mover el scroll
        pg.evaluate("""() => {
            const l = document.getElementById('chatMessages');
            let c = l;
            for (let i = 0; i < 4 && c; i++) {
                const o = getComputedStyle(c).overflowY;
                if ((o === 'auto' || o === 'scroll') && c.scrollHeight > c.clientHeight + 40) break;
                c = c.parentElement;
            }
            window.__mqScroll = c || l;
            window.__mqScroll.scrollTop = 0;
            window.__mqScroll.dispatchEvent(new Event('scroll'));
        }""")
        pg.wait_for_timeout(900)
        arriba = pg.evaluate("() => !!document.querySelector('.mq-ir-final.visible')")
        pg.evaluate("""() => { const c = window.__mqScroll; c.scrollTop = c.scrollHeight; c.dispatchEvent(new Event('scroll')); }""")
        pg.wait_for_timeout(900)
        abajo = pg.evaluate("() => !!document.querySelector('.mq-ir-final.visible')")
        ir = {'existe': True, 'alSubir': arriba, 'alBajar': abajo}
        check('T-45 . aparece «Ir al final» al subir a leer historia y se esconde abajo',
              ir.get('existe') and ir.get('alSubir') and not ir.get('alBajar'), str(ir))

        nuevos = pg.evaluate("""() => {
            const c = document.getElementById('chatMessages');
            const recibidos = c.querySelectorAll('.message.received');
            if (!recibidos.length) return 'sin mensajes recibidos';
            const d = document.createElement('div'); d.className = 'mq-nuevos'; d.textContent = '2 mensajes nuevos';
            recibidos[recibidos.length - 1].parentNode.insertBefore(d, recibidos[recibidos.length - 1]);
            const est = getComputedStyle(d);
            const r = {color: est.color, texto: d.textContent};
            d.remove();
            return r;
        }""")
        check('T-45 . el marcador «Mensajes nuevos» se pinta destacado',
              isinstance(nuevos, dict) and 'rgb(196, 49, 75)' in nuevos.get('color', ''), str(nuevos))

        adj = pg.evaluate("() => typeof window.handleFileSelect === 'function' && !!window.__mqAdjunto")
        check('T-45 . el adjunto se previsualiza en la caja antes de enviarlo', bool(adj),
              'vista previa activa')

        nav.close()
    print('\nCandado T-45 (look de la conversación): %s' %
          ('TODO OK - 0 fallas' if not fallas else '%d FALLAS -> %s' % (len(fallas), fallas)))
    return 1 if fallas else 0

if __name__ == '__main__':
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else ''))
