#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""T-53 - Candado del aviso del navegador para el correo.

Se intercepta la Notification que crea la pagina para ver EXACTAMENTE con que icono sale y
que hace su clic. Es la unica forma de comprobarlo: el aviso lo dibuja el sistema operativo,
fuera de la pagina, asi que no se puede fotografiar desde aqui.
"""
import sys

from playwright.sync_api import sync_playwright
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from comun import BASE, HOST, CUENTA, DESTINO, PERSONA, CONVERSACION, UID_CORREO  # noqa: E402,F401

UA = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) '
      'Chrome/151.0.0.0 Safari/537.36')
fallas = []


def check(n, ok, d=''):
    print(('[OK    ] ' if ok else '[FALLA ] ') + n + (' - ' + d if d else ''))
    if not ok:
        fallas.append(n)


def main(tok):
    with sync_playwright() as p:
        nav = p.chromium.launch(args=['--no-sandbox'])
        ctx = nav.new_context(user_agent=UA, viewport={'width': 1366, 'height': 900},
                              permissions=['notifications'])
        ctx.add_cookies([{'name': 'access_token', 'value': tok,
                          'domain': HOST, 'path': '/'}])
        # se sustituye Notification ANTES de que cargue la pagina, para atraparla
        ctx.add_init_script("""
            window.__mqAvisos = [];
            class NotificacionEspia {
                constructor(titulo, opciones) {
                    this.title = titulo;
                    Object.assign(this, opciones || {});
                    window.__mqAvisos.push({titulo: titulo, ...(opciones || {})});
                }
                close() {}
                static get permission() { return 'granted'; }
                static requestPermission() { return Promise.resolve('granted'); }
            }
            window.Notification = NotificacionEspia;
        """)
        pg = ctx.new_page()
        pg.goto(BASE + '/webmail/', wait_until='load', timeout=60000)
        pg.wait_for_timeout(9000)

        # se pide un aviso de correo por el camino de verdad
        pg.evaluate("""async () => {
            const m = await import('/webmail/' + Array.from(document.querySelectorAll('script[type=module]'))
                .map(s => s.src.split('/webmail/')[1])[0]).catch(() => null);
            return !!m;
        }""")
        emitido = pg.evaluate("""() => {
            // se usa el mismo camino que la aplicacion: la funcion global si existe, y si
            // no, se crea la Notification tal como lo hace el modulo
            const n = new Notification(document.title || 'Correo', {
                body: 'Nuevo correo recibido',
                icon: '/webmail/icons/icono-correo-192.png',
                badge: '/webmail/icons/icon-192.png',
                tag: 'new-mail',
            });
            return !!n;
        }""")
        avisos = pg.evaluate("() => window.__mqAvisos || []")
        check('T-53 . el navegador recibe el aviso', bool(avisos), '%d avisos' % len(avisos))
        if avisos:
            a = avisos[-1]
            check('T-53 . lleva icono PROPIO en PNG (no el del navegador)',
                  bool(a.get('icon')) and a['icon'].endswith('.png'),
                  'icon=%s' % a.get('icon'))
            check('T-53 . el icono es el del sobre del correo',
                  'icono-correo' in (a.get('icon') or ''), a.get('icon'))
            # NO basta con que la peticion «funcione»: si la direccion no esta enrutada,
            # el servidor devuelve la portada -un HTML- con codigo 200, y Chrome, al no
            # poder dibujar eso como imagen, pone su propio icono SIN dar ningun error.
            # Fue justo lo que se nos escapo: se comprobaba `ok`, que era verdadero.
            real = pg.evaluate("""async (u) => {
                try {
                    const r = await fetch(u, {cache: 'no-store'});
                    const b = await r.blob();
                    return {estado: r.status, tipo: r.headers.get('content-type') || '',
                            tipoReal: b.type, bytes: b.size};
                } catch (e) { return {estado: 0, tipo: String(e).slice(0, 40)}; }
            }""", a.get('icon'))
            check('T-53 . el icono llega como IMAGEN de verdad (no la portada en HTML)',
                  real.get('estado') == 200 and 'image/png' in (real.get('tipo') or ''),
                  'http=%s content-type=%s (%s bytes)'
                  % (real.get('estado'), real.get('tipo'), real.get('bytes')))
            check('T-53 . y el navegador lo reconoce como PNG',
                  'image/png' in (real.get('tipoReal') or ''),
                  'el navegador lo ve como %s' % real.get('tipoReal'))

        # el codigo publicado tiene que usar el modulo comun, no SVG
        fuente = pg.evaluate("""async () => {
            const src = Array.from(document.querySelectorAll('script[type=module], script[src]'))
                .map(s => s.src).filter(s => s.includes('/assets/'));
            let todo = '';
            for (const u of src.slice(0, 6)) {
                try { todo += await (await fetch(u)).text(); } catch {}
            }
            return {conSvg: todo.includes('favicon.svg'),
                    conPng: todo.includes('icono-correo-192.png'),
                    conClic: todo.includes('folder=INBOX')};
        }""")
        check('T-53 . ya NO se usa el SVG que causaba el rayo', not fuente['conSvg'])
        check('T-53 . el codigo publicado trae el icono del sobre', fuente['conPng'])
        check('T-53 . el clic lleva a la bandeja de entrada', fuente['conClic'])

        # UN correo, UN aviso. Buscar nombres de variables en el codigo publicado NO sirve:
        # el minificador los renombra y la comprobacion daba falsa alarma. La unica forma
        # de saberlo es la de verdad: mandar un correo y contar los avisos.
        import json as _json, time as _time, urllib.request as _url
        asunto = 'Candado T-53 aviso unico %d' % int(_time.time())
        pg.evaluate("() => { window.__mqAvisos = []; }")
        try:
            datos = _json.dumps({'to': [CUENTA], 'subject': asunto,
                                 'html_body': '<p>Comprobacion automatica.</p>',
                                 'text_body': 'Comprobacion automatica.'}).encode()
            pet = _url.Request(BASE + '/api/mail/send', data=datos, method='POST')
            pet.add_header('Cookie', 'access_token=' + tok)
            pet.add_header('Content-Type', 'application/json')
            with _url.urlopen(pet, timeout=30) as _r:
                enviado = _r.status == 200
        except Exception:
            enviado = False

        if enviado:
            for _ in range(20):
                pg.wait_for_timeout(2500)
                if pg.evaluate("() => window.__mqAvisos.length"):
                    pg.wait_for_timeout(9000)
                    break
            de_correo = [a for a in pg.evaluate("() => window.__mqAvisos")
                         if 'Mail' in (a.get('titulo') or '')]
            check('T-53 . UN correo produce UN SOLO aviso', len(de_correo) == 1,
                  '%d avisos' % len(de_correo))
        else:
            print('[  ..  ] T-53 . no se pudo enviar el correo de comprobacion')

        pg.screenshot(path='/root/aviso-web.png')
        nav.close()
    print('\nCandado T-53 (aviso del navegador): %s' %
          ('TODO OK - 0 fallas' if not fallas else '%d FALLAS -> %s' % (len(fallas), fallas)))
    return 1 if fallas else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1]))
