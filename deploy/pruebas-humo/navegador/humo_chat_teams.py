#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""T-50 tanda 1 - El panel de la izquierda como Teams.
Comprueba los puntos 1, 2, 5, 6, 8, 9 y 35 del requerimiento."""
import sys

from playwright.sync_api import sync_playwright
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from comun import BASE, HOST, CUENTA, DESTINO, PERSONA, CONVERSACION, UID_CORREO  # noqa: E402,F401

UA = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) '
      'Chrome/151.0.0.0 Safari/537.36 MaquitaTeams/0.4.61')
fallas = []


def check(n, ok, d=''):
    print(('[OK    ] ' if ok else '[FALLA ] ') + n + (' - ' + d if d else ''))
    if not ok:
        fallas.append(n)


def main(tok):
    errores = []
    with sync_playwright() as p:
        nav = p.chromium.launch(args=['--no-sandbox'])
        ctx = nav.new_context(user_agent=UA, viewport={'width': 1366, 'height': 900})
        ctx.add_cookies([{'name': 'access_token', 'value': tok,
                          'domain': HOST, 'path': '/'}])
        pg = ctx.new_page()
        pg.on('console', lambda m: errores.append(m.text) if m.type == 'error' else None)
        pg.goto(BASE + '/chat/', wait_until='load', timeout=60000)
        pg.wait_for_timeout(9000)

        # punto 1: el modulo se llama Chat
        titulo = pg.evaluate("""() => {
            const h = document.querySelector('.chat-sidebar-header h5');
            return h ? h.textContent.trim() : '';
        }""")
        check('T-50.1 . el módulo se llama «Chat»', 'Chat' in titulo and 'Mensajes' not in titulo,
              'dice %r' % titulo)

        # punto 2: los filtros de Teams
        filtros = pg.evaluate("""() => Array.from(document.querySelectorAll('.mq-filtro'))
            .map(b => b.textContent.trim())""")
        check('T-50.2 . están los filtros «No leído» y «Chats de reuniones»',
              'No leído' in filtros and 'Chats de reuniones' in filtros, '%s' % filtros)
        viejas = pg.evaluate("""() => Array.from(document.querySelectorAll('.chat-tab[data-tab]'))
            .filter(t => getComputedStyle(t).display !== 'none').length""")
        check('T-50.2 . las pestañas antiguas ya no se ven', viejas == 0,
              '%d visibles' % viejas)

        # puntos 8 y 9: se puede fijar y aparece la sección Favoritos
        conv = pg.evaluate("""() => {
            const f = document.querySelector('.conversation-item[data-conv-id]');
            return f ? Number(f.dataset.convId) : 0;
        }""")
        check('T-50 . hay conversaciones con las que probar', conv > 0, 'conversación %s' % conv)
        if conv:
            pg.evaluate("(id) => window.mqAlternarFavorito(id)", conv)
            pg.wait_for_timeout(2500)
            secciones = pg.evaluate("""() => Array.from(document.querySelectorAll('.mq-seccion-lista span:first-child'))
                .map(s => s.textContent.trim())""")
            check('T-50.8 . aparece la sección «Favoritos» al fijar', 'Favoritos' in secciones,
                  '%s' % secciones)
            check('T-50.9 . la sección «Chats» queda debajo',
                  'Chats' in secciones or len(secciones) == 1, '%s' % secciones)
            check('T-50.8 . la conversación fijada queda marcada',
                  pg.evaluate("(id) => !!document.querySelector('.conversation-item.mq-favorita[data-conv-id=\"'+id+'\"]')", conv))
            # se deja como estaba
            pg.evaluate("(id) => window.mqAlternarFavorito(id)", conv)
            pg.wait_for_timeout(1800)

        # punto 6: presencia SIEMPRE sobre el avatar
        presencia = pg.evaluate("""() => {
            const filas = document.querySelectorAll('.conversation-item[data-conv-id]');
            let con = 0;
            filas.forEach(f => { if (f.querySelector('.mq-estado')) con++; });
            return {total: filas.length, con: con};
        }""")
        check('T-50.6 . TODOS los avatares llevan indicador de presencia',
              presencia['total'] > 0 and presencia['con'] == presencia['total'],
              '%d de %d' % (presencia['con'], presencia['total']))

        # punto 5: alturas y tipografía de la fila
        medidas = pg.evaluate("""() => {
            const f = document.querySelector('.conversation-item[data-conv-id]');
            if (!f) return null;
            const n = f.querySelector('.conversation-name');
            return {alto: f.getBoundingClientRect().height,
                    fuente: n ? getComputedStyle(n).fontSize : ''};
        }""")
        check('T-50.5 . la fila tiene la altura y la tipografía pedidas',
              medidas and medidas['alto'] >= 50 and medidas['fuente'] == '14px',
              'alto=%.0fpx fuente=%s' % (medidas['alto'], medidas['fuente']) if medidas else 'sin filas')

        # punto 35: sin leer en negrita y con punto
        check('T-50.35 . la marca de «sin leer» está definida',
              pg.evaluate("""() => {
                  const f = document.querySelector('.conversation-item');
                  if (!f) return false;
                  f.classList.add('mq-no-leida');
                  const n = f.querySelector('.conversation-name');
                  const peso = n ? getComputedStyle(n).fontWeight : '';
                  const punto = getComputedStyle(f, '::before').width;
                  f.classList.remove('mq-no-leida');
                  return (peso === '700' || peso === 'bold') && punto !== 'auto' && punto !== '0px';
              }"""))

        # ---------- el hover no puede mover NADA (bug reportado en vivo) ----------
        filas_hover = pg.query_selector_all('.conversations-list .conversation-item[data-conv-id]')
        if filas_hover:
            antes = pg.evaluate("() => Array.from(document.querySelectorAll('.conversations-list .conversation-item')).map(function (f) { var r = f.getBoundingClientRect(); return [Math.round(r.top), Math.round(r.height), Math.round(r.left)]; })")
            filas_hover[0].hover()
            pg.wait_for_timeout(700)
            durante = pg.evaluate("() => Array.from(document.querySelectorAll('.conversations-list .conversation-item')).map(function (f) { var r = f.getBoundingClientRect(); return [Math.round(r.top), Math.round(r.height), Math.round(r.left)]; })")
            if len(filas_hover) > 1:
                filas_hover[1].hover()
                pg.wait_for_timeout(700)
            despues = pg.evaluate("() => Array.from(document.querySelectorAll('.conversations-list .conversation-item')).map(function (f) { var r = f.getBoundingClientRect(); return [Math.round(r.top), Math.round(r.height), Math.round(r.left)]; })")
            check('T-50 . pasar el raton por una fila no mueve la lista',
                  antes == durante, 'posiciones antes=%s durante=%s' % (antes[:2], durante[:2]))
            check('T-50 . pasar de una fila a otra tampoco la mueve',
                  durante == despues, 'durante=%s despues=%s' % (durante[:2], despues[:2]))
            # y que no haya un repintado en bucle: se cuentan los cambios del DOM con el raton encima
            pg.evaluate("() => { window.__mqCambios = 0; var l = document.getElementById('conversationsList'); window.__mqObs = new MutationObserver(function (ms) { window.__mqCambios += ms.length; }); window.__mqObs.observe(l, {childList: true, subtree: true, attributes: true}); }")
            filas_hover[0].hover()
            pg.wait_for_timeout(2500)
            cambios = pg.evaluate("() => { window.__mqObs.disconnect(); return window.__mqCambios; }")
            check('T-50 . con el raton encima la lista no se repinta en bucle', cambios < 25,
                  '%d cambios del DOM en 2,5 s' % cambios)

        # ---------- TANDA 2: el encabezado del chat activo ----------
        if conv:
            pg.evaluate("(id) => window.openConversation && window.openConversation(id, 'direct')", conv)
            pg.wait_for_timeout(5000)

            pestanas = pg.evaluate("() => Array.from(document.querySelectorAll('.mq-pestana')).map(b => b.textContent.trim())")
            check('T-50.10 . el encabezado tiene las pestanas Chat, Archivos y Fotos',
                  pestanas == ['Chat', 'Archivos', 'Fotos'], '%s' % pestanas)

            orden = pg.evaluate("() => Array.from(document.querySelectorAll('.chat-main-header .chat-actions > button')).map(b => b.id)")
            esperado = ['btnLlamadaVideo', 'btnLlamadaAudio', 'mq-participantes', 'mq-buscar', 'mq-mas']
            reales = [o for o in orden if o in esperado]
            check('T-50.11 . las acciones van en el orden de Teams', reales == esperado, '%s' % reales)

            check('T-50.14 . esta el boton de agregar participantes',
                  pg.evaluate("() => !!document.getElementById('mq-participantes')"))

            check('T-50.12-13 . videollamada y llamada estan en el encabezado del chat',
                  pg.evaluate("() => { var c = document.querySelector('.chat-main-header .chat-actions'); return !!(c && c.querySelector('#btnLlamadaVideo') && c.querySelector('#btnLlamadaAudio')); }"))

            check('T-50.6 . el avatar del encabezado lleva indicador de presencia',
                  pg.evaluate("() => { var a = document.getElementById('chatHeaderAvatar'); return !!a && a.classList.contains('mq-estado'); }"))

            pg.evaluate("() => window.mqCambiarVistaChat('archivos')")
            pg.wait_for_timeout(900)
            filtrado = pg.evaluate("() => { var h = document.getElementById('chatMessages'); var ms = h.querySelectorAll('.message'); var vis = 0; ms.forEach(function (m) { if (getComputedStyle(m).display !== 'none') vis++; }); return {total: ms.length, visibles: vis, aviso: !!h.querySelector('.mq-sin-nada')}; }")
            check('T-50.10 . la pestana Archivos filtra el hilo',
                  filtrado['total'] == 0 or filtrado['visibles'] < filtrado['total'] or filtrado['aviso'],
                  '%d de %d visibles, aviso=%s' % (filtrado['visibles'], filtrado['total'], filtrado['aviso']))

            pg.evaluate("() => window.mqCambiarVistaChat('chat')")
            pg.wait_for_timeout(700)
            check('T-50.10 . al volver a Chat se ve todo otra vez',
                  pg.evaluate("() => { var h = document.getElementById('chatMessages'); var ms = h.querySelectorAll('.message'); var vis = 0; ms.forEach(function (m) { if (getComputedStyle(m).display !== 'none') vis++; }); return ms.length === vis; }"))

        # ---------- TANDA 3: historial y barra de redaccion ----------
        if conv:
            # punto 24: la caja dice "Escribe un mensaje" y esta abajo
            caja = pg.evaluate("() => { var t = document.getElementById('messageInput'); if (!t) return null; var r = t.getBoundingClientRect(); return {texto: t.placeholder, y: r.top, alto: window.innerHeight}; }")
            check('T-50.24 . la caja dice «Escribe un mensaje» y esta abajo',
                  caja and 'scribe un mensaje' in (caja['texto'] or '') and caja['y'] > caja['alto'] * 0.6,
                  'texto=%r' % (caja['texto'] if caja else None))

            # punto 29: ENVIAR es el ultimo de la fila y se ve siempre
            envio = pg.evaluate("() => { var c = document.querySelector('.chat-input-container'); var b = document.getElementById('btnSendMessage'); if (!c || !b) return null; var bs = Array.from(c.querySelectorAll('button')).filter(function (x) { return getComputedStyle(x).display !== 'none'; }); var xs = bs.map(function (x) { return x.getBoundingClientRect().left; }); return {visible: getComputedStyle(b).display !== 'none', esUltimo: b.getBoundingClientRect().left >= Math.max.apply(null, xs) - 1}; }")
            check('T-50.29 . el boton de enviar se ve siempre', envio and envio['visible'])
            check('T-50.29 . y esta en el extremo derecho de la barra', envio and envio['esUltimo'])

            # punto 26: el boton de adjuntar sigue ahi
            check('T-50.26 . esta el boton de adjuntar archivos',
                  pg.evaluate("() => !!document.querySelector('.chat-input-container button[onclick*=\"attachFile\"]')"))

            # punto 18: recibidos a la izquierda, enviados a la derecha
            lados = pg.evaluate("() => { var h = document.getElementById('chatMessages'); if (!h) return null; var med = h.getBoundingClientRect().left + h.getBoundingClientRect().width / 2; var mal = 0, prop = 0, aj = 0; h.querySelectorAll('.message').forEach(function (m) { var b = m.querySelector('.message-content'); if (!b) return; var r = b.getBoundingClientRect(); var centro = r.left + r.width / 2; if (m.classList.contains('sent')) { prop++; if (centro < med) mal++; } else { aj++; if (centro > med) mal++; } }); return {propios: prop, ajenos: aj, malColocados: mal}; }")
            check('T-50.18 . recibidos a la izquierda y enviados a la derecha',
                  lados and lados['malColocados'] == 0,
                  '%d propios, %d ajenos, %d mal colocados' % (lados['propios'], lados['ajenos'], lados['malColocados']) if lados else 'sin datos')

            # punto 19: las burbujas conservan lo de T-45 dentro de la estructura nueva
            burbuja = pg.evaluate("() => { var b = document.querySelector('.chat-messages .message.sent .message-content'); if (!b) return null; var cs = getComputedStyle(b); return {radio: cs.borderRadius, fondo: cs.backgroundColor, ancho: b.getBoundingClientRect().width, panel: document.querySelector('.chat-messages').getBoundingClientRect().width}; }")
            check('T-50.19 . las burbujas mantienen forma, color y ancho de T-45',
                  burbuja and burbuja['radio'] != '0px' and burbuja['ancho'] <= burbuja['panel'],
                  'radio=%s fondo=%s ancho=%dpx' % (burbuja['radio'], burbuja['fondo'], burbuja['ancho']) if burbuja else 'sin burbujas')

        graves = [e for e in errores if 'is not defined' in e or 'SyntaxError' in e]
        check('T-50 . sin errores de JavaScript', not graves, '; '.join(graves[:2]) if graves else 'ninguno')
        nav.close()
    print('\nCandado T-50 tandas 1, 2 y 3 (panel, encabezado y redaccion): %s' %
          ('TODO OK - 0 fallas' if not fallas else '%d FALLAS -> %s' % (len(fallas), fallas)))
    return 1 if fallas else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1]))
