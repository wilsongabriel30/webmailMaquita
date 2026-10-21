#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""T-45 punto 9 - Ambitos de busqueda.
La lupa de una conversacion busca SOLO en esa conversacion; lo transversal (contenido de
todos los chats y personas del directorio) vive en el buscador de la izquierda."""
import sys
import time

from playwright.sync_api import sync_playwright
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from comun import BASE, HOST, CUENTA, DESTINO, PERSONA, CONVERSACION, UID_CORREO  # noqa: E402,F401

UA = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) '
      'Chrome/151.0.0.0 Safari/537.36 MaquitaTeams/0.4.50')
fallas = []


def check(n, ok, d=''):
    print(('[OK    ] ' if ok else '[FALLA ] ') + n + (' - ' + d if d else ''))
    if not ok:
        fallas.append(n)


def main(tok, conv_a=32, conv_b=None):
    marca = 'ambito%d' % int(time.time())
    with sync_playwright() as p:
        nav = p.chromium.launch(args=['--no-sandbox'])
        ctx = nav.new_context(user_agent=UA, viewport={'width': 1280, 'height': 860})
        ctx.add_cookies([{'name': 'access_token', 'value': tok, 'domain': HOST, 'path': '/'}])
        pg = ctx.new_page()
        pg.goto('%s/chat/' % BASE, wait_until='domcontentloaded', timeout=60000)
        pg.wait_for_timeout(6000)

        # se averigua otra conversacion distinta de la de referencia
        convs = pg.evaluate("""async () => {
            const r = await fetch('/api/chat/conversations');
            const d = await r.json();
            const l = d.conversations || d.conversaciones || d.resultados || [];
            return l.map(c => c.id);
        }""")
        otras = [c for c in convs if c != conv_a]
        if conv_b is None:
            conv_b = 52 if 52 in convs else (otras[0] if otras else None)  # 52 = conversacion de candados
        check('T-45.9 . hay dos conversaciones para comparar ámbitos',
              conv_b is not None, 'A=%s B=%s' % (conv_a, conv_b))
        if conv_b is None:
            nav.close()
            return 1

        # se deja una palabra unica en la conversacion B
        env = pg.evaluate("""async ([conv, texto]) => {
            const r = await fetch('/api/chat/conversations/' + conv + '/messages', {
                method: 'POST', headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({content: texto, message_type: 'text'})});
            return r.status;
        }""", [conv_b, 'Palabra de prueba ' + marca])
        check('T-45.9 . se deja una palabra única en la otra conversación', env in (200, 201),
              'estado=%s' % env)
        pg.wait_for_timeout(1500)

        # 1) la lupa de la conversacion A: no debe encontrar lo que esta en B
        enA = pg.evaluate("""async ([conv, q]) => {
            const r = await fetch('/api/chat/buscar-mensajes?q=' + encodeURIComponent(q) +
                                  '&conversation_id=' + conv);
            const d = await r.json();
            return (d.resultados || []).length;
        }""", [conv_a, marca])
        check('T-45.9 . la lupa de una conversación NO ve lo de otra conversación',
              enA == 0, '%d resultados' % enA)

        # 2) la lupa de la conversacion B: si debe encontrarlo
        enB = pg.evaluate("""async ([conv, q]) => {
            const r = await fetch('/api/chat/buscar-mensajes?q=' + encodeURIComponent(q) +
                                  '&conversation_id=' + conv);
            const d = await r.json();
            return (d.resultados || []).length;
        }""", [conv_b, marca])
        check('T-45.9 . la lupa SÍ encuentra lo que está en su propia conversación',
              enB >= 1, '%d resultados' % enB)

        # 3) el buscador general: si ve el contenido de todos los chats
        general = pg.evaluate("""async (q) => {
            const r = await fetch('/api/chat/buscar-mensajes?q=' + encodeURIComponent(q));
            const d = await r.json();
            return (d.resultados || []).length;
        }""", marca)
        check('T-45.9 . el buscador general SÍ ve el contenido de todos los chats',
              general >= 1, '%d resultados' % general)

        # 4) la lupa ya no ofrece saltar a «todas las conversaciones»
        pg.goto('%s/chat/conversation/%d' % (BASE, conv_a), wait_until='domcontentloaded', timeout=60000)
        pg.wait_for_timeout(5000)
        lupa = pg.evaluate("""() => {
            if (typeof window.abrirBuscadorMensajes !== 'function') return {falta: true};
            window.abrirBuscadorMensajes();
            const ov = document.getElementById('buscadorMsgOverlay');
            return {falta: false,
                    radios: ov ? ov.querySelectorAll('input[name="ambitoBusq"]').length : -1,
                    texto: ov ? (ov.querySelector('#buscarMsgInput') || {}).placeholder : ''};
        }""")
        check('T-45.9 . la lupa no ofrece el salto a «todas las conversaciones»',
              lupa.get('radios') == 0, 'selectores de ámbito=%s' % lupa.get('radios'))
        check('T-45.9 . la lupa dice que busca en esta conversación',
              'esta conversación' in (lupa.get('texto') or ''), 'texto=%r' % lupa.get('texto'))

        # 5) el buscador de la izquierda muestra la seccion de contenido
        pg.goto('%s/chat/' % BASE, wait_until='domcontentloaded', timeout=60000)
        pg.wait_for_timeout(6000)
        pg.evaluate("""(q) => {
            const i = document.getElementById('searchConversations');
            i.value = q; i.dispatchEvent(new Event('input', {bubbles: true}));
            if (typeof window.filterConversations === 'function') window.filterConversations(q);
        }""", marca)
        pg.wait_for_timeout(3000)
        izq = pg.evaluate("""() => {
            const s = document.getElementById('mensajesBusqueda');
            return {hay: !!s, filas: s ? s.querySelectorAll('.mq-resultado-mensaje').length : 0,
                    resalta: s ? s.querySelectorAll('mark').length : 0};
        }""")
        check('T-45.9 . el buscador de la izquierda muestra la sección «Mensajes»',
              izq['hay'] and izq['filas'] >= 1, '%d resultados' % izq['filas'])
        check('T-45.9 . resalta el término encontrado', izq['resalta'] >= 1,
              '%d resaltados' % izq['resalta'])
        check('T-45.9 . el buscador de la izquierda también propone personas',
              pg.evaluate("() => typeof window.buscarCompanerosEnLista === 'function'"))
        nav.close()
    print('\nCandado T-45 punto 9 (ámbitos de búsqueda): %s' %
          ('TODO OK - 0 fallas' if not fallas else '%d FALLAS -> %s' % (len(fallas), fallas)))
    return 1 if fallas else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1], int(sys.argv[2]) if len(sys.argv) > 2 else int(CONVERSACION)))
