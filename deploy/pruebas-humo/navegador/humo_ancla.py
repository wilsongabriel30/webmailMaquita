#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""T-54a - Candado del anclaje instantaneo.

Como se mide «el paseo»: se vigila la posicion del hilo desde que se abre la conversacion.
Si el navegador ANIMA el recorrido, la posicion pasa por decenas de valores intermedios; si
salta de golpe, hay uno o dos. Se exige lo segundo.
"""
import sys

from playwright.sync_api import sync_playwright
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from comun import BASE, HOST, CUENTA, DESTINO, PERSONA, CONVERSACION, UID_CORREO  # noqa: E402,F401

UA = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) '
      'Chrome/151.0.0.0 Safari/537.36 MaquitaTeams/0.4.69')
fallas = []


def check(n, ok, d=''):
    print(('[OK    ] ' if ok else '[FALLA ] ') + n + (' - ' + d if d else ''))
    if not ok:
        fallas.append(n)


def main(tok, conv=48):
    with sync_playwright() as p:
        nav = p.chromium.launch(args=['--no-sandbox'])
        ctx = nav.new_context(user_agent=UA, viewport={'width': 1366, 'height': 900})
        ctx.add_cookies([{'name': 'access_token', 'value': tok,
                          'domain': HOST, 'path': '/'}])
        pg = ctx.new_page()
        pg.goto(BASE + '/chat/', wait_until='load', timeout=60000)
        pg.wait_for_timeout(8000)

        # el estilo que causaba el barrido no puede volver
        suave = pg.evaluate("""() => {
            const c = document.getElementById('chatMessages');
            return c ? getComputedStyle(c).scrollBehavior : 'sin-hilo';
        }""")
        check('T-54a . el hilo NO tiene desplazamiento suave permanente', suave != 'smooth',
              'scroll-behavior=%s' % suave)

        # se vigila la posicion mientras se abre la conversacion
        pg.evaluate("""() => {
            window.__mqPosiciones = [];
            const c = document.getElementById('chatMessages');
            if (c) {
                window.__mqVigia = () => window.__mqPosiciones.push(Math.round(c.scrollTop));
                c.addEventListener('scroll', window.__mqVigia);
            }
        }""")
        pg.evaluate("(id) => window.openConversation && window.openConversation(id, 'direct')", conv)
        pg.wait_for_timeout(6000)

        r = pg.evaluate("""() => {
            const c = document.getElementById('chatMessages');
            const pos = window.__mqPosiciones || [];
            // cuantos valores DISTINTOS: si hubo animacion, son muchos
            const distintos = Array.from(new Set(pos)).length;
            return {saltos: distintos, total: pos.length,
                    mensajes: c ? c.querySelectorAll('.message').length : 0,
                    alFinal: c ? (c.scrollHeight - c.scrollTop - c.clientHeight) < 250 : false,
                    hayMarca: !!(c && c.querySelector('.mq-nuevos'))};
        }""")
        check('T-54a . la conversacion tiene mensajes de sobra para notarse',
              r['mensajes'] >= 20, '%d mensajes' % r['mensajes'])
        check('T-54a . al abrir NO hay paseo por la historia', r['saltos'] <= 4,
              '%d posiciones distintas (%d avisos de scroll)' % (r['saltos'], r['total']))
        check('T-54a . queda colocada donde toca',
              r['alFinal'] or r['hayMarca'],
              'al final=%s, marca de nuevos=%s' % (r['alFinal'], r['hayMarca']))

        # el caso del PRIMER NO LEIDO: se pone la marca a mitad del hilo y se pide anclar.
        # Es el caso que pidio soporte y no siempre hay uno real a mano, asi que se provoca.
        anclado = pg.evaluate("""() => {
            const c = document.getElementById('chatMessages');
            const ms = c.querySelectorAll('.message');
            if (ms.length < 10) return null;
            const previo = c.querySelector('.mq-nuevos');
            if (previo) previo.remove();
            const marca = document.createElement('div');
            marca.className = 'mq-nuevos';
            marca.textContent = 'Mensajes nuevos';
            ms[Math.floor(ms.length / 2)].before(marca);
            c.scrollTop = 0;                       // se lleva la vista arriba del todo
            window.MaquitaAncla.anclar();          // y se pide colocarse
            const r = marca.getBoundingClientRect(), rc = c.getBoundingClientRect();
            return {visible: r.top >= rc.top - 80 && r.top <= rc.bottom,
                    posicion: Math.round(c.scrollTop)};
        }""")
        if anclado:
            check('T-54a . ancla en el PRIMER mensaje sin leer', anclado['visible'],
                  'la marca queda a la vista (posicion %s)' % anclado['posicion'])
        else:
            print('[  ..  ] T-54a . no habia mensajes suficientes para probar el no leido')

        # y con ?msg= debe quedarse en ESE mensaje, tambien de golpe
        # Se elige un mensaje del ULTIMO TERCIO, no el primero.
        # El primero de la lista es el MAS ANTIGUO de los cargados y, si entran mensajes
        # nuevos mientras corre el candado, se sale de la ventana de los ultimos y al
        # recargar ya no esta: la comprobacion fallaba unas veces si y otras no. Uno del
        # ultimo tercio siempre sigue cargado, y no es el ultimo del todo, asi que anclar
        # a el se nota.
        alguno = pg.evaluate("""() => {
            const ms = document.querySelectorAll('.chat-messages .message[data-message-id]');
            if (!ms.length) return null;
            const i = Math.max(0, ms.length - Math.max(3, Math.floor(ms.length / 3)));
            return ms[i].dataset.messageId;
        }""")
        if alguno:
            pg.goto('%s/chat/conversation/%d?msg=%s' % (BASE, conv, alguno),
                    wait_until='domcontentloaded', timeout=60000)
            # Se ESPERA a que el mensaje exista, en vez de confiar en un tiempo fijo.
            # Con la maquina de pruebas cargada -varios bloques del candado a la vez- la
            # pagina tarda mas en pintar, y con una espera fija esta comprobacion fallaba
            # unas veces si y otras no. Un candado intermitente es peor que ninguno:
            # ensena a no hacer caso de los rojos.
            try:
                pg.wait_for_function(
                    "(id) => !!document.querySelector('.message[data-message-id=\"' + id + '\"]')",
                    arg=alguno, timeout=25000)
                pg.wait_for_timeout(1200)      # que termine de colocarse
            except Exception:
                pass
            v = pg.evaluate("""(id) => {
                const c = document.getElementById('chatMessages');
                const m = c ? c.querySelector('.message[data-message-id="' + id + '"]') : null;
                if (!c || !m) return null;
                const r = m.getBoundingClientRect(), rc = c.getBoundingClientRect();
                return {visible: r.top >= rc.top - 40 && r.bottom <= rc.bottom + 40};
            }""", alguno)
            check('T-54a . con ?msg= se queda en ESE mensaje',
                  bool(v and v['visible']), 'visible=%s' % (v and v['visible']))
        nav.close()
    print('\nCandado T-54a (llegar sin paseo): %s' %
          ('TODO OK - 0 fallas' if not fallas else '%d FALLAS -> %s' % (len(fallas), fallas)))
    return 1 if fallas else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1]))
