#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""T-49 - Candado del indicador de espacio y del boton «Liberar espacio».

Lo que de verdad hay que asegurar: que liberar NO se lleve por delante lo que la persona
escribio y todavia no ha salido. Eso se comprueba primero.
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
        ctx = nav.new_context(user_agent=UA, viewport={'width': 1366, 'height': 900})
        ctx.add_cookies([{'name': 'access_token', 'value': tok,
                          'domain': HOST, 'path': '/'}])
        pg = ctx.new_page()
        # una sola carga y directa a Configuracion: cargar el webmail dos veces costaba
        # mas de dos minutos en el candado completo, y no hacia falta.
        pg.goto(BASE + '/webmail/settings', wait_until='domcontentloaded', timeout=60000)
        pg.wait_for_timeout(6000)

        # se deja un correo pendiente y algo de relleno que SI se puede borrar
        pg.evaluate("""async () => {
            function abrir(n) {
                return new Promise(ok => { const p = indexedDB.open(n);
                    p.onsuccess = () => ok(p.result); p.onerror = () => ok(null); });
            }
            const db = await abrir('maquita-mail-offline');
            if (db && db.objectStoreNames.contains('outbox')) {
                const tx = db.transaction('outbox', 'readwrite');
                tx.objectStore('outbox').put({id: 'candado-espacio', createdAt: Date.now(),
                    status: 'pending', retries: 0, sobre: {v: 1, iv: new Uint8Array(12),
                    ct: new Uint8Array(400)}});
                await new Promise(ok => { tx.oncomplete = ok; tx.onerror = ok; });
            }
            if (db && db.objectStoreNames.contains('messages')) {
                const tx2 = db.transaction('messages', 'readwrite');
                for (let i = 0; i < 12; i++) {
                    tx2.objectStore('messages').put({id: 'relleno:' + i, folder: 'INBOX',
                        uid: 9000 + i, cachedAt: Date.now(),
                        sobre: {v: 1, iv: new Uint8Array(12), ct: new Uint8Array(3000)}});
                }
                await new Promise(ok => { tx2.oncomplete = ok; tx2.onerror = ok; });
            }
        }""")

        # se abre la seccion nueva (ya estamos en Configuracion)
        abierta = pg.evaluate("""() => {
            const b = Array.from(document.querySelectorAll('button'))
                .find(x => (x.textContent || '').includes('Espacio en el equipo'));
            if (b) { b.click(); return true; }
            return false;
        }""")
        check('T-49 . la Configuracion tiene la seccion «Espacio en el equipo»', abierta)
        # el espacio se calcula leyendo la base, asi que se ESPERA a que termine en vez de
        # confiar en un tiempo fijo: con el disco ocupado puede tardar mas
        try:
            pg.wait_for_function(
                "() => Array.from(document.querySelectorAll('button'))"
                ".some(b => (b.textContent || '').includes('Liberar espacio'))",
                timeout=20000)
        except Exception:
            pass

        visible = pg.evaluate("""() => {
            const t = document.body.innerText || '';
            const m = t.match(/([\\d.,]+\\s*[KMG]?B)\\s+de\\s+([\\d.,]+\\s*[KMG]?B)/);
            return {texto: m ? m[0] : '', tope: m ? m[2] : '',
                    hayBoton: !!Array.from(document.querySelectorAll('button'))
                        .find(b => (b.textContent || '').includes('Liberar espacio')),
                    avisaPendientes: t.includes('sin enviar')};
        }""")
        check('T-49 . muestra cuanto se usa y de cuanto', bool(visible['texto']),
              visible['texto'])
        check('T-49 . el tope que ensena es de 2 GB', '2' in (visible['tope'] or ''),
              'tope=%s' % visible['tope'])
        check('T-49 . esta el boton «Liberar espacio»', visible['hayBoton'])
        check('T-49 . avisa de que lo sin enviar no se toca', visible['avisaPendientes'])

        # Contar el total antes y despues no sirve: la aplicacion sigue descargando correo
        # por detras y repuebla mientras se libera, asi que el numero puede subir sin que
        # el boton haya fallado. Se comprueba algo que no depende de ese ruido: los
        # registros concretos que sembro esta prueba TIENEN que desaparecer.

        # LO IMPORTANTE: liberar no puede llevarse lo pendiente
        pg.evaluate("""() => {
            const b = Array.from(document.querySelectorAll('button'))
                .find(x => (x.textContent || '').includes('Liberar espacio'));
            if (b) b.click();
        }""")
        pg.wait_for_timeout(5000)
        despues = pg.evaluate("""async () => {
            function abrir(n) {
                return new Promise(ok => { const p = indexedDB.open(n);
                    p.onsuccess = () => ok(p.result); p.onerror = () => ok(null); });
            }
            const db = await abrir('maquita-mail-offline');
            const pend = await new Promise(ok => {
                const r = db.transaction('outbox', 'readonly').objectStore('outbox').get('candado-espacio');
                r.onsuccess = () => ok(!!r.result); r.onerror = () => ok(false);
            });
            const rell = await new Promise(ok => {
                const r = db.transaction('messages', 'readonly').objectStore('messages').count();
                r.onsuccess = () => ok(r.result); r.onerror = () => ok(-1);
            });
            // cuantos de los sembrados por la prueba sobreviven: deben ser cero
            const todos = await new Promise(ok => {
                const r = db.transaction('messages', 'readonly').objectStore('messages').getAll();
                r.onsuccess = () => ok(r.result || []); r.onerror = () => ok([]);
            });
            const sembrados = todos.filter(m => String(m.id || '').startsWith('relleno:')).length;
            return {pendienteVive: pend, mensajes: rell, relleno: sembrados};
        }""")
        check('T-49 . liberar NO se lleva lo que esta sin enviar', despues['pendienteVive'])
        # No se exige que quede en cero: en cuanto se libera, la aplicacion vuelve a
        # guardar lo que hace falta para seguir yendo rapida, que es justo lo que debe
        # hacer. Lo que se comprueba es que de verdad se vacio.
        check('T-49 . liberar si borra lo que se puede volver a descargar',
              despues['relleno'] == 0,
              'quedan %d de los 12 registros sembrados' % despues['relleno'])

        # se deja limpio
        pg.evaluate("""async () => {
            const p = indexedDB.open('maquita-mail-offline');
            await new Promise(ok => { p.onsuccess = ok; p.onerror = ok; });
            try { p.result.transaction('outbox', 'readwrite').objectStore('outbox')
                    .delete('candado-espacio'); } catch (e) {}
        }""")
        pg.wait_for_timeout(1200)
        nav.close()
    print('\nCandado T-49 (espacio en el equipo): %s' %
          ('TODO OK - 0 fallas' if not fallas else '%d FALLAS -> %s' % (len(fallas), fallas)))
    return 1 if fallas else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1]))
