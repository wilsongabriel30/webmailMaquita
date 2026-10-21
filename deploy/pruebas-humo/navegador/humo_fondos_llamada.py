#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""T-52 - Candado de los fondos en las llamadas del chat.

Lo que mas importa comprobar, por este orden:
  1. que NADA sale a internet: si el desenfoque dependiera de un CDN de fuera, fallaria
     justo cuando la conexion va mal, que es cuando mas se usa;
  2. que el espejo esta SOLO en la vista propia y no en lo que se envia;
  3. que el boton y sus opciones estan donde deben.
"""
import sys

from playwright.sync_api import sync_playwright
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from comun import BASE, HOST, CUENTA, DESTINO, PERSONA, CONVERSACION, UID_CORREO  # noqa: E402,F401

UA = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) '
      'Chrome/151.0.0.0 Safari/537.36 MaquitaTeams/0.4.69')
fallas = []
FUERA = ('cdn.jsdelivr.net', 'storage.googleapis.com', 'unpkg.com', 'cdnjs.cloudflare.com')


def check(n, ok, d=''):
    print(('[OK    ] ' if ok else '[FALLA ] ') + n + (' - ' + d if d else ''))
    if not ok:
        fallas.append(n)


def main(tok):
    externas = []
    with sync_playwright() as p:
        nav = p.chromium.launch(args=['--no-sandbox', '--use-fake-ui-for-media-stream',
                                      '--use-fake-device-for-media-stream'])
        ctx = nav.new_context(user_agent=UA, viewport={'width': 1280, 'height': 860},
                              permissions=['camera', 'microphone'])
        ctx.add_cookies([{'name': 'access_token', 'value': tok,
                          'domain': HOST, 'path': '/'}])
        pg = ctx.new_page()
        pg.on('request', lambda r: externas.append(r.url)
              if any(d in r.url for d in FUERA) else None)
        pg.goto(BASE + '/chat/llamada?role=caller&tipo=video&peer=1&name=Prueba',
                wait_until='load', timeout=60000)
        pg.wait_for_timeout(8000)

        cargado = pg.evaluate("() => typeof window.MaquitaFondos === 'object'")
        check('T-52 . el modulo de fondos esta cargado en la ventana de llamada', cargado)

        # el espejo: solo en la vista propia
        espejo = pg.evaluate("""() => {
            const v = document.getElementById('localVideo');
            if (!v) return null;
            // sin llamada de verdad el video esta oculto, y en un elemento oculto el
            // navegador informa 'none' aunque la regla exista. Se muestra un instante
            // para poder medirlo de verdad, y se deja como estaba.
            const antes = v.style.display;
            v.style.display = 'block';
            const t = getComputedStyle(v).transform;
            v.style.display = antes;
            return {clase: v.classList.contains('mq-espejo'),
                    transformacion: t,
                    otros: Array.from(document.querySelectorAll('video'))
                        .filter(x => x.id !== 'localVideo' && x.classList.contains('mq-espejo')).length};
        }""")
        check('T-52 . la vista propia se ve en espejo',
              bool(espejo and espejo['clase'] and 'matrix(-1' in (espejo['transformacion'] or '')),
              'transform=%s' % (espejo or {}).get('transformacion'))
        check('T-52 . el espejo NO se aplica a los demas videos',
              bool(espejo) and espejo['otros'] == 0,
              '%s videos ajenos en espejo' % (espejo or {}).get('otros'))

        # las opciones de fondo
        opciones = pg.evaluate("() => (window.MaquitaFondos && window.MaquitaFondos.FONDOS || []).map(f => f.id)")
        check('T-52 . estan el desenfoque y al menos un fondo de la organización',
              'desenfoque' in opciones and len(opciones) > 1,
              '%s' % opciones)

        # se carga la libreria y se comprueba de donde vienen sus piezas
        cargada = pg.evaluate("""async () => {
            try {
                const m = await import('/static/js/lib/livekit-track-processors.mjs');
                return {ok: true, tiene: typeof m.BackgroundBlur === 'function'
                                      && typeof m.VirtualBackground === 'function'};
            } catch (e) { return {ok: false, error: String(e).slice(0, 80)}; }
        }""")
        check('T-52 . la libreria de fondos carga desde NUESTRO servidor',
              cargada.get('ok') and cargada.get('tiene'),
              cargada.get('error', 'con desenfoque y fondo virtual'))

        # los archivos que necesita, servidos aqui
        for ruta in ('/static/js/lib/modelos/selfie_segmenter.tflite',
                     '/static/js/lib/mediapipe/wasm/vision_wasm_internal.wasm'):
            estado = pg.evaluate("""async (u) => {
                try { const r = await fetch(u, {method: 'HEAD'}); return r.status; }
                catch { return 0; }
            }""", ruta)
            check('T-52 . se sirve aqui %s' % ruta.split('/')[-1], estado == 200,
                  'http=%s' % estado)

        pg.wait_for_timeout(2500)
        nav.close()

    check('T-52 . NADA se pide a internet (ni CDN ni Google)', not externas,
          '; '.join(sorted(set(externas))[:2]) if externas else 'ninguna peticion externa')

    print('\nCandado T-52 (fondos en las llamadas): %s' %
          ('TODO OK - 0 fallas' if not fallas else '%d FALLAS -> %s' % (len(fallas), fallas)))
    return 1 if fallas else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1]))
